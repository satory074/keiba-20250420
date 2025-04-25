"""
Enhanced main script for horse racing prediction with improved robustness.
JRA公式データとリアルタイム更新に対応したパイプライン実装。
"""
import argparse
import json
import os
import time
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# Import utilities
from utils import get_soup, initialize_driver
from headless_browser import initialize_driver_with_fallback, safe_get_with_retry
from logger_config import get_logger

from scrapers.jra_scraper import get_jra_calendar, get_race_entries_pdf, parse_race_entries_pdf
from api.jma_client import get_weather_forecast
from api.odds_client import get_odds_from_netkeiba, get_all_odds_from_netkeiba, should_update_model
from scheduler import RaceDataScheduler

# Get logger instance
logger = get_logger(__name__)


def load_test_data(race_id: str) -> Optional[Dict[str, Any]]:
    """
    テストデータをロードします（利用可能な場合）。
    
    Args:
        race_id: テストデータをロードするレースID
        
    Returns:
        レースデータを含む辞書、またはテストデータが見つからない場合はNone
    """
    test_filename = f"test_data/flora_stakes_test.json"
    
    if os.path.exists(test_filename):
        try:
            with open(test_filename, "r", encoding="utf-8") as f:
                race_data = json.load(f)
            logger.info(f"レース {race_id} のテストデータを {test_filename} からロードしました")
            return race_data
        except json.JSONDecodeError as e:
            logger.error(f"テストデータJSONの解析エラー: {e}")
    
    return None


def fetch_jra_data(race_id: str) -> Dict[str, Any]:
    """
    JRA公式サイトからデータを取得します。
    
    Args:
        race_id: レースID
        
    Returns:
        JRAデータを含む辞書
    """
    logger.info(f"JRA公式データの取得を開始: レースID {race_id}")
    
    year = race_id[0:4]
    month = race_id[4:6]
    day = race_id[6:8]
    venue_code = race_id[8:10]
    race_number = race_id[10:12]
    
    calendar_data = get_jra_calendar(year)
    
    pdf_path = get_race_entries_pdf(year, month, day, venue_code, race_number)
    
    horses_data = []
    if pdf_path:
        horses_data = parse_race_entries_pdf(pdf_path)
        logger.info(f"JRA出馬表PDFから{len(horses_data)}頭の馬情報を抽出しました")
    else:
        logger.warning("JRA出馬表PDFの取得または解析に失敗しました")
    
    jra_data = {
        "race_id": race_id,
        "calendar_data": calendar_data,
        "pdf_path": pdf_path,
        "horses": horses_data,
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"JRA公式データの取得完了: レースID {race_id}")
    return jra_data


def fetch_weather_data(race_id: str, venue_code: str) -> Dict[str, Any]:
    """
    気象庁APIから天気予報データを取得します。
    
    Args:
        race_id: レースID
        venue_code: 競馬場コード
        
    Returns:
        天気予報データを含む辞書
    """
    logger.info(f"気象データの取得を開始: レースID {race_id}, 競馬場 {venue_code}")
    
    weather_data = get_weather_forecast(venue_code)
    
    if not weather_data:
        logger.warning(f"気象データの取得に失敗しました: 競馬場 {venue_code}")
        weather_data = {
            "venue_code": venue_code,
            "forecast": {},
            "timestamp": datetime.now().isoformat()
        }
    
    logger.info(f"気象データの取得完了: レースID {race_id}")
    return weather_data


def fetch_odds_data(race_id: str) -> Dict[str, Any]:
    """
    netkeibaからオッズデータを取得します。
    
    Args:
        race_id: レースID
        
    Returns:
        オッズデータを含む辞書
    """
    logger.info(f"オッズデータの取得を開始: レースID {race_id}")
    
    odds_data = get_all_odds_from_netkeiba(race_id)
    
    if not odds_data or not odds_data.get("odds_data"):
        logger.warning(f"オッズデータの取得に失敗しました: レースID {race_id}")
        odds_data = {
            "race_id": race_id,
            "odds_data": {},
            "timestamp": datetime.now().isoformat()
        }
    
    logger.info(f"オッズデータの取得完了: レースID {race_id}")
    return odds_data


def initialize_scheduler(race_ids: List[str], callback=None) -> RaceDataScheduler:
    """
    リアルタイム更新用のスケジューラを初期化します。
    
    Args:
        race_ids: 監視するレースIDのリスト
        callback: データ更新時に呼び出すコールバック関数
        
    Returns:
        初期化されたスケジューラインスタンス
    """
    logger.info(f"{len(race_ids)}件のレースのリアルタイム更新スケジューラを初期化中...")
    
    scheduler = RaceDataScheduler()
    
    for race_id in race_ids:
        venue_code = None
        if len(race_id) >= 10:
            venue_code_num = race_id[8:10]
            venue_mapping = {
                "01": "sapporo",
                "02": "hakodate",
                "03": "fukushima",
                "04": "niigata",
                "05": "tokyo",
                "06": "nakayama",
                "07": "chukyo",
                "08": "kyoto",
                "09": "hanshin",
                "10": "kokura"
            }
            venue_code = venue_mapping.get(venue_code_num)
        
        if venue_code:
            scheduler.add_race(race_id, venue_code)
            logger.info(f"レースID {race_id} (競馬場: {venue_code}) をスケジューラに追加しました")
        else:
            logger.warning(f"レースID {race_id} の競馬場コードを特定できませんでした")
    
    if callback:
        scheduler.set_update_callback(callback)
    
    logger.info("リアルタイム更新スケジューラの初期化完了")
    return scheduler


def main(race_id: str, use_headless: bool = True, use_cache: bool = True, use_test_data: bool = False, 
         enable_realtime: bool = True, update_interval: int = 2):
    """
    JRA公式データとリアルタイム更新に対応した強化版メイン関数。
    
    Args:
        race_id: 取得対象のレースID
        use_headless: ヘッドレスブラウザを使用するかどうか
        use_cache: キャッシュデータを使用するかどうか
        use_test_data: テストデータを使用するかどうか
        enable_realtime: リアルタイム更新を有効にするかどうか
        update_interval: 更新間隔（分）
    """
    logger.info(f"レース {race_id} の強化版データ収集を開始します")
    
    is_future_race = race_id.startswith("2025") or race_id.startswith("2026")
    logger.info(f"レースタイプ: {'未来レース' if is_future_race else '過去レース'}")
    
    cache_filename = f"race_data_{race_id}.json"
    if use_cache and os.path.exists(cache_filename):
        logger.info(f"レース {race_id} のキャッシュデータが見つかりました。{cache_filename} から読み込みます")
        try:
            with open(cache_filename, "r", encoding="utf-8") as f:
                race_data = json.load(f)
            logger.info(f"レース {race_id} のキャッシュデータの読み込みに成功しました")
            
            if "timestamp" in race_data:
                cache_time = datetime.fromisoformat(race_data["timestamp"])
                current_time = datetime.now()
                time_diff = current_time - cache_time
                
                if time_diff.total_seconds() > 21600:  # 6時間 = 21600秒
                    logger.info(f"キャッシュデータが古いため（{time_diff.total_seconds()/3600:.1f}時間経過）、新しいデータを取得します")
                else:
                    if enable_realtime and is_future_race:
                        logger.info("リアルタイム更新を開始します...")
                        start_realtime_updates(race_id, race_data)
                    return race_data
            else:
                logger.info("キャッシュデータにタイムスタンプがないため、新しいデータを取得します")
        except Exception as e:
            logger.warning(f"キャッシュデータの読み込みエラー: {e}。新しいデータを取得します")
    
    if use_test_data:
        test_data = load_test_data(race_id)
        if test_data:
            logger.info(f"レース {race_id} のテストデータを使用します")
            
            with open(cache_filename, "w", encoding="utf-8") as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
            logger.info(f"テストデータを {cache_filename} に保存しました")
            
            return test_data
    
    logger.info(f"レース {race_id} のキャッシュまたはテストデータが利用できません。新しいデータを取得します...")
    
    driver = None
    if use_headless:
        driver = initialize_driver_with_fallback()
    else:
        driver = initialize_driver()
    
    if not driver:
        logger.error("WebDriverの初期化に失敗しました。Seleniumが必要なデータは取得できません。")
        logger.info("最小限のデータ収集にフォールバックします...")
    
    race_data = {"race_id": race_id}
    
    logger.info(f"レースDBページを取得中: https://db.netkeiba.com/race/{race_id}")
    soup = get_soup(f"https://db.netkeiba.com/race/{race_id}")
    
    if soup:
        from scrapers.race_scraper import scrape_race_info, scrape_detailed_race_results
        from scrapers.horse_scraper import scrape_horse_list
        
        logger.info("レース情報を抽出中...")
        race_info = scrape_race_info(soup, race_id)
        race_data.update(race_info)
        
        logger.info("出走馬リストを抽出中...")
        horses = scrape_horse_list(soup)
        if horses:
            race_data["horses"] = horses
        else:
            logger.warning(f"レースDBページから出走馬リストの抽出に失敗しました。データが不完全な可能性があります。")
    else:
        logger.warning(f"レース {race_id} のDBページの取得に失敗しました。データが不完全な可能性があります。")
    
    if is_future_race:
        logger.info("未来レースのためJRA公式データを取得します...")
        jra_data = fetch_jra_data(race_id)
        
        if jra_data:
            race_data["jra_data"] = jra_data
            
            if not race_data.get("horses") and jra_data.get("horses"):
                race_data["horses"] = jra_data["horses"]
                logger.info(f"JRAデータから{len(jra_data['horses'])}頭の馬情報を補完しました")
            
            if not race_data.get("venue_name") and jra_data.get("venue_name"):
                race_data["venue_name"] = jra_data["venue_name"]
                logger.info(f"JRAデータから競馬場情報を補完しました: {jra_data['venue_name']}")
        
        venue_code = None
        if "venue_name" in race_data:
            venue_mapping = {
                "札幌": "sapporo",
                "函館": "hakodate",
                "福島": "fukushima",
                "新潟": "niigata",
                "東京": "tokyo",
                "中山": "nakayama",
                "中京": "chukyo",
                "京都": "kyoto",
                "阪神": "hanshin",
                "小倉": "kokura"
            }
            venue_code = venue_mapping.get(race_data["venue_name"])
        
        if venue_code:
            logger.info(f"競馬場 {venue_code} の気象データを取得します...")
            weather_data = fetch_weather_data(race_id, venue_code)
            if weather_data:
                race_data["weather_data"] = weather_data
                logger.info("気象データの取得に成功しました")
    
    if driver:
        from scrapers.shutuba_scraper import scrape_shutuba_past
        from scrapers.odds_scraper import scrape_live_odds
        from scrapers.paddock_scraper import scrape_paddock_info
        from scrapers.announcement_scraper import scrape_race_announcements
        
        from config import SHUTUBA_PAST_URL
        shutuba_url = SHUTUBA_PAST_URL.format(race_id)
        logger.info(f"Seleniumで過去成績ページを取得中: {shutuba_url}")
        
        if safe_get_with_retry(driver, shutuba_url):
            shutuba_data = scrape_shutuba_past(driver, race_id)
            
            if not race_data.get("horses") and shutuba_data:
                race_data["horses"] = shutuba_data.get("horses", [])
            elif race_data.get("horses") and shutuba_data:
                horse_map = {horse.get("umaban"): horse for horse in race_data["horses"]}
                
                for shutuba_horse in shutuba_data.get("horses", []):
                    umaban = shutuba_horse.get("umaban")
                    if umaban in horse_map:
                        horse_map[umaban].update(shutuba_horse)
                
                race_data["horses"] = list(horse_map.values())
        else:
            logger.warning(f"レース {race_id} の過去成績ページの取得に失敗しました。データが不完全な可能性があります。")
        
        logger.info("リアルタイムオッズを取得中...")
        live_odds = scrape_live_odds(driver, race_id)
        race_data["live_odds_data"] = live_odds
        
        logger.info("API経由でオッズデータを取得中...")
        api_odds = fetch_odds_data(race_id)
        if api_odds and api_odds.get("odds_data"):
            race_data["api_odds_data"] = api_odds
            logger.info("API経由でのオッズデータ取得に成功しました")
        
        logger.info("パドック情報を取得中...")
        paddock_info = scrape_paddock_info(driver, race_id)
        race_data["paddock_info"] = paddock_info
        
        logger.info("レース発表情報を取得中...")
        announcements = scrape_race_announcements(driver, race_id)
        race_data["announcements"] = announcements
        
        driver.quit()
        logger.info("WebDriverを閉じました。")
    
    from scrapers.race_scraper import scrape_course_details
    from scrapers.horse_scraper import scrape_horse_details, scrape_horse_results, scrape_pedigree, scrape_training
    from scrapers.jockey_scraper import scrape_jockey_profile
    from scrapers.trainer_scraper import scrape_trainer_profile
    from scrapers.odds_scraper import scrape_odds
    from scrapers.speed_figure_scraper import scrape_speed_figures
    
    logger.info(f"{len(race_data.get('horses', []))}頭の詳細情報を取得中...")
    
    for i, horse in enumerate(race_data.get("horses", [])):
        horse_id = horse.get("horse_id")
        if not horse_id:
            continue
        
        horse_details = scrape_horse_details(horse_id)
        if horse_details:
            horse.update(horse_details)
        
        horse_results = scrape_horse_results(horse_id)
        if horse_results:
            horse["recent_results"] = horse_results
        
        pedigree_data = scrape_pedigree(horse_id)
        if pedigree_data:
            horse["pedigree_data"] = pedigree_data
        
        training_data = scrape_training(horse_id)
        if training_data:
            horse["training_data"] = training_data
        
        jockey_id = horse.get("jockey_id")
        if jockey_id:
            jockey_profile = scrape_jockey_profile(jockey_id)
            if jockey_profile:
                horse["jockey_profile"] = jockey_profile
        
        trainer_id = horse.get("trainer_id")
        if trainer_id:
            trainer_profile = scrape_trainer_profile(trainer_id)
            if trainer_profile:
                horse["trainer_profile"] = trainer_profile
        
        logger.info(f"馬 {i+1}/{len(race_data.get('horses', []))}: {horse.get('horse_name', '不明')} の処理完了")
        
        time.sleep(0.5)
    
    logger.info("詳細なレース結果ページを取得中（ラップタイム、タイム差など）...")
    detailed_results = scrape_detailed_race_results(race_id)
    if detailed_results:
        race_data.update(detailed_results)
    
    logger.info("オッズデータを取得中...")
    odds_data = scrape_odds(race_id)
    if odds_data:
        race_data["odds_data"] = odds_data
    
    logger.info("スピード指数を取得中...")
    speed_figures = scrape_speed_figures(race_id)
    race_data["speed_figures"] = speed_figures
    
    if "venue_name" in race_data:
        logger.info(f"競馬場 {race_data['venue_name']} のコース詳細を取得中...")
        course_details = scrape_course_details(race_data["venue_name"])
        race_data["course_details"] = course_details
    else:
        logger.warning("venue_nameがrace_dataにないため、コース詳細を取得できません。")
    
    output_filename = f"race_data_{race_id}.json"
    logger.info(f"データを {output_filename} に保存中...")
    
    race_data["timestamp"] = datetime.now().isoformat()
    
    from validator import validate_and_save_race_data
    
    validation_result = validate_and_save_race_data(race_data, output_filename)
    if validation_result:
        logger.info("データ検証成功！すべての必須フィールドが存在します。")
    else:
        missing_data_filename = f"missing_data_{race_id}.txt"
        if os.path.exists(missing_data_filename):
            logger.info(f"取得できなかったデータの一覧を表示します：")
            with open(missing_data_filename, "r", encoding="utf-8") as f:
                missing_data_report = f.read()
                print("\n" + "="*80)
                print(missing_data_report)
                print("="*80 + "\n")
        logger.warning("データ検証で不足フィールドが見つかりました。詳細は検証レポートを確認してください。")
    
    if enable_realtime and is_future_race:
        logger.info("リアルタイム更新を開始します...")
        start_realtime_updates(race_id, race_data)
    
    return race_data


def start_realtime_updates(race_id: str, race_data: Dict[str, Any]):
    """
    リアルタイム更新を開始します。
    
    Args:
        race_id: レースID
        race_data: 現在のレースデータ
    """
    logger.info(f"レース {race_id} のリアルタイム更新を開始します")
    
    venue_code = None
    if "venue_name" in race_data:
        venue_mapping = {
            "札幌": "sapporo",
            "函館": "hakodate",
            "福島": "fukushima",
            "新潟": "niigata",
            "東京": "tokyo",
            "中山": "nakayama",
            "中京": "chukyo",
            "京都": "kyoto",
            "阪神": "hanshin",
            "小倉": "kokura"
        }
        venue_code = venue_mapping.get(race_data["venue_name"])
    
    if not venue_code:
        logger.warning(f"競馬場コードが取得できないため、リアルタイム更新を開始できません。")
        return
    
    def update_callback(update_type: str, data: Dict[str, Any]):
        """
        データ更新時のコールバック関数。
        
        Args:
            update_type: 更新タイプ（"weather", "odds", "track_condition"）
            data: 更新データ
        """
        logger.info(f"リアルタイム更新を受信: タイプ={update_type}")
        
        cache_filename = f"race_data_{race_id}.json"
        current_data = {}
        
        try:
            with open(cache_filename, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception as e:
            logger.error(f"キャッシュデータの読み込みエラー: {e}")
            return
        
        if update_type == "weather":
            current_data["weather_data"] = data
            logger.info("気象データを更新しました")
        elif update_type == "odds":
            current_data["api_odds_data"] = data
            logger.info("オッズデータを更新しました")
        elif update_type == "track_condition":
            current_data["track_condition"] = data.get("track_condition")
            logger.info("馬場状態を更新しました")
        
        current_data["timestamp"] = datetime.now().isoformat()
        current_data["last_update_type"] = update_type
        
        try:
            with open(cache_filename, "w", encoding="utf-8") as f:
                json.dump(current_data, f, ensure_ascii=False, indent=2)
            logger.info(f"更新されたデータを {cache_filename} に保存しました")
            
            from betting_recommendation import generate_recommendations
            generate_recommendations(race_id)
            logger.info("予測モデルを再計算しました")
        except Exception as e:
            logger.error(f"更新データの保存エラー: {e}")
    
    scheduler = initialize_scheduler([race_id], update_callback)
    
    scheduler.start()
    logger.info(f"レース {race_id} のリアルタイム更新スケジューラを開始しました")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced scraper for horse racing data from netkeiba.com")
    parser.add_argument("race_id", help="Race ID to scrape data for")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache usage")
    parser.add_argument("--no-test-data", action="store_true", help="Disable test data usage")
    
    args = parser.parse_args()
    
    try:
        race_data = main(args.race_id, not args.no_headless, not args.no_cache, not args.no_test_data)
        logger.info(f"Data collection complete for race {args.race_id}")
        
        # Run betting recommendation
        logger.info(f"Generating betting recommendations for race {args.race_id}")
        from betting_recommendation import generate_recommendations
        generate_recommendations(args.race_id)
    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
