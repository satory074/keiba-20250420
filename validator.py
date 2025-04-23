"""
Validation functions to ensure all required data points are collected.
"""
import json
from typing import Dict, Any, List, Optional
from logger_config import get_logger

logger = get_logger(__name__)


def validate_race_data(race_data: Dict[str, Any]) -> bool:
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
    
    all_complete = all(len(missing) == 0 for missing in missing_fields.values())
    
    if all_complete:
        logger.info("Validation successful! All required data points are present.")
        return True
    else:
        for category, fields in missing_fields.items():
            if fields:
                logger.warning(f"Category {category} missing fields: {', '.join(fields)}")
        return False


def validate_and_save_race_data(race_data: Dict[str, Any], output_filename: str) -> bool:
    """Validates race data and saves it to a JSON file."""
    is_valid = validate_race_data(race_data)
    
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
        }
        
        report_filename = f"validation_report_{race_data.get('race_id', 'unknown')}.json"
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(validation_report, f, ensure_ascii=False, indent=2)
        logger.info(f"Validation report saved to {report_filename}")
        
        return is_valid
    except Exception as e:
        logger.error(f"Error saving data: {e}", exc_info=True)
        return False
