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
    
    is_future_race = False
    if race_data.get("race_id") and race_data.get("race_id").startswith("2025"):
        is_future_race = True
        logger.info(f"未来のレース（{race_data.get('race_id')}）を検出しました。")
    
    if is_future_race:
        required_categories = {
            "A": [
                "race_id", "race_name", "date", "venue_name", "race_number", 
                "course_type", "distance_meters", "race_class", "age_condition", 
                "sex_condition", "weight_condition", "head_count",
                "course_details",
                "weather_track_details"
            ],
            "B": ["horses"],  # Require horse list with basic info
            "C": [],  # Jockey/trainer data might be limited for future races
            "D": ["live_odds_data"],  # Require odds data for future races
        }
        logger.info("未来レース用の検証基準を適用します（一部のフィールドのみ必須）")
    else:
        required_categories = {
            "A": [
                "race_id", "race_name", "date", "venue_name", "race_number", 
                "course_type", "distance_meters", "race_class", "age_condition", 
                "sex_condition", "weight_condition", "head_count",
                "course_details",
                "weather",
                "track_condition",
                "weather_track_details",
                "lap_times", "pace_segments"
            ],
            "B": ["horses"],
            "C": ["horses"],  # Jockey and trainer data is nested within horses
            "D": ["live_odds_data", "payouts"],
        }
    
    missing_fields = {category: [] for category in ["A", "B", "C", "D", "E"]}
    
    for field in required_categories["A"]:
        if field not in race_data or race_data[field] is None:
            missing_fields["A"].append(field)
    
    if "course_details" in race_data and race_data["course_details"]:
        course_details = race_data["course_details"]
        for field in ["straight_length", "corner_shape", "elevation", "track_bias"]:
            if field not in course_details or course_details[field] is None:
                missing_fields["A"].append(f"course_details.{field}")
    
    if "weather_track_details" in race_data and race_data["weather_track_details"]:
        wt_details = race_data["weather_track_details"]
        if "summary_text" not in wt_details or not wt_details["summary_text"]:
            missing_fields["A"].append("weather_track_details.summary_text")
        if "summary_text" in wt_details and wt_details["summary_text"]:
            if "左" not in wt_details["summary_text"] and "右" not in wt_details["summary_text"]:
                missing_fields["A"].append("course_direction")
    
    if "horses" not in race_data or not race_data["horses"]:
        missing_fields["B"].append("horses")
    else:
        for horse in race_data["horses"]:
            for field in ["umaban", "horse_name"]:
                if field not in horse or horse[field] is None:
                    if field not in missing_fields["B"]:
                        missing_fields["B"].append(field)
        
        if not is_future_race:
            for horse in race_data["horses"]:
                for field in ["horse_id", "sex", "age", "burden_weight"]:
                    if field not in horse or horse[field] is None:
                        if field not in missing_fields["B"]:
                            missing_fields["B"].append(field)
                
                if "past_5_races" not in horse or not horse["past_5_races"]:
                    if "past_5_races" not in missing_fields["B"]:
                        missing_fields["B"].append("past_5_races")
                
                if "pedigree_data" not in horse or not horse["pedigree_data"]:
                    if "pedigree_data" not in missing_fields["B"]:
                        missing_fields["B"].append("pedigree_data")
                
                if "training_data" not in horse or not horse["training_data"]:
                    if "training_data" not in missing_fields["B"]:
                        missing_fields["B"].append("training_data")
    
    if "paddock_info" not in race_data or not race_data["paddock_info"] or not race_data["paddock_info"].get("paddock_observations"):
        if not is_future_race:
            missing_fields["B"].append("paddock_info")
    
    if "speed_figures" not in race_data or not race_data["speed_figures"] or not race_data["speed_figures"].get("figures"):
        if not is_future_race:
            missing_fields["B"].append("speed_figures")
    
    if "horses" in race_data and race_data["horses"] and not is_future_race:
        for horse in race_data["horses"]:
            if "jockey_profile" not in horse or not horse["jockey_profile"]:
                if "jockey_profile" not in missing_fields["C"]:
                    missing_fields["C"].append("jockey_profile")
            
            if "trainer_profile" not in horse or not horse["trainer_profile"]:
                if "trainer_profile" not in missing_fields["C"]:
                    missing_fields["C"].append("trainer_profile")
    
    for field in required_categories["D"]:
        if field not in race_data or race_data[field] is None:
            missing_fields["D"].append(field)
    
    if "live_odds_data" in race_data and race_data["live_odds_data"]:
        odds_data = race_data["live_odds_data"]
        if "odds" not in odds_data or not odds_data["odds"]:
            missing_fields["D"].append("live_odds_data.odds")
        else:
            for bet_type in ["tan_fuku", "umaren", "wide", "umatan", "sanrentan", "sanrenpuku"]:
                if bet_type not in odds_data["odds"] or not odds_data["odds"][bet_type]:
                    missing_fields["D"].append(f"live_odds_data.odds.{bet_type}")
    
    required_complete = True
    for category, fields in required_categories.items():
        if category == "horses":
            continue  # Special case handled separately
        
        missing_required = [field for field in missing_fields[category] 
                           if any(req_field in field for req_field in required_categories[category])]
        if missing_required:
            required_complete = False
    
    if required_complete:
        logger.info("検証成功！すべての必須データポイントが存在します。")
        if is_future_race:
            logger.info("未来レースのため、一部のデータが欠けていますが、必須データは揃っています。")
    else:
        for category, fields in missing_fields.items():
            if fields:
                logger.warning(f"カテゴリ {category} の不足フィールド: {', '.join(fields)}")
    
    return required_complete, missing_fields


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
        
        logger.info("取得できなかったデータの一覧を表示します：\n")
        logger.info("=" * 80)
        logger.info(missing_data_report)
        logger.info("=" * 80)
        
        if is_valid:
            logger.info("データ検証に成功しました。すべての必須フィールドが存在します。")
        else:
            logger.warning("データ検証で不足フィールドが見つかりました。詳細は検証レポートを確認してください。")
        
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
    
    is_future_race = race_id.startswith("2025")
    
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
        
        if is_future_race:
            report += "- 未来のレースのため、一部のデータがまだ公開されていない可能性があります。\n"
            report += "  （これは正常な状態です。未来レースでは一部のデータは取得できません）\n"
        
        report += "- ネットワーク接続の問題により、一部のデータの取得に失敗した可能性があります。\n"
        report += "- Webサイトの構造が変更された可能性があります。\n"
        report += "- タイムアウトにより、一部のデータの取得に失敗した可能性があります。\n\n"
        
        report += "## 推奨アクション\n\n"
        
        if is_future_race:
            report += "- 未来レースの場合、レース当日に再度実行することで、より多くのデータが取得できる可能性があります。\n"
        else:
            report += "- 後日再度実行して、データが公開されているか確認してください。\n"
        
        report += "- ネットワーク接続を確認してください。\n"
        report += "- config.pyのSELENIUM_WAIT_TIMEを増やして再試行してください。\n"
        
        if is_future_race:
            report += "\n## 未来レースについての注意\n\n"
            report += "未来レースでは、以下のデータは通常取得できません：\n"
            report += "- 天候・馬場状態（レース当日まで確定しない）\n"
            report += "- 確定した出走馬情報（馬ID、性別、年齢、斤量など）\n"
            report += "- 騎手・調教師の詳細情報\n"
            report += "- 確定した払戻情報（レース終了後に公開）\n\n"
            report += "これらのデータが不足していても、基本的なレース情報とオッズ情報が取得できていれば、\n"
            report += "予測に必要な最低限のデータは揃っていると判断されます。\n"
    
    return report
