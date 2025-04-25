"""
オッズデータを取得するためのクライアント。
netkeibaの内部APIと商用KeiBa-ODDS-APIの両方に対応。
"""
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from logger_config import get_logger

logger = get_logger(__name__)

NETKEIBA_ODDS_API_URL = "https://race.netkeiba.com/api/api_get_jra_odds.html"

KEIBA_ODDS_API_URL = "https://api.team-nave.com/kb_odds/v1/odds"

BET_TYPE_CODES = {
    "tan_fuku": 1,    # 単勝・複勝
    "wakuren": 2,     # 枠連
    "umaren": 3,      # 馬連
    "wide": 5,        # ワイド
    "umatan": 7,      # 馬単
    "sanrentan": 9,   # 3連単
    "sanrenpuku": 8   # 3連複
}

def get_odds_from_netkeiba(race_id: str, bet_type: str = "tan_fuku", action: str = "init") -> Dict[str, Any]:
    """
    netkeibaの内部APIからオッズデータを取得します。
    
    Args:
        race_id: レースID
        bet_type: 式別（"tan_fuku", "umaren", "wide", "umatan", "sanrentan", "sanrenpuku"）
        action: "init"（最新データ）または"update"（差分）
        
    Returns:
        オッズデータを含む辞書
    """
    logger.info(f"netkeibaからオッズを取得中: {race_id}, 式別: {bet_type}")
    
    try:
        type_code = BET_TYPE_CODES.get(bet_type)
        if not type_code:
            logger.error(f"不明な式別: {bet_type}")
            return {}
            
        params = {
            "race_id": race_id,
            "type": type_code,
            "action": action
        }
        
        response = requests.get(NETKEIBA_ODDS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "data" not in data or "odds" not in data["data"]:
            logger.warning(f"オッズデータが取得できませんでした: {race_id}, {bet_type}")
            return {}
            
        odds_data = data["data"]["odds"]
        timestamp = data["data"].get("timestamp")
        
        result = {
            "race_id": race_id,
            "bet_type": bet_type,
            "timestamp": timestamp if timestamp else datetime.now().timestamp(),
            "source": "netkeiba API"
        }
        
        if bet_type == "tan_fuku":
            if "1" in odds_data and "2" in odds_data:
                result["tan"] = odds_data["1"]
                result["fuku"] = odds_data["2"]
        else:
            result["odds"] = odds_data
        
        logger.info(f"netkeibaからオッズ取得完了: {race_id}, 式別: {bet_type}")
        return result
        
    except Exception as e:  
        logger.error(f"netkeibaオッズAPI取得エラー: {e}", exc_info=True)
        return {}

def get_all_odds_from_netkeiba(race_id: str) -> Dict[str, Any]:
    """
    全式別のオッズデータを取得します。
    
    Args:
        race_id: レースID
        
    Returns:
        全式別のオッズデータを含む辞書
    """
    logger.info(f"全式別のオッズを取得中: {race_id}")
    
    all_odds = {
        "race_id": race_id,
        "timestamp": datetime.now().isoformat(),
        "source": "netkeiba API",
        "odds_data": {}
    }
    
    for bet_type in BET_TYPE_CODES.keys():
        odds = get_odds_from_netkeiba(race_id, bet_type)
        if odds:
            if bet_type == "tan_fuku":
                if "tan" in odds:
                    all_odds["odds_data"]["tan"] = odds["tan"]
                if "fuku" in odds:
                    all_odds["odds_data"]["fuku"] = odds["fuku"]
            else:
                all_odds["odds_data"][bet_type] = odds.get("odds", {})
    
    return all_odds

def get_odds_from_commercial_api(race_id: str, api_key: str, user_id: str) -> Dict[str, Any]:
    """
    商用KeiBa-ODDS-APIからオッズデータを取得します。
    
    Args:
        race_id: レースID
        api_key: APIキー
        user_id: ユーザーID
        
    Returns:
        オッズデータを含む辞書
    """
    logger.info(f"商用APIからオッズを取得中: {race_id}")
    
    try:
        params = {
            "race_id": race_id,
            "type": "win",
            "hist": 1,
            "uid": user_id,
            "key": api_key
        }
        
        response = requests.get(KEIBA_ODDS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        result = {
            "race_id": race_id,
            "timestamp": datetime.now().isoformat(),
            "source": "KeiBa-ODDS-API",
            "odds_data": data
        }
        
        logger.info(f"商用APIからオッズ取得完了: {race_id}")
        return result
        
    except Exception as e:
        logger.error(f"商用オッズAPI取得エラー: {e}", exc_info=True)
        return {}

def should_update_model(prev_odds: Dict[str, Any], curr_odds: Dict[str, Any], threshold: float = 0.15) -> bool:
    """
    オッズの変動が閾値を超えているかどうかを判定します。
    
    Args:
        prev_odds: 前回のオッズデータ
        curr_odds: 現在のオッズデータ
        threshold: 変動閾値（デフォルト: 15%）
        
    Returns:
        モデルを更新すべきかどうか
    """
    if "tan" in prev_odds.get("odds_data", {}) and "tan" in curr_odds.get("odds_data", {}):
        prev_tan = prev_odds["odds_data"]["tan"]
        curr_tan = curr_odds["odds_data"]["tan"]
        
        for horse_num, prev_value in prev_tan.items():
            if horse_num in curr_tan:
                prev_odds_value = float(prev_value[0]) if isinstance(prev_value, list) and len(prev_value) > 0 else 0
                curr_odds_value = float(curr_tan[horse_num][0]) if isinstance(curr_tan[horse_num], list) and len(curr_tan[horse_num]) > 0 else 0
                
                if prev_odds_value == 0 or curr_odds_value == 0:
                    continue
                    
                change_rate = abs(curr_odds_value - prev_odds_value) / prev_odds_value
                
                if change_rate >= threshold:
                    logger.info(f"オッズ変動閾値超過: 馬番 {horse_num}, 変動率 {change_rate:.2f}, 前回 {prev_odds_value}, 現在 {curr_odds_value}")
                    return True
        
        prev_top3 = sorted(prev_tan.items(), key=lambda x: float(x[1][0]) if isinstance(x[1], list) and len(x[1]) > 0 else float('inf'))[:3]
        curr_top3 = sorted(curr_tan.items(), key=lambda x: float(x[1][0]) if isinstance(x[1], list) and len(x[1]) > 0 else float('inf'))[:3]
        
        prev_top3_nums = [x[0] for x in prev_top3]
        curr_top3_nums = [x[0] for x in curr_top3]
        
        if prev_top3_nums != curr_top3_nums:
            logger.info(f"人気順変動: 前回 {prev_top3_nums}, 現在 {curr_top3_nums}")
            return True
    
    return False
