"""
Validation functions to ensure all required data points are collected.
JRA公式データとリアルタイム更新データの検証機能を含みます。
"""
import json
import os
from typing import Dict, Any, List, Optional, Tuple, Set
from logger_config import get_logger

logger = get_logger(__name__)


def validate_race_data(race_data: Dict[str, Any]) -> Tuple[bool, Dict[str, List[str]]]:
    """
    レースデータの完全性を検証します。
    JRA公式データ、気象データ、リアルタイムオッズデータの検証も含みます。
    """
    logger.info("レースデータの完全性を検証中...")
    
    race_id = race_data.get("race_id", "")
    is_future_race = False
    if race_id and isinstance(race_id, str) and race_id.startswith("2025"):
        is_future_race = True
        logger.info(f"未来のレース（{race_id}）を検出しました。")
    
    if is_future_race:
        required_categories = {
            "A": ["race_id", "race_name", "date", "venue_name", "course_type", "distance_meters"],
            "B": ["horses"],  # 未来レースでは馬リストのみ必須
            "C": [],  # 未来レースでは騎手/調教師データは必須ではない
            "D": ["live_odds_data"],  # 未来レースでは基本的なオッズデータのみ必須
            "E": [],  # 自己分析データは必須ではない
            "JRA": [],  # JRAデータは必須ではないが、あれば検証
            "REALTIME": []  # リアルタイムデータは必須ではないが、あれば検証
        }
        logger.info("未来レース用の検証基準を適用します（必須フィールドを削減）")
    else:
        required_categories = {
            "A": ["race_id", "race_name", "date", "venue_name", "course_type", "distance_meters", 
                  "weather", "track_condition", "race_class", "age_condition", "sex_condition", 
                  "weight_condition", "head_count", "course_details", "weather_track_details"],
            "B": ["horses"],
            "C": ["horses"],  # 騎手と調教師のデータは馬データ内にネスト
            "D": ["live_odds_data", "payouts"],
            "E": [],  # 自己分析データは必須ではない
            "JRA": [],  # JRAデータは必須ではないが、あれば検証
            "REALTIME": []  # リアルタイムデータは必須ではないが、あれば検証
        }
    
    missing_fields = {category: [] for category in ["A", "B", "C", "D", "E", "JRA", "REALTIME"]}
    
    for field in required_categories["A"]:
        if field not in race_data or race_data[field] is None:
            missing_fields["A"].append(field)
    
    if "horses" not in race_data or not race_data["horses"]:
        missing_fields["B"].append("horses")
    elif not is_future_race:
        for horse in race_data["horses"]:
            for field in ["horse_id", "horse_name", "sex", "age", "burden_weight", 
                         "pedigree_data", "training_data"]:
                if field not in horse or horse[field] is None:
                    if field not in missing_fields["B"]:
                        missing_fields["B"].append(field)
    
    if "C" in required_categories and required_categories["C"] and "horses" in race_data and race_data["horses"]:
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
    
    if "jra_data" not in race_data:
        missing_fields["JRA"].append("jra_data")
    else:
        jra_data = race_data["jra_data"]
        if not jra_data:
            missing_fields["JRA"].append("jra_data_empty")
        else:
            for field in ["race_info", "horses"]:
                if field not in jra_data or not jra_data[field]:
                    missing_fields["JRA"].append(f"jra_{field}")
    
    if "weather_data" not in race_data:
        missing_fields["REALTIME"].append("weather_data")
    else:
        weather_data = race_data["weather_data"]
        if not weather_data:
            missing_fields["REALTIME"].append("weather_data_empty")
        else:
            for field in ["forecast", "timestamp"]:
                if field not in weather_data or not weather_data[field]:
                    missing_fields["REALTIME"].append(f"weather_{field}")
    
    if "odds_data" not in race_data:
        missing_fields["REALTIME"].append("odds_data")
    else:
        odds_data = race_data["odds_data"]
        if not odds_data:
            missing_fields["REALTIME"].append("odds_data_empty")
        else:
            if "tan" not in odds_data or not odds_data["tan"]:
                missing_fields["REALTIME"].append("odds_tan")
    
    if "track_condition" not in race_data:
        missing_fields["REALTIME"].append("track_condition")
    else:
        track_condition = race_data["track_condition"]
        if not track_condition:
            missing_fields["REALTIME"].append("track_condition_empty")
    
    required_complete = True
    for category, fields in required_categories.items():
        if category == "horses":
            continue  # 特別なケースとして別途処理
        
        missing_required = [field for field in missing_fields[category] 
                           if field in required_categories[category]]
        if missing_required:
            required_complete = False
    
    if required_complete:
        logger.info("検証成功！すべての必須データポイントが存在します。")
        
        if not missing_fields["JRA"]:
            logger.info("JRA公式データも正常に取得されています。")
        else:
            logger.info("JRA公式データは取得されていませんが、必須ではありません。")
            
        if not missing_fields["REALTIME"]:
            logger.info("リアルタイム更新データも正常に取得されています。")
        else:
            logger.info("一部のリアルタイム更新データは取得されていませんが、必須ではありません。")
            
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
    """
    不足データの詳細レポートを生成します。
    JRA公式データとリアルタイム更新データの状態も含めます。
    """
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
            elif category == "E":
                report += "## E. 自己分析\n\n"
            elif category == "JRA":
                report += "## JRA公式データ\n\n"
            elif category == "REALTIME":
                report += "## リアルタイム更新データ\n\n"
            
            for field in fields:
                if field == "jra_data":
                    report += "- JRA公式データ（出馬表PDFなど）\n"
                elif field == "jra_data_empty":
                    report += "- JRA公式データが空です\n"
                elif field == "jra_race_info":
                    report += "- JRAレース情報\n"
                elif field == "jra_horses":
                    report += "- JRA出走馬情報\n"
                elif field == "weather_data":
                    report += "- 気象庁データ\n"
                elif field == "weather_data_empty":
                    report += "- 気象データが空です\n"
                elif field == "weather_forecast":
                    report += "- 天気予報データ\n"
                elif field == "weather_timestamp":
                    report += "- 気象データのタイムスタンプ\n"
                elif field == "odds_data":
                    report += "- リアルタイムオッズデータ\n"
                elif field == "odds_data_empty":
                    report += "- オッズデータが空です\n"
                elif field == "odds_tan":
                    report += "- 単勝オッズ\n"
                elif field == "track_condition":
                    report += "- 馬場状態データ\n"
                elif field == "track_condition_empty":
                    report += "- 馬場状態データが空です\n"
                else:
                    report += f"- {field}\n"
            report += "\n"
    
    if not has_missing_data:
        report += "すべてのデータが正常に取得されました。不足データはありません。\n"
    else:
        report += "## 考えられる原因\n\n"
        
        if is_future_race:
            report += "- 未来のレースのため、一部のデータがまだ公開されていない可能性があります。\n"
            report += "  （これは正常な状態です。未来レースでは一部のデータは取得できません）\n"
        
        if missing_fields.get("JRA"):
            report += "- JRA公式サイトの構造が変更された可能性があります。\n"
            report += "- 出馬表PDFがまだ公開されていない可能性があります。\n"
        
        if missing_fields.get("REALTIME"):
            report += "- 気象庁APIの接続に問題がある可能性があります。\n"
            report += "- オッズAPIの接続に問題がある可能性があります。\n"
            report += "- 馬場状態データがまだ更新されていない可能性があります。\n"
        
        report += "- ネットワーク接続の問題により、一部のデータの取得に失敗した可能性があります。\n"
        report += "- Webサイトの構造が変更された可能性があります。\n"
        report += "- タイムアウトにより、一部のデータの取得に失敗した可能性があります。\n\n"
        
        report += "## 推奨アクション\n\n"
        
        if is_future_race:
            report += "- 未来レースの場合、レース当日に再度実行することで、より多くのデータが取得できる可能性があります。\n"
        else:
            report += "- 後日再度実行して、データが公開されているか確認してください。\n"
        
        if missing_fields.get("JRA"):
            report += "- JRA公式サイトで出馬表PDFが公開されているか確認してください。\n"
            report += "- JRAスクレイパーの設定を確認してください。\n"
        
        if missing_fields.get("REALTIME"):
            report += "- 気象庁APIの接続設定を確認してください。\n"
            report += "- オッズAPIの認証情報を確認してください。\n"
            report += "- スケジューラーが正しく動作しているか確認してください。\n"
        
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
