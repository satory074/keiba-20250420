"""
定期的なデータ更新を行うスケジューラー。
"""
import time
import threading
import schedule
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional, List

from logger_config import get_logger
from api.jma_client import get_weather_forecast
from api.odds_client import get_all_odds_from_netkeiba, should_update_model
from scrapers.jra_constants import VENUE_CODES

logger = get_logger(__name__)

class RaceDataScheduler:
    """
    レースデータの定期更新を管理するスケジューラークラス。
    """
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.race_data_cache = {}  # レースIDごとのデータキャッシュ
        self.update_callbacks = []  # データ更新時のコールバック関数リスト
        self.scheduled_jobs = {}  # スケジュールされたジョブの管理
        
    def register_update_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        データ更新時に呼び出すコールバック関数を登録します。
        
        Args:
            callback: コールバック関数。引数はレースIDとデータ辞書。
        """
        self.update_callbacks.append(callback)
        
    def notify_update(self, race_id: str, data: Dict[str, Any]) -> None:
        """
        データ更新を通知します。
        
        Args:
            race_id: レースID
            data: 更新されたデータ
        """
        for callback in self.update_callbacks:
            try:
                callback(race_id, data)
            except Exception as e:
                logger.error(f"コールバック実行エラー: {e}", exc_info=True)
    
    def update_weather(self, race_id: str) -> None:
        """
        気象データを更新します。
        
        Args:
            race_id: レースID
        """
        logger.info(f"気象データ更新タスク実行: {race_id}")
        
        try:
            venue_code = race_id[8:10]
            
            venue_name = None
            for name, code in VENUE_CODES.items():
                if venue_code == code[:2]:
                    venue_name = code
                    break
                    
            if not venue_name:
                logger.error(f"不明な会場コード: {venue_code}")
                return
                
            weather_data = get_weather_forecast(venue_name)
            
            if not weather_data:
                logger.warning(f"気象データが取得できませんでした: {race_id}")
                return
                
            if race_id not in self.race_data_cache:
                self.race_data_cache[race_id] = {}
                
            prev_weather = self.race_data_cache[race_id].get("weather_data", {})
            
            update_needed = False
            
            if weather_data:
                if not prev_weather:
                    update_needed = True
                else:
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    if today_str in weather_data.get("forecast", {}):
                        today_weather = weather_data["forecast"][today_str]
                        if today_str in prev_weather.get("forecast", {}):
                            prev_today = prev_weather["forecast"][today_str]
                            
                            if today_weather.get("weather_code") != prev_today.get("weather_code"):
                                update_needed = True
                                logger.info(f"天気コードが変更されました: {prev_today.get('weather_code')} -> {today_weather.get('weather_code')}")
                            
                            prev_prob = prev_today.get("precipitation_prob", 0)
                            curr_prob = today_weather.get("precipitation_prob", 0)
                            if abs(curr_prob - prev_prob) >= 20:
                                update_needed = True
                                logger.info(f"降水確率が大幅に変更されました: {prev_prob}% -> {curr_prob}%")
                        else:
                            update_needed = True
            
            if update_needed:
                self.race_data_cache[race_id]["weather_data"] = weather_data
                logger.info(f"気象データを更新しました: {race_id}")
                
                self.notify_update(race_id, {"weather_data": weather_data})
            else:
                logger.info(f"気象データの更新は不要です: {race_id}")
                
        except Exception as e:
            logger.error(f"気象データ更新エラー: {e}", exc_info=True)
    
    def update_odds(self, race_id: str) -> None:
        """
        オッズデータを更新します。
        
        Args:
            race_id: レースID
        """
        logger.info(f"オッズデータ更新タスク実行: {race_id}")
        
        try:
            odds_data = get_all_odds_from_netkeiba(race_id)
            
            if not odds_data or not odds_data.get("odds_data"):
                logger.warning(f"オッズデータが取得できませんでした: {race_id}")
                return
                
            if race_id not in self.race_data_cache:
                self.race_data_cache[race_id] = {}
                
            prev_odds = self.race_data_cache[race_id].get("odds_data", {})
            
            update_needed = False
            
            if odds_data.get("odds_data"):
                if not prev_odds:
                    update_needed = True
                else:
                    update_needed = should_update_model(
                        {"odds_data": prev_odds}, 
                        {"odds_data": odds_data.get("odds_data", {})},
                        threshold=0.15
                    )
            
            if update_needed:
                self.race_data_cache[race_id]["odds_data"] = odds_data["odds_data"]
                logger.info(f"オッズデータを更新しました: {race_id}")
                
                self.notify_update(race_id, {"odds_data": odds_data["odds_data"]})
            else:
                logger.info(f"オッズデータの更新は不要です: {race_id}")
                
        except Exception as e:
            logger.error(f"オッズデータ更新エラー: {e}", exc_info=True)
    
    def update_track_condition(self, race_id: str) -> None:
        """
        馬場状態データを更新します。
        
        Args:
            race_id: レースID
        """
        logger.info(f"馬場状態更新タスク実行: {race_id}")
        
        try:
            
            pass
            
        except Exception as e:
            logger.error(f"馬場状態更新エラー: {e}", exc_info=True)
    
    def schedule_race_updates(self, race_id: str, race_datetime: datetime) -> None:
        """
        レースの定期更新をスケジュールします。
        
        Args:
            race_id: レースID
            race_datetime: レース開催日時
        """
        logger.info(f"レース更新スケジュール設定: {race_id}, 開催日時: {race_datetime}")
        
        now = datetime.now()
        
        is_race_day = now.date() == race_datetime.date()
        
        is_before_race = now < race_datetime
        
        if race_id not in self.scheduled_jobs:
            self.scheduled_jobs[race_id] = []
        
        if is_before_race and (race_datetime.date() - now.date()).days == 1:
            init_time = "09:00"
            logger.info(f"前日初期化処理をスケジュール: {race_id}, 時刻: {init_time}")
            
            job = schedule.every().day.at(init_time).do(self.update_weather, race_id)
            self.scheduled_jobs[race_id].append(job)
            
        if is_race_day and is_before_race:
            init_time = "09:00"
            logger.info(f"当日初期化処理をスケジュール: {race_id}, 時刻: {init_time}")
            
            job = schedule.every().day.at(init_time).do(self.update_weather, race_id)
            self.scheduled_jobs[race_id].append(job)
            
            job = schedule.every().day.at(init_time).do(self.update_track_condition, race_id)
            self.scheduled_jobs[race_id].append(job)
            
            logger.info(f"定期更新処理をスケジュール: {race_id}")
            
            job = schedule.every(30).minutes.do(self.update_weather, race_id)
            self.scheduled_jobs[race_id].append(job)
            
            job = schedule.every(30).minutes.do(self.update_track_condition, race_id)
            self.scheduled_jobs[race_id].append(job)
            
            job = schedule.every(2).minutes.do(self.update_odds, race_id)
            self.scheduled_jobs[race_id].append(job)
            
            race_end_time = race_datetime + timedelta(minutes=30)  # レース終了は約30分後と仮定
            
            def cleanup_race():
                logger.info(f"レース終了後のクリーンアップ: {race_id}")
                self.clear_race_schedule(race_id)
                
            job = schedule.every().day.at(race_end_time.strftime("%H:%M")).do(cleanup_race)
            self.scheduled_jobs[race_id].append(job)
    
    def clear_race_schedule(self, race_id: str) -> None:
        """
        特定のレースのスケジュールをクリアします。
        
        Args:
            race_id: レースID
        """
        if race_id in self.scheduled_jobs:
            for job in self.scheduled_jobs[race_id]:
                schedule.cancel_job(job)
            self.scheduled_jobs[race_id] = []
            logger.info(f"レース {race_id} のスケジュールをクリアしました")
    
    def start(self) -> None:
        """
        スケジューラーを開始します。
        """
        if self.running:
            logger.warning("スケジューラーは既に実行中です")
            return
            
        self.running = True
        
        def run_scheduler():
            logger.info("スケジューラーを開始しました")
            while self.running:
                schedule.run_pending()
                time.sleep(1)
                
        self.thread = threading.Thread(target=run_scheduler)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self) -> None:
        """
        スケジューラーを停止します。
        """
        if not self.running:
            logger.warning("スケジューラーは実行されていません")
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            logger.info("スケジューラーを停止しました")
            
    def add_race(self, race_id: str, race_datetime: datetime) -> None:
        """
        監視対象レースを追加します。
        
        Args:
            race_id: レースID
            race_datetime: レース開催日時
        """
        logger.info(f"監視対象レースを追加: {race_id}, 開催日時: {race_datetime}")
        
        self.clear_race_schedule(race_id)
        
        self.schedule_race_updates(race_id, race_datetime)
        
    def remove_race(self, race_id: str) -> None:
        """
        監視対象レースを削除します。
        
        Args:
            race_id: レースID
        """
        logger.info(f"監視対象レースを削除: {race_id}")
        
        self.clear_race_schedule(race_id)
        
        if race_id in self.race_data_cache:
            del self.race_data_cache[race_id]
