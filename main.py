"""
Main script to orchestrate the Netkeiba race data scraping process.
"""
import argparse
import json
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

from config import BASE_URL_NETKEIBA
from logger_config import get_logger
from utils import initialize_driver, get_soup

from scrapers.race_scraper import scrape_race_info, scrape_detailed_race_results, scrape_course_details
from scrapers.horse_scraper import (
    scrape_horse_list,
    scrape_horse_details,
    scrape_horse_results,
    scrape_pedigree,
    scrape_training,
)
from scrapers.jockey_scraper import scrape_jockey_profile
from scrapers.trainer_scraper import scrape_trainer_profile
from scrapers.odds_scraper import scrape_odds, scrape_live_odds
from scrapers.shutuba_scraper import scrape_shutuba_past
from scrapers.paddock_scraper import scrape_paddock_info
from scrapers.speed_figure_scraper import scrape_speed_figures
from scrapers.announcement_scraper import scrape_race_announcements

from betting_recommendation import generate_recommendations

logger = get_logger(__name__)


def main(race_id):
    """Main function to orchestrate the scraping process."""
    logger.info(f"レースID {race_id} のデータ収集を開始します")
    driver = None  # Initialize driver to None
    race_data = {}  # Initialize race_data
    
    cached_data_file = f"race_data_{race_id}.json"
    if os.path.exists(cached_data_file):
        logger.info(f"キャッシュデータが見つかりました（race {race_id}）。{cached_data_file}から読み込みます")
        try:
            with open(cached_data_file, 'r', encoding='utf-8') as f:
                race_data = json.load(f)
            logger.info(f"キャッシュデータの読み込みに成功しました")
            
            data_incomplete = False
            if "horses" not in race_data or not race_data["horses"]:
                logger.warning("キャッシュデータに出走馬情報がありません。新しいデータを取得します。")
                data_incomplete = True
            elif "race_name" not in race_data or not race_data["race_name"]:
                logger.warning("キャッシュデータにレース名がありません。新しいデータを取得します。")
                data_incomplete = True
            
            if not data_incomplete and "timestamp" in race_data:
                cache_time = datetime.fromisoformat(race_data["timestamp"])
                current_time = datetime.now()
                time_diff = current_time - cache_time
                
                if time_diff.total_seconds() > 21600:  # 6時間 = 21600秒
                    logger.info(f"キャッシュデータが古いため（{time_diff.total_seconds()/3600:.1f}時間経過）、新しいデータを取得します")
                else:
                    logger.info(f"キャッシュデータは最新です（{time_diff.total_seconds()/3600:.1f}時間前）")
                    recommendations = generate_recommendations(race_id)
                    return
            else:
                if not data_incomplete:
                    logger.info("キャッシュデータにタイムスタンプがないため、新しいデータを取得します")
        except Exception as e:
            logger.warning(f"キャッシュデータの読み込みエラー: {e}。新しいデータを取得します")

    try:
        driver = initialize_driver()  # Initialize WebDriver
        logger.info("WebDriverの初期化に成功しました")

        race_shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
        logger.info(f"出馬表ページを取得中: {race_shutuba_url}")
        
        if driver:
            try:
                driver.get(race_shutuba_url)
                race_soup = BeautifulSoup(driver.page_source, "html.parser")
                logger.info("出馬表ページの取得に成功しました（Selenium使用）")
            except Exception as e:
                logger.warning(f"Seleniumでの出馬表ページ取得に失敗: {e}")
                race_soup = get_soup(race_shutuba_url)
        else:
            race_soup = get_soup(race_shutuba_url)
            
        if not race_soup or "レース情報が見つかりませんでした" in race_soup.text:
            race_db_url = f"{BASE_URL_NETKEIBA}/race/{race_id}"
            logger.info(f"出馬表ページの取得に失敗したため、DBページを取得中: {race_db_url}")
            race_soup = get_soup(race_db_url)
            
        if not race_soup:
            logger.error(f"レース情報ページの取得に失敗しました。終了します。")
            return

        logger.info("レース基本情報を抽出中...")
        race_data = scrape_race_info(race_soup, race_id)
        logger.info(f"レース名: {race_data.get('race_name', '不明')}, 開催場所: {race_data.get('venue_name', '不明')}")

        logger.info("出走馬リストを抽出中...")
        horses_summary = scrape_horse_list(race_soup)
        if not horses_summary:
            logger.warning("出走馬リストの抽出に失敗しました。データが不完全な可能性があります。")
            race_data["horses"] = []
        else:
            logger.info(f"{len(horses_summary)}頭の出走馬情報を抽出しました")

        logger.info("過去成績データを取得中...")
        past_perf_by_umaban = scrape_shutuba_past(driver, race_id)
        logger.info(f"{len(past_perf_by_umaban)}頭の過去成績データを取得しました")

        logger.info(f"{len(horses_summary)}頭の詳細情報を取得中...")
        all_horse_details = []
        for i, horse_sum in enumerate(horses_summary):
            horse_id_str = horse_sum.get('horse_id', '不明')
            horse_name = horse_sum.get('horse_name', '不明')
            logger.info(f"  馬{i+1}/{len(horses_summary)}の詳細情報を取得中（ID: {horse_id_str}, 名前: {horse_name}）...")
            merged_details = horse_sum.copy()  # Start with summary data

            if 'horse_id' in horse_sum:
                horse_id = horse_sum["horse_id"]
                details = scrape_horse_details(horse_id)
                merged_details.update(details)  # Merge details

                horse_results = scrape_horse_results(horse_id)
                merged_details["full_results_data"] = horse_results

                pedigree_data = scrape_pedigree(horse_id)
                merged_details["pedigree_data"] = pedigree_data

                training_data = scrape_training(driver, horse_id)
                merged_details["training_data"] = training_data

                if merged_details.get("jockey_id"):
                    jockey_profile_data = scrape_jockey_profile(merged_details["jockey_id"])
                    merged_details["jockey_profile"] = jockey_profile_data
                if merged_details.get("trainer_id"):
                    trainer_profile_data = scrape_trainer_profile(merged_details["trainer_id"])
                    merged_details["trainer_profile"] = trainer_profile_data

            else:
                logger.warning(f"  馬{i+1}のIDが不明のため、詳細情報の取得をスキップします。")

            try:
                umaban_int = int(horse_sum.get("umaban", 0))
                if umaban_int in past_perf_by_umaban:
                    merged_details.update(past_perf_by_umaban[umaban_int])
                    logger.debug(f"馬番{umaban_int}の過去成績データをマージしました")
                else:
                    logger.debug(f"馬番{umaban_int}の過去成績データが見つかりませんでした")
            except (ValueError, TypeError):
                logger.warning(f"馬番'{horse_sum.get('umaban')}'を整数に変換できないため、過去成績データをマージできません。")

            all_horse_details.append(merged_details)

        race_data["horses"] = all_horse_details  # Assign horse details
        logger.info(f"{len(all_horse_details)}頭の詳細情報を取得完了")

        logger.info("レース詳細結果を取得中（ラップタイム、タイム差など）...")
        detailed_results = scrape_detailed_race_results(race_id)
        time_diffs = detailed_results.pop("time_diffs", {})
        race_data.update(detailed_results)  # Merge lap times, weather etc. into main race_data

        logger.info("タイム差データを馬データにマージ中...")
        if "horses" in race_data:  # Ensure horses list exists
            for horse_detail in race_data["horses"]:
                try:
                    umaban_int = int(horse_detail.get("umaban", 0))
                    if umaban_int in time_diffs:
                        horse_detail["time_diff_result_page"] = time_diffs[umaban_int]  # B3.4
                        logger.debug(f"馬番{umaban_int}のタイム差'{time_diffs[umaban_int]}'をマージしました")
                    else:
                        logger.debug(f"馬番{umaban_int}のタイム差データが見つかりませんでした")
                except (ValueError, TypeError):
                    logger.warning(f"馬番'{horse_detail.get('umaban')}'を整数に変換できないため、タイム差データをマージできません。")
        else:
            logger.warning("race_dataに'horses'キーがないため、タイム差データをマージできません。")

        logger.info("オッズデータを取得中...")
        live_odds = scrape_live_odds(driver, race_id)  # Pass driver instance
        race_data["live_odds_data"] = live_odds  # Add live odds under new key
        logger.info("オッズデータの取得完了")

        logger.info("パドック情報を取得中...")
        paddock_info = scrape_paddock_info(driver, race_id)
        race_data["paddock_info"] = paddock_info
        logger.info("パドック情報の取得完了")

        logger.info("スピード指数を取得中...")
        speed_figures = scrape_speed_figures(race_id)
        race_data["speed_figures"] = speed_figures
        logger.info("スピード指数の取得完了")

        logger.info("レース発表情報を取得中...")
        announcements = scrape_race_announcements(driver, race_id)
        race_data["announcements"] = announcements
        logger.info("レース発表情報の取得完了")

        if "venue_name" in race_data:
            logger.info(f"コース詳細情報を取得中（開催場所: {race_data['venue_name']}）...")
            course_details = scrape_course_details(race_data["venue_name"])
            race_data["course_details"] = course_details
            logger.info("コース詳細情報の取得完了")
        else:
            logger.warning("race_dataに'venue_name'キーがないため、コース詳細情報を取得できません。")

        logger.info("払戻情報を抽出中...")
        if race_soup:
            payout_data = scrape_odds(race_soup, race_id)
            race_data["payouts"] = payout_data.get("payouts", {})  # Extract only the payouts dict
            logger.info("払戻情報の抽出完了")
        else:
            logger.warning("race_soupが利用できないため、払戻情報を抽出できません。")
            race_data["payouts"] = {}

        output_filename = f"race_data_{race_id}.json"
        logger.info(f"データを検証して保存中: {output_filename}...")
        
        race_data["timestamp"] = datetime.now().isoformat()
        
        from validator import validate_and_save_race_data
        
        validation_result = validate_and_save_race_data(race_data, output_filename)
        if validation_result:
            logger.info("データ検証成功！すべての必須フィールドが存在します。")
        else:
            logger.warning("データ検証で不足フィールドが見つかりました。詳細は検証レポートを確認してください。")
        
        logger.info("馬券推奨を生成中...")
        recommendations = generate_recommendations(race_id)
        logger.info("馬券推奨の生成完了")

    except Exception as e:
        logger.error(f"レース{race_id}のメイン処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
        logger.error("実データの取得に失敗しました。データが不完全な可能性があります。")
        
        if os.path.exists(cached_data_file):
            logger.info(f"キャッシュデータを使用して分析を試みます: {cached_data_file}")
            try:
                recommendations = generate_recommendations(race_id)
                logger.info("キャッシュデータを使用した馬券推奨の生成完了")
            except Exception as rec_error:
                logger.error(f"キャッシュデータを使用した馬券推奨の生成に失敗しました: {rec_error}")
    finally:
        if driver:
            logger.info("WebDriverを終了中...")
            driver.quit()
            logger.info("WebDriver終了完了")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="netkeiba.comから指定されたレースIDのレースデータを取得します。")
    parser.add_argument("race_id", help="netkeibaのレースID（例: 202306050811）")
    args = parser.parse_args()

    if not re.match(r"^\d{12}$", args.race_id):
        logger.error(f"無効なレースID形式 '{args.race_id}'。12桁の数字が必要です。")
    else:
        main(args.race_id)
