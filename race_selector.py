"""
Race selection module for horse racing prediction.

This module implements race selection functionality based on the strategic framework
in docs/main.md, helping identify races with the highest potential for value betting.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from logger_config import get_logger

logger = get_logger(__name__)


class RaceSelector:
    """
    Implements race selection functionality to identify promising betting opportunities.
    """

    def __init__(self, race_database: Optional[Dict[str, Any]] = None):
        """
        Initialize the race selector with optional race database.
        
        Args:
            race_database: Dictionary mapping race IDs to race data
        """
        self.race_database = race_database or {}
        self.selection_criteria = {
            "field_size": {
                "min": 6,
                "max": 16,
                "weight": 0.1
            },
            "race_class": {
                "preferred": ["G1", "G2", "G3", "OP", "3勝"],
                "weight": 0.15
            },
            "track_condition": {
                "preferred": ["良", "稍重"],
                "weight": 0.1
            },
            "market_inefficiency": {
                "weight": 0.25
            },
            "data_availability": {
                "weight": 0.2
            },
            "historical_edge": {
                "weight": 0.2
            }
        }
        
        self.race_scores = {}
        logger.info("Initialized race selector with default selection criteria")

    def set_selection_criteria(self, criteria: Dict[str, Any]) -> None:
        """
        Update race selection criteria.
        
        Args:
            criteria: Dictionary containing selection criteria parameters
        """
        self.selection_criteria.update(criteria)
        logger.info(f"Updated selection criteria: {criteria}")

    def score_races(self, races: Dict[str, Any]) -> Dict[str, float]:
        """
        Score races based on selection criteria to identify promising opportunities.
        
        Args:
            races: Dictionary mapping race IDs to race data
            
        Returns:
            Dictionary mapping race IDs to opportunity scores (0-100)
        """
        logger.info(f"Scoring {len(races)} races for betting opportunities...")
        
        self.race_scores = {}
        
        for race_id, race_data in races.items():
            score = self._calculate_race_score(race_data)
            self.race_scores[race_id] = score
            
            race_name = race_data.get("race_name", "Unknown")
            logger.info(f"Race {race_id} ({race_name}): Score {score:.1f}/100")
        
        return self.race_scores

    def _calculate_race_score(self, race_data: Dict[str, Any]) -> float:
        """
        Calculate opportunity score for a single race.
        
        Args:
            race_data: Dictionary containing race data
            
        Returns:
            Opportunity score (0-100)
        """
        score_components = {}
        
        field_size = len(race_data.get("horses", []))
        min_size = self.selection_criteria["field_size"]["min"]
        max_size = self.selection_criteria["field_size"]["max"]
        
        if field_size < min_size:
            field_size_score = 30  # Too few horses
        elif field_size > max_size:
            field_size_score = 50  # Too many horses
        else:
            field_size_score = 100 - abs((field_size - (min_size + max_size) / 2) / ((max_size - min_size) / 2)) * 50
        
        score_components["field_size"] = field_size_score
        
        race_class = race_data.get("race_class", "")
        preferred_classes = self.selection_criteria["race_class"]["preferred"]
        
        if any(cls in race_class for cls in preferred_classes):
            class_score = 100
        else:
            class_score = 50
        
        score_components["race_class"] = class_score
        
        track_condition = race_data.get("track_condition", "")
        preferred_conditions = self.selection_criteria["track_condition"]["preferred"]
        
        if track_condition in preferred_conditions:
            condition_score = 100
        else:
            condition_score = 60
        
        score_components["track_condition"] = condition_score
        
        market_score = self._calculate_market_inefficiency_score(race_data)
        score_components["market_inefficiency"] = market_score
        
        data_score = self._calculate_data_availability_score(race_data)
        score_components["data_availability"] = data_score
        
        edge_score = self._calculate_historical_edge_score(race_data)
        score_components["historical_edge"] = edge_score
        
        weighted_score = 0
        for component, score in score_components.items():
            weight = self.selection_criteria.get(component, {}).get("weight", 0)
            weighted_score += score * weight
        
        return weighted_score

    def _calculate_market_inefficiency_score(self, race_data: Dict[str, Any]) -> float:
        """
        Calculate market inefficiency score based on odds distribution.
        
        Args:
            race_data: Dictionary containing race data
            
        Returns:
            Market inefficiency score (0-100)
        """
        odds_data = race_data.get("live_odds_data", {})
        tan_odds = odds_data.get("tan_odds", {})
        
        if not tan_odds:
            return 50  # Neutral score if no odds data
        
        implied_probs = {}
        total_implied_prob = 0
        
        for umaban, odds_str in tan_odds.items():
            try:
                odds = float(odds_str)
                implied_prob = 1.0 / odds
                implied_probs[umaban] = implied_prob
                total_implied_prob += implied_prob
            except (ValueError, TypeError):
                pass
        
        if total_implied_prob == 0:
            return 50
        
        overround = total_implied_prob - 1.0
        
        if overround > 0.3:  # Very high overround
            return 90
        elif overround > 0.2:
            return 80
        elif overround > 0.15:
            return 70
        else:
            return 50
        

    def _calculate_data_availability_score(self, race_data: Dict[str, Any]) -> float:
        """
        Calculate data availability score based on completeness of race data.
        
        Args:
            race_data: Dictionary containing race data
            
        Returns:
            Data availability score (0-100)
        """
        score = 0
        total_checks = 6
        
        if all(key in race_data for key in ["race_name", "venue_name", "course_type", "distance_meters"]):
            score += 1
        
        horses = race_data.get("horses", [])
        if horses and all("horse_name" in horse and "pedigree_data" in horse for horse in horses):
            score += 1
        
        if horses and all("training_data" in horse and horse["training_data"] for horse in horses):
            score += 1
        
        if horses and all("jockey_profile" in horse and "trainer_profile" in horse for horse in horses):
            score += 1
        
        if "live_odds_data" in race_data and race_data["live_odds_data"]:
            score += 1
        
        if "speed_figures" in race_data and race_data["speed_figures"]:
            score += 1
        
        return (score / total_checks) * 100

    def _calculate_historical_edge_score(self, race_data: Dict[str, Any]) -> float:
        """
        Calculate historical edge score based on past performance in similar races.
        
        Args:
            race_data: Dictionary containing race data
            
        Returns:
            Historical edge score (0-100)
        """
        
        venue = race_data.get("venue_name", "")
        distance = race_data.get("distance_meters", 0)
        course_type = race_data.get("course_type", "")
        
        
        return 60

    def get_recommended_races(self, min_score: float = 70.0, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recommended races based on opportunity scores.
        
        Args:
            min_score: Minimum opportunity score to include
            limit: Maximum number of races to recommend
            
        Returns:
            List of recommended races with scores
        """
        if not self.race_scores:
            logger.warning("No races have been scored yet")
            return []
        
        sorted_races = sorted(self.race_scores.items(), key=lambda x: x[1], reverse=True)
        
        recommended = [
            {
                "race_id": race_id,
                "score": score,
                "race_name": self.race_database.get(race_id, {}).get("race_name", "Unknown"),
                "venue": self.race_database.get(race_id, {}).get("venue_name", "Unknown"),
                "date": self.race_database.get(race_id, {}).get("date", "Unknown"),
            }
            for race_id, score in sorted_races
            if score >= min_score and race_id in self.race_database
        ]
        
        return recommended[:limit]

    def filter_races_by_criteria(self, races: Dict[str, Any], criteria: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter races based on specific criteria.
        
        Args:
            races: Dictionary mapping race IDs to race data
            criteria: Dictionary containing filter criteria
            
        Returns:
            Dictionary of races that match the criteria
        """
        filtered_races = {}
        
        for race_id, race_data in races.items():
            if self._race_matches_criteria(race_data, criteria):
                filtered_races[race_id] = race_data
        
        logger.info(f"Filtered {len(races)} races down to {len(filtered_races)} based on criteria")
        return filtered_races

    def _race_matches_criteria(self, race_data: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """
        Check if a race matches the specified criteria.
        
        Args:
            race_data: Dictionary containing race data
            criteria: Dictionary containing filter criteria
            
        Returns:
            True if the race matches all criteria, False otherwise
        """
        if "venue" in criteria and race_data.get("venue_name") != criteria["venue"]:
            return False
        
        if "race_class" in criteria:
            race_class = race_data.get("race_class", "")
            if not any(cls in race_class for cls in criteria["race_class"]):
                return False
        
        if "min_distance" in criteria:
            distance = race_data.get("distance_meters", 0)
            if distance < criteria["min_distance"]:
                return False
        
        if "max_distance" in criteria:
            distance = race_data.get("distance_meters", 0)
            if distance > criteria["max_distance"]:
                return False
        
        if "course_type" in criteria and race_data.get("course_type") != criteria["course_type"]:
            return False
        
        if "min_field_size" in criteria:
            field_size = len(race_data.get("horses", []))
            if field_size < criteria["min_field_size"]:
                return False
        
        if "max_field_size" in criteria:
            field_size = len(race_data.get("horses", []))
            if field_size > criteria["max_field_size"]:
                return False
        
        return True

    def get_upcoming_races(self, days_ahead: int = 7) -> List[str]:
        """
        Get list of upcoming race IDs within the specified time frame.
        
        Args:
            days_ahead: Number of days ahead to look for races
            
        Returns:
            List of upcoming race IDs
        """
        upcoming_races = []
        today = datetime.now().date()
        
        for race_id, race_data in self.race_database.items():
            race_date_str = race_data.get("date")
            if not race_date_str:
                continue
            
            try:
                race_date = None
                date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]
                
                for fmt in date_formats:
                    try:
                        race_date = datetime.strptime(race_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                
                if race_date and today <= race_date <= today + timedelta(days=days_ahead):
                    upcoming_races.append(race_id)
            except Exception as e:
                logger.warning(f"Error parsing date for race {race_id}: {e}")
        
        logger.info(f"Found {len(upcoming_races)} upcoming races in the next {days_ahead} days")
        return upcoming_races
