"""
Betting analyzer module for horse racing prediction.

This module implements the betting analysis logic based on the strategic framework
in docs/main.md and the workflow in docs/workflow.md.
"""
import json
import logging
import math
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

from logger_config import get_logger

logger = get_logger(__name__)

MIN_EXPECTED_VALUE = 1.1  # Minimum expected value to consider a bet (10% above breakeven)
DEFAULT_BET_AMOUNT = 100  # Default bet amount in yen
MAX_BET_AMOUNT = 300  # Maximum bet amount in yen
BREAKEVEN_THRESHOLD = {
    "tan": 1.25,  # Approximate breakeven for win bets (1 / 0.8 payout rate)
    "fuku": 1.25,  # Approximate breakeven for place bets
    "umaren": 1.29,  # Approximate breakeven for quinella bets
    "umatan": 1.29,  # Approximate breakeven for exacta bets
    "wide": 1.29,  # Approximate breakeven for quinella place bets
    "sanrentan": 1.33,  # Approximate breakeven for trifecta bets
    "sanrenpuku": 1.33,  # Approximate breakeven for trio bets
}


class BettingAnalyzer:
    """
    Analyzes race data and generates betting recommendations based on value betting principles.
    """

    def __init__(self, race_data: Dict[str, Any]):
        """
        Initialize the betting analyzer with race data.
        
        Args:
            race_data: Dictionary containing race data collected from netkeiba.com
        """
        self.race_data = race_data
        self.race_id = race_data.get("race_id", "unknown")
        self.race_name = race_data.get("race_name", "unknown")
        self.horses = race_data.get("horses", [])
        self.odds_data = race_data.get("live_odds_data", {})
        self.payouts = race_data.get("payouts", {})
        self.course_details = race_data.get("course_details", {})
        self.track_condition = race_data.get("track_condition", "unknown")
        self.weather = race_data.get("weather", "unknown")
        self.distance_meters = race_data.get("distance_meters", 0)
        self.course_type = race_data.get("course_type", "unknown")
        
        self.win_probabilities = {}
        self.place_probabilities = {}
        
        self.expected_values = {
            "tan": {},
            "fuku": {},
            "umaren": {},
            "umatan": {},
            "wide": {},
            "sanrentan": {},
            "sanrenpuku": {},
        }
        
        self.recommendations = []

    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze race data and generate betting recommendations.
        
        Returns:
            List of betting recommendations, including bet type, horses, amount, and expected value.
        """
        logger.info(f"Analyzing race {self.race_id}: {self.race_name}")
        
        self._analyze_race_conditions()
        self._analyze_horses()
        self._estimate_probabilities()
        
        self._calculate_expected_values()
        self._make_betting_decisions()
        
        return self.recommendations

    def _analyze_race_conditions(self) -> None:
        """
        Analyze race conditions including track, weather, and course characteristics.
        """
        logger.info("Analyzing race conditions...")
        
        track_bias = None
        if self.course_details and "track_bias" in self.course_details:
            for bias_data in self.course_details["track_bias"]:
                if (bias_data.get("track_type") == self.course_type and 
                    str(self.distance_meters) in bias_data.get("distance", "")):
                    track_bias = bias_data.get("bias_description")
                    break
        
        logger.info(f"Track condition: {self.track_condition}, Weather: {self.weather}")
        if track_bias:
            logger.info(f"Track bias: {track_bias}")
        
        self.track_analysis = {
            "track_condition": self.track_condition,
            "weather": self.weather,
            "track_bias": track_bias
        }

    def _analyze_horses(self) -> None:
        """
        Analyze each horse's data including past performance, speed figures, and jockey/trainer stats.
        """
        logger.info(f"Analyzing {len(self.horses)} horses...")
        
        self.horse_analysis = {}
        
        for horse in self.horses:
            umaban = horse.get("umaban")
            if not umaban:
                continue
                
            horse_name = horse.get("horse_name", f"Horse #{umaban}")
            logger.info(f"Analyzing horse {umaban}: {horse_name}")
            
            analysis = {
                "umaban": umaban,
                "horse_name": horse_name,
                "speed_score": 0,
                "form_score": 0,
                "jockey_score": 0,
                "trainer_score": 0,
                "pedigree_score": 0,
                "condition_score": 0,
                "total_score": 0,
            }
            
            speed_figures = self.race_data.get("speed_figures", {}).get("figures", {}).get(umaban, {})
            if speed_figures:
                speed_index = speed_figures.get("speed_index")
                if speed_index and isinstance(speed_index, str) and speed_index.isdigit():
                    analysis["speed_score"] = int(speed_index)
            
            past_results = horse.get("full_results_data", {}).get("results", [])
            if past_results:
                recent_results = past_results[:3]
                positions = []
                for result in recent_results:
                    position = result.get("position")
                    if position and position.isdigit():
                        positions.append(int(position))
                
                if positions:
                    avg_position = sum(positions) / len(positions)
                    form_score = max(0, 100 - (avg_position - 1) * 6)
                    analysis["form_score"] = form_score
            
            jockey_profile = horse.get("jockey_profile", {})
            if jockey_profile:
                win_rate = jockey_profile.get("win_rate")
                if win_rate and isinstance(win_rate, str) and win_rate.endswith("%"):
                    try:
                        win_rate_value = float(win_rate.rstrip("%"))
                        jockey_score = min(100, win_rate_value * 3.33)
                        analysis["jockey_score"] = jockey_score
                    except ValueError:
                        pass
            
            trainer_profile = horse.get("trainer_profile", {})
            if trainer_profile:
                win_rate = trainer_profile.get("win_rate")
                if win_rate and isinstance(win_rate, str) and win_rate.endswith("%"):
                    try:
                        win_rate_value = float(win_rate.rstrip("%"))
                        trainer_score = min(100, win_rate_value * 5)
                        analysis["trainer_score"] = trainer_score
                    except ValueError:
                        pass
            
            pedigree_data = horse.get("pedigree_data", {})
            if pedigree_data:
                analysis["pedigree_score"] = 50
                
                sire = pedigree_data.get("sire", {}).get("name", "")
                dam_sire = pedigree_data.get("dam_sire", {}).get("name", "")
                
                if sire or dam_sire:
                    analysis["pedigree_score"] += 10
            
            paddock_info = self.race_data.get("paddock_info", {}).get("paddock_observations", {}).get(umaban, {})
            if paddock_info:
                analysis["condition_score"] = 50
                
                condition_text = paddock_info.get("condition_text", "")
                if "良好" in condition_text or "絶好" in condition_text:
                    analysis["condition_score"] += 30
                elif "不安" in condition_text or "悪い" in condition_text:
                    analysis["condition_score"] -= 30
            
            weights = {
                "speed_score": 0.3,
                "form_score": 0.25,
                "jockey_score": 0.15,
                "trainer_score": 0.1,
                "pedigree_score": 0.1,
                "condition_score": 0.1,
            }
            
            total_score = 0
            for key, weight in weights.items():
                total_score += analysis[key] * weight
            
            analysis["total_score"] = total_score
            self.horse_analysis[umaban] = analysis
            
            logger.info(f"Horse {umaban} analysis complete. Total score: {total_score:.2f}")

    def _estimate_probabilities(self) -> None:
        """
        Estimate win and place probabilities for each horse based on analysis.
        """
        logger.info("Estimating probabilities...")
        
        total_score_sum = sum(analysis["total_score"] for analysis in self.horse_analysis.values())
        
        if total_score_sum > 0:
            for umaban, analysis in self.horse_analysis.items():
                raw_probability = analysis["total_score"] / total_score_sum
                
                adjusted_probability = raw_probability
                
                self.win_probabilities[umaban] = adjusted_probability
                
                self.place_probabilities[umaban] = min(0.95, adjusted_probability * 2.5)
                
                logger.info(f"Horse {umaban}: Win probability = {adjusted_probability:.2%}")
        else:
            logger.warning("Could not estimate probabilities: total score sum is zero")

    def _calculate_expected_values(self) -> None:
        """
        Calculate expected values for different bet types based on probabilities and odds.
        """
        logger.info("Calculating expected values...")
        
        tan_odds = self.odds_data.get("tan_odds", {})
        for umaban, probability in self.win_probabilities.items():
            if umaban in tan_odds:
                try:
                    odds = float(tan_odds[umaban])
                    expected_value = probability * odds
                    self.expected_values["tan"][umaban] = expected_value
                    logger.info(f"Horse {umaban}: Win EV = {expected_value:.2f} (Prob: {probability:.2%}, Odds: {odds})")
                except (ValueError, TypeError):
                    logger.warning(f"Could not calculate win EV for horse {umaban}: invalid odds {tan_odds[umaban]}")
        
        fuku_odds = self.odds_data.get("fuku_odds", {})
        for umaban, probability in self.place_probabilities.items():
            if umaban in fuku_odds:
                try:
                    odds_range = fuku_odds[umaban].split("-")
                    if len(odds_range) == 2:
                        min_odds = float(odds_range[0])
                        max_odds = float(odds_range[1])
                        expected_value = probability * min_odds
                        self.expected_values["fuku"][umaban] = expected_value
                        logger.info(f"Horse {umaban}: Place EV = {expected_value:.2f} (Prob: {probability:.2%}, Odds: {min_odds}-{max_odds})")
                except (ValueError, TypeError, IndexError):
                    logger.warning(f"Could not calculate place EV for horse {umaban}: invalid odds {fuku_odds[umaban]}")
        
        umaren_odds = self.odds_data.get("umaren_odds", {})
        for combo, odds_str in umaren_odds.items():
            try:
                horses = combo.split("-")
                if len(horses) == 2:
                    horse1, horse2 = horses
                    if horse1 in self.win_probabilities and horse2 in self.win_probabilities:
                        p_a = self.win_probabilities[horse1]
                        p_b = self.win_probabilities[horse2]
                        
                        p_quinella = 2 * p_a * p_b
                        
                        odds = float(odds_str)
                        expected_value = p_quinella * odds
                        self.expected_values["umaren"][combo] = expected_value
                        logger.info(f"Quinella {combo}: EV = {expected_value:.2f} (Prob: {p_quinella:.2%}, Odds: {odds})")
            except (ValueError, TypeError, IndexError):
                logger.warning(f"Could not calculate quinella EV for combo {combo}: invalid odds or horses")
        

    def _make_betting_decisions(self) -> None:
        """
        Make betting decisions based on expected values and betting strategy.
        """
        logger.info("Making betting decisions...")
        
        best_bets = {}
        
        best_tan_ev = 0
        best_tan_horse = None
        for umaban, ev in self.expected_values["tan"].items():
            if ev > best_tan_ev and ev > BREAKEVEN_THRESHOLD["tan"] * MIN_EXPECTED_VALUE:
                best_tan_ev = ev
                best_tan_horse = umaban
        
        if best_tan_horse:
            best_bets["tan"] = {
                "horse": best_tan_horse,
                "ev": best_tan_ev,
                "odds": self.odds_data.get("tan_odds", {}).get(best_tan_horse, "N/A")
            }
        
        best_fuku_ev = 0
        best_fuku_horse = None
        for umaban, ev in self.expected_values["fuku"].items():
            if ev > best_fuku_ev and ev > BREAKEVEN_THRESHOLD["fuku"] * MIN_EXPECTED_VALUE:
                best_fuku_ev = ev
                best_fuku_horse = umaban
        
        if best_fuku_horse:
            best_bets["fuku"] = {
                "horse": best_fuku_horse,
                "ev": best_fuku_ev,
                "odds": self.odds_data.get("fuku_odds", {}).get(best_fuku_horse, "N/A")
            }
        
        best_umaren_ev = 0
        best_umaren_combo = None
        for combo, ev in self.expected_values["umaren"].items():
            if ev > best_umaren_ev and ev > BREAKEVEN_THRESHOLD["umaren"] * MIN_EXPECTED_VALUE:
                best_umaren_ev = ev
                best_umaren_combo = combo
        
        if best_umaren_combo:
            best_bets["umaren"] = {
                "horses": best_umaren_combo,
                "ev": best_umaren_ev,
                "odds": self.odds_data.get("umaren_odds", {}).get(best_umaren_combo, "N/A")
            }
        
        if not best_bets:
            self.recommendations.append({
                "bet_type": "no_bet",
                "reason": "No value bets found with expected value above threshold",
                "threshold": MIN_EXPECTED_VALUE
            })
            logger.info("Recommendation: DO NOT BET - No value bets found")
            return
        
        best_bet_type = max(best_bets.keys(), key=lambda k: best_bets[k]["ev"])
        best_bet = best_bets[best_bet_type]
        
        if best_bet_type == "tan":
            umaban = best_bet["horse"]
            probability = self.win_probabilities.get(umaban, 0)
            odds = float(best_bet["odds"])
            edge = best_bet["ev"] - 1  # How much above breakeven
            
            kelly_fraction = max(0, edge / (odds - 1))
            
            conservative_kelly = kelly_fraction / 4
            
            bet_amount = min(MAX_BET_AMOUNT, math.ceil(DEFAULT_BET_AMOUNT * conservative_kelly / 0.1) * 100)
            
            bet_amount = max(100, bet_amount)
            
            horse_name = next((h["horse_name"] for h in self.horses if h.get("umaban") == umaban), f"Horse #{umaban}")
            self.recommendations.append({
                "bet_type": "tan",
                "horse": umaban,
                "horse_name": horse_name,
                "odds": best_bet["odds"],
                "expected_value": best_bet["ev"],
                "probability": f"{probability:.2%}",
                "amount": bet_amount,
                "reason": f"Best value bet with EV {best_bet['ev']:.2f} (threshold: {MIN_EXPECTED_VALUE})"
            })
            
            logger.info(f"Recommendation: BET {bet_amount}¥ on WIN {umaban} ({horse_name}) at odds {best_bet['odds']} (EV: {best_bet['ev']:.2f})")
        
        elif best_bet_type == "fuku":
            umaban = best_bet["horse"]
            probability = self.place_probabilities.get(umaban, 0)
            
            odds_range = str(best_bet["odds"]).split("-")
            if len(odds_range) == 2:
                min_odds = float(odds_range[0])
                edge = best_bet["ev"] - 1
                
                kelly_fraction = max(0, edge / (min_odds - 1))
                
                conservative_kelly = kelly_fraction / 4
                
                bet_amount = min(MAX_BET_AMOUNT, math.ceil(DEFAULT_BET_AMOUNT * conservative_kelly / 0.1) * 100)
                
                bet_amount = max(100, bet_amount)
                
                horse_name = next((h["horse_name"] for h in self.horses if h.get("umaban") == umaban), f"Horse #{umaban}")
                self.recommendations.append({
                    "bet_type": "fuku",
                    "horse": umaban,
                    "horse_name": horse_name,
                    "odds": best_bet["odds"],
                    "expected_value": best_bet["ev"],
                    "probability": f"{probability:.2%}",
                    "amount": bet_amount,
                    "reason": f"Best value bet with EV {best_bet['ev']:.2f} (threshold: {MIN_EXPECTED_VALUE})"
                })
                
                logger.info(f"Recommendation: BET {bet_amount}¥ on PLACE {umaban} ({horse_name}) at odds {best_bet['odds']} (EV: {best_bet['ev']:.2f})")
        
        elif best_bet_type == "umaren":
            horses = best_bet["horses"].split("-")
            if len(horses) == 2:
                horse1, horse2 = horses
                
                bet_amount = 100  # Fixed amount for simplicity
                
                horse1_name = next((h["horse_name"] for h in self.horses if h.get("umaban") == horse1), f"Horse #{horse1}")
                horse2_name = next((h["horse_name"] for h in self.horses if h.get("umaban") == horse2), f"Horse #{horse2}")
                
                self.recommendations.append({
                    "bet_type": "umaren",
                    "horses": [horse1, horse2],
                    "horse_names": [horse1_name, horse2_name],
                    "odds": best_bet["odds"],
                    "expected_value": best_bet["ev"],
                    "amount": bet_amount,
                    "reason": f"Best value bet with EV {best_bet['ev']:.2f} (threshold: {MIN_EXPECTED_VALUE})"
                })
                
                logger.info(f"Recommendation: BET {bet_amount}¥ on QUINELLA {horse1}-{horse2} ({horse1_name}-{horse2_name}) at odds {best_bet['odds']} (EV: {best_bet['ev']:.2f})")


def analyze_race(race_data_file: str) -> List[Dict[str, Any]]:
    """
    Analyze a race from a race data file and generate betting recommendations.
    
    Args:
        race_data_file: Path to the race data JSON file
        
    Returns:
        List of betting recommendations
    """
    try:
        with open(race_data_file, 'r', encoding='utf-8') as f:
            race_data = json.load(f)
        
        analyzer = BettingAnalyzer(race_data)
        recommendations = analyzer.analyze()
        return recommendations
    
    except FileNotFoundError:
        logger.error(f"Race data file not found: {race_data_file}")
        return [{"bet_type": "error", "reason": f"Race data file not found: {race_data_file}"}]
    
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in race data file: {race_data_file}")
        return [{"bet_type": "error", "reason": f"Invalid JSON in race data file: {race_data_file}"}]
    
    except Exception as e:
        logger.error(f"Error analyzing race data: {e}", exc_info=True)
        return [{"bet_type": "error", "reason": f"Error analyzing race data: {str(e)}"}]
