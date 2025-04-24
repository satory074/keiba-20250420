"""
Validation functions to ensure all required data points are collected.
"""
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from logger_config import get_logger

logger = get_logger(__name__)


def validate_race_data(race_data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
    """Validates that all required data points from searchlist.md are present in the race data."""
    logger.info("Validating race data for completeness...")
    
    required_categories = {
        "A": ["race_id", "race_name", "date", "venue_name", "course_type", "distance_meters", 
              "weather", "track_condition", "race_class", "age_condition", "sex_condition", 
              "weight_condition", "head_count", "course_details", "weather_track_details", 
              "announcements"],
        "B": ["horses"],
        "C": ["horses"],  # Jockey and trainer data is nested within horses
        "D": ["live_odds_data", "payouts"],
    }
    
    missing_fields = {category: [] for category in required_categories}
    
    for field in required_categories["A"]:
        if field not in race_data or race_data[field] is None:
            missing_fields["A"].append(field)
    
    if "horses" not in race_data or not race_data["horses"]:
        missing_fields["B"].append("horses")
    else:
        for horse in race_data["horses"]:
            for field in ["horse_id", "horse_name", "sex", "age", "burden_weight", 
                         "pedigree_data", "training_data"]:
                if field not in horse or horse[field] is None:
                    if field not in missing_fields["B"]:
                        missing_fields["B"].append(field)
    
    if "horses" in race_data and race_data["horses"]:
        for horse in race_data["horses"]:
            if "jockey_profile" not in horse or horse["jockey_profile"] is None:
                if "jockey_profile" not in missing_fields["C"]:
                    missing_fields["C"].append("jockey_profile")
            if "trainer_profile" not in horse or horse["trainer_profile"] is None:
                if "trainer_profile" not in missing_fields["C"]:
                    missing_fields["C"].append("trainer_profile")
    
    for field in required_categories["D"]:
        if field not in race_data or race_data[field] is None:
            missing_fields["D"].append(field)
    
    is_future_race = False
    if race_data.get("race_id") and race_data.get("race_id").startswith("2025"):
        is_future_race = True
        logger.info(f"未来のレース（{race_data.get('race_id')}）を検出しました。")
    
    all_complete = all(len(missing) == 0 for missing in missing_fields.values())
    
    if all_complete:
        logger.info("検証成功！すべての必須データポイントが存在します。")
    else:
        for category, fields in missing_fields.items():
            if fields:
                logger.warning(f"カテゴリ {category} の不足フィールド: {', '.join(fields)}")
    
    return all_complete, missing_fields


def validate_and_save_race_data(race_data: Dict[str, Any], output_filename: str) -> bool:
    """Validates race data and saves it to a JSON file."""
    is_valid, missing_fields = validate_race_data(race_data)
    
    race_data["missing_data"] = missing_fields
    
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(race_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Data saved to {output_filename}")
        
        validation_report = {
            "filename": output_filename,
            "is_valid": is_valid,
            "timestamp": race_data.get("timestamp", None),
            "race_id": race_data.get("race_id", None),
            "race_name": race_data.get("race_name", None),
            "missing_fields": missing_fields
        }
        
        report_filename = f"validation_report_{race_data.get('race_id', 'unknown')}.json"
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(validation_report, f, ensure_ascii=False, indent=2)
        logger.info(f"Validation report saved to {report_filename}")
        
        missing_data_report = generate_missing_data_report(race_data, missing_fields)
        missing_data_filename = f"missing_data_{race_data.get('race_id', 'unknown')}.txt"
        with open(missing_data_filename, "w", encoding="utf-8") as f:
            f.write(missing_data_report)
        logger.info(f"Missing data report saved to {missing_data_filename}")
        
        return is_valid
    except Exception as e:
        logger.error(f"Error saving data: {e}", exc_info=True)
        return False


def generate_missing_data_report(race_data: Dict[str, Any], missing_fields: Dict[str, List[str]]) -> str:
    """Generates a detailed report of missing data."""
    race_id = race_data.get("race_id", "不明")
    race_name = race_data.get("race_name", "不明")
    
    report = f"# 取得できなかったデータ一覧 - レースID: {race_id}\n\n"
    report += f"レース名: {race_name}\n"
    report += f"実行日時: {race_data.get('timestamp', '不明')}\n\n"
    
    has_missing_data = False
    
    for category, fields in missing_fields.items():
        if fields:
            has_missing_data = True
            if category == "A":
                report += "## A. レース条件\n\n"
            elif category == "B":
                report += "## B. 馬情報\n\n"
            elif category == "C":
                report += "## C. 人的要素\n\n"
            elif category == "D":
                report += "## D. 市場情報\n\n"
            
            for field in fields:
                report += f"- {field}\n"
            report += "\n"
    
    if not has_missing_data:
        report += "すべてのデータが正常に取得されました。不足データはありません。\n"
    else:
        report += "## 考えられる原因\n\n"
        
        if race_id.startswith("2025"):
            report += "- 未来のレースのため、一部のデータがまだ公開されていない可能性があります。\n"
        
        report += "- ネットワーク接続の問題により、一部のデータの取得に失敗した可能性があります。\n"
        report += "- Webサイトの構造が変更された可能性があります。\n"
        report += "- タイムアウトにより、一部のデータの取得に失敗した可能性があります。\n\n"
        
        report += "## 推奨アクション\n\n"
        report += "- 後日再度実行して、データが公開されているか確認してください。\n"
        report += "- ネットワーク接続を確認してください。\n"
        report += "- config.pyのSELENIUM_WAIT_TIMEを増やして再試行してください。\n"
    
    return report
