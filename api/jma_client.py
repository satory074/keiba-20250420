"""
気象庁API（気象庁防災情報XMLフォーマット形式電文）からデータを取得するクライアント。
"""
import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

from logger_config import get_logger
from scrapers.jra_constants import VENUE_CODES

logger = get_logger(__name__)

JMA_API_BASE_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast"

VENUE_TO_JMA_AREA = {
    "tokyo": "130000",    # 東京
    "nakayama": "120000", # 千葉
    "hanshin": "270000",  # 大阪
    "kyoto": "260000",    # 京都
    "fukushima": "070000", # 福島
    "niigata": "150000",  # 新潟
    "kokura": "400000",   # 福岡
    "sapporo": "016000",  # 札幌
    "hakodate": "017000", # 函館
    "chukyo": "230000"    # 愛知
}

def get_weather_forecast(venue_code: str) -> Dict[str, Any]:
    """
    指定された競馬場の気象情報を取得します。
    
    Args:
        venue_code: 競馬場コード
        
    Returns:
        気象情報を含む辞書
    """
    logger.info(f"気象庁APIから天気予報を取得中: {venue_code}")
    
    area_code = VENUE_TO_JMA_AREA.get(venue_code)
    if not area_code:
        logger.error(f"不明な競馬場コード: {venue_code}")
        return {}
        
    try:
        url = f"{JMA_API_BASE_URL}/{area_code}.json"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if not data or not isinstance(data, list) or len(data) == 0:
            logger.warning(f"気象データが取得できませんでした: {url}")
            return {}
            
        weather_data = {}
        
        timedef = data[0].get("timeSeries", [])
        if timedef and len(timedef) > 0:
            weather_series = timedef[0]
            time_series = weather_series.get("timeDefines", [])
            areas = weather_series.get("areas", [])
            
            if areas and len(areas) > 0:
                area_data = areas[0]
                weather_codes = area_data.get("weatherCodes", [])
                weathers = area_data.get("weathers", [])
                
                for i, time_str in enumerate(time_series):
                    if i < len(weathers):
                        time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        jst_time = time_dt.astimezone(timezone(timedelta(hours=9)))
                        date_str = jst_time.strftime("%Y-%m-%d")
                        
                        weather_data[date_str] = {
                            "weather": weathers[i],
                            "weather_code": weather_codes[i] if i < len(weather_codes) else None,
                            "timestamp": jst_time.isoformat()
                        }
        
        if len(data[0].get("timeSeries", [])) > 1:
            temp_series = data[0]["timeSeries"][2]
            temp_times = temp_series.get("timeDefines", [])
            areas = temp_series.get("areas", [])
            
            if areas and len(areas) > 0:
                area_data = areas[0]
                temps = area_data.get("temps", [])
                
                for i, time_str in enumerate(temp_times):
                    if i < len(temps):
                        time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        jst_time = time_dt.astimezone(timezone(timedelta(hours=9)))
                        date_str = jst_time.strftime("%Y-%m-%d")
                        
                        if date_str in weather_data:
                            weather_data[date_str]["temperature"] = int(temps[i])
        
        if len(data[0].get("timeSeries", [])) > 1:
            rain_series = data[0]["timeSeries"][1]
            rain_times = rain_series.get("timeDefines", [])
            areas = rain_series.get("areas", [])
            
            if areas and len(areas) > 0:
                area_data = areas[0]
                probs = area_data.get("pops", [])
                
                for i, time_str in enumerate(rain_times):
                    if i < len(probs):
                        time_dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                        jst_time = time_dt.astimezone(timezone(timedelta(hours=9)))
                        date_str = jst_time.strftime("%Y-%m-%d")
                        hour = jst_time.hour
                        
                        prob_key = "precipitation_prob"
                        if hour < 6:
                            prob_key = "precipitation_prob_00_06"
                        elif hour < 12:
                            prob_key = "precipitation_prob_06_12"
                        elif hour < 18:
                            prob_key = "precipitation_prob_12_18"
                        else:
                            prob_key = "precipitation_prob_18_24"
                        
                        if date_str in weather_data:
                            weather_data[date_str][prob_key] = int(probs[i]) if probs[i].isdigit() else 0
        
        logger.info(f"気象庁APIから天気予報取得完了: {venue_code}")
        
        result = {
            "venue_code": venue_code,
            "source": "気象庁",
            "forecast": weather_data,
            "timestamp": datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.error(f"気象庁API取得エラー: {e}", exc_info=True)
        return {}
