"""
Advanced probability models for horse racing prediction.

This module implements sophisticated probability estimation techniques based on the strategic framework
in docs/main.md, including Bayesian estimation, conditional probabilities, and Monte Carlo simulation.
"""
import math
import random
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

from logger_config import get_logger

logger = get_logger(__name__)


class ProbabilityModels:
    """
    Implements advanced probability estimation models for horse racing.
    """

    def __init__(self, race_data: Dict[str, Any], factor_analysis: Dict[str, Dict[str, Any]]):
        """
        Initialize the probability models with race data and factor analysis results.
        
        Args:
            race_data: Dictionary containing race data collected from netkeiba.com
            factor_analysis: Dictionary containing advanced factor analysis results
        """
        self.race_data = race_data
        self.factor_analysis = factor_analysis
        self.horses = race_data.get("horses", [])
        self.horse_count = len(self.horses)
        
        self.win_probabilities = {}
        self.place_probabilities = {}
        self.show_probabilities = {}
        self.exacta_probabilities = {}
        self.quinella_probabilities = {}
        self.trifecta_probabilities = {}
        self.trio_probabilities = {}
        
        self.market_priors = self._calculate_market_priors()
        
        self.simulation_results = {}

    def _calculate_market_priors(self) -> Dict[str, float]:
        """
        Calculate prior probabilities based on market odds.
        
        Returns:
            Dictionary mapping horse numbers to prior probabilities.
        """
        priors = {}
        odds_data = self.race_data.get("live_odds_data", {})
        tan_odds = odds_data.get("tan_odds", {})
        
        if not tan_odds:
            for horse in self.horses:
                umaban = horse.get("umaban")
                if umaban:
                    priors[umaban] = 1.0 / self.horse_count
            return priors
        
        total_implied_prob = 0
        implied_probs = {}
        
        for umaban, odds_str in tan_odds.items():
            try:
                odds = float(odds_str)
                implied_prob = 1.0 / odds
                implied_probs[umaban] = implied_prob
                total_implied_prob += implied_prob
            except (ValueError, TypeError):
                logger.warning(f"Invalid odds format for horse {umaban}: {odds_str}")
        
        if total_implied_prob > 0:
            for umaban, prob in implied_probs.items():
                priors[umaban] = prob / total_implied_prob
        
        return priors

    def estimate_all_probabilities(self) -> Dict[str, Dict[str, float]]:
        """
        Estimate probabilities for all bet types using multiple models.
        
        Returns:
            Dictionary containing probability estimates for all bet types.
        """
        logger.info("Estimating probabilities using multiple models...")
        
        self.win_probabilities = self.bayesian_win_probability()
        
        self.place_probabilities = self.estimate_place_probabilities()
        
        self.show_probabilities = self.estimate_show_probabilities()
        
        self._run_monte_carlo_simulation(10000)
        
        self.exacta_probabilities = self.estimate_exacta_probabilities()
        self.quinella_probabilities = self.estimate_quinella_probabilities()
        self.trifecta_probabilities = self.estimate_trifecta_probabilities()
        self.trio_probabilities = self.estimate_trio_probabilities()
        
        all_probabilities = {
            "win": self.win_probabilities,
            "place": self.place_probabilities,
            "show": self.show_probabilities,
            "exacta": self.exacta_probabilities,
            "quinella": self.quinella_probabilities,
            "trifecta": self.trifecta_probabilities,
            "trio": self.trio_probabilities
        }
        
        return all_probabilities

    def bayesian_win_probability(self) -> Dict[str, float]:
        """
        Estimate win probabilities using Bayesian updating with factor analysis.
        
        Returns:
            Dictionary mapping horse numbers to win probabilities.
        """
        logger.info("Estimating win probabilities using Bayesian model...")
        
        posterior_probs = self.market_priors.copy()
        
        factor_weights = {
            "lap_time_analysis": 0.15,
            "pedigree_assessment": 0.10,
            "track_bias_impact": 0.15,
            "pace_adaptability": 0.20,
            "weather_impact": 0.10,
            "distance_aptitude": 0.15,
            "recovery_pattern": 0.05,
            "factor_scores": 0.10
        }
        
        for umaban, analysis in self.factor_analysis.items():
            if umaban not in posterior_probs:
                continue
                
            prior_prob = posterior_probs[umaban]
            likelihood_ratio = 1.0
            
            for factor, weight in factor_weights.items():
                if factor not in analysis:
                    continue
                    
                factor_data = analysis[factor]
                
                if factor == "lap_time_analysis":
                    if "finishing_kick_score" in factor_data:
                        score = factor_data["finishing_kick_score"] / 100.0
                        likelihood_ratio *= 1.0 + (score - 0.5) * weight * 2
                
                elif factor == "pedigree_assessment":
                    if "overall_score" in factor_data:
                        score = factor_data["overall_score"] / 100.0
                        likelihood_ratio *= 1.0 + (score - 0.5) * weight * 2
                
                elif factor == "track_bias_impact":
                    if "bias_score" in factor_data:
                        score = factor_data["bias_score"] / 100.0
                        likelihood_ratio *= 1.0 + (score - 0.5) * weight * 2
                
                elif factor == "pace_adaptability":
                    pace_scenario = "balanced_pace_score"  # Default
                    for race_horse in self.horses:
                        if race_horse.get("umaban") == umaban:
                            race_analysis = self.race_data.get("race_analysis", {})
                            if "pace_scenario" in race_analysis:
                                scenario = race_analysis["pace_scenario"]
                                if scenario == "fast":
                                    pace_scenario = "fast_pace_score"
                                elif scenario == "slow":
                                    pace_scenario = "slow_pace_score"
                            break
                    
                    if pace_scenario in factor_data:
                        score = factor_data[pace_scenario] / 100.0
                        likelihood_ratio *= 1.0 + (score - 0.5) * weight * 2
                
                elif factor == "weather_impact":
                    if "weather_advantage" in factor_data:
                        advantage = factor_data["weather_advantage"]
                        if advantage == "advantage":
                            likelihood_ratio *= 1.0 + weight
                        elif advantage == "disadvantage":
                            likelihood_ratio *= 1.0 - weight * 0.5
                
                elif factor == "distance_aptitude":
                    if "distance_advantage" in factor_data:
                        advantage = factor_data["distance_advantage"]
                        if advantage == "advantage":
                            likelihood_ratio *= 1.0 + weight
                        elif advantage == "disadvantage":
                            likelihood_ratio *= 1.0 - weight * 0.5
                
                elif factor == "factor_scores":
                    if "total_score" in factor_data:
                        score = factor_data["total_score"] / 100.0
                        likelihood_ratio *= 1.0 + (score - 0.5) * weight * 2
            
            posterior_probs[umaban] = prior_prob * likelihood_ratio
        
        total_posterior = sum(posterior_probs.values())
        if total_posterior > 0:
            for umaban in posterior_probs:
                posterior_probs[umaban] /= total_posterior
        
        return posterior_probs

    def estimate_place_probabilities(self) -> Dict[str, float]:
        """
        Estimate place probabilities based on win probabilities.
        
        Returns:
            Dictionary mapping horse numbers to place probabilities.
        """
        logger.info("Estimating place probabilities...")
        
        place_probs = {}
        
        for umaban, win_prob in self.win_probabilities.items():
            if win_prob > 0.3:  # Strong favorite
                place_probs[umaban] = min(0.8, win_prob * 1.5)
            elif win_prob > 0.15:  # Contender
                place_probs[umaban] = min(0.6, win_prob * 2.0)
            else:  # Longshot
                place_probs[umaban] = min(0.4, win_prob * 2.5)
        
        total_place_prob = sum(place_probs.values())
        if total_place_prob > 0:
            for umaban in place_probs:
                place_probs[umaban] /= total_place_prob
        
        return place_probs

    def estimate_show_probabilities(self) -> Dict[str, float]:
        """
        Estimate show probabilities (finish in top 3) based on win and place probabilities.
        
        Returns:
            Dictionary mapping horse numbers to show probabilities.
        """
        logger.info("Estimating show probabilities...")
        
        show_probs = {}
        
        for umaban, place_prob in self.place_probabilities.items():
            win_prob = self.win_probabilities.get(umaban, 0)
            
            if win_prob > 0.2:  # Strong favorite
                show_probs[umaban] = min(0.9, place_prob * 1.3)
            elif win_prob > 0.1:  # Contender
                show_probs[umaban] = min(0.7, place_prob * 1.5)
            else:  # Longshot
                show_probs[umaban] = min(0.5, place_prob * 1.8)
        
        total_show_prob = sum(show_probs.values())
        if total_show_prob > 0:
            for umaban in show_probs:
                show_probs[umaban] /= total_show_prob
        
        return show_probs

    def _run_monte_carlo_simulation(self, num_simulations: int = 10000) -> None:
        """
        Run Monte Carlo simulation to estimate exotic bet probabilities.
        
        Args:
            num_simulations: Number of race simulations to run
        """
        logger.info(f"Running Monte Carlo simulation with {num_simulations} iterations...")
        
        exacta_counts = {}
        quinella_counts = {}
        trifecta_counts = {}
        trio_counts = {}
        
        horse_numbers = list(self.win_probabilities.keys())
        
        for _ in range(num_simulations):
            horse_values = {}
            for umaban in horse_numbers:
                win_prob = self.win_probabilities.get(umaban, 0.001)
                
                lambda_param = -math.log(win_prob) * 5
                random_value = random.expovariate(lambda_param)
                
                if umaban in self.factor_analysis:
                    analysis = self.factor_analysis[umaban]
                    
                    pace_adaptability = analysis.get("pace_adaptability", {})
                    race_analysis = self.race_data.get("race_analysis", {})
                    pace_scenario = race_analysis.get("pace_scenario", "balanced")
                    
                    if pace_scenario == "fast" and "fast_pace_score" in pace_adaptability:
                        score = pace_adaptability["fast_pace_score"] / 100.0
                        random_value *= 1.0 - (score - 0.5) * 0.3
                    elif pace_scenario == "slow" and "slow_pace_score" in pace_adaptability:
                        score = pace_adaptability["slow_pace_score"] / 100.0
                        random_value *= 1.0 - (score - 0.5) * 0.3
                    
                    track_bias = analysis.get("track_bias_impact", {})
                    if "bias_advantage" in track_bias:
                        advantage = track_bias["bias_advantage"]
                        if advantage == "advantage":
                            random_value *= 0.9
                        elif advantage == "disadvantage":
                            random_value *= 1.1
                
                horse_values[umaban] = random_value
            
            sorted_horses = sorted(horse_values.items(), key=lambda x: x[1])
            
            if len(sorted_horses) >= 3:
                first = sorted_horses[0][0]
                second = sorted_horses[1][0]
                third = sorted_horses[2][0]
                
                exacta_key = f"{first}-{second}"
                exacta_counts[exacta_key] = exacta_counts.get(exacta_key, 0) + 1
                
                quinella_key = "-".join(sorted([first, second]))
                quinella_counts[quinella_key] = quinella_counts.get(quinella_key, 0) + 1
                
                trifecta_key = f"{first}-{second}-{third}"
                trifecta_counts[trifecta_key] = trifecta_counts.get(trifecta_key, 0) + 1
                
                trio_key = "-".join(sorted([first, second, third]))
                trio_counts[trio_key] = trio_counts.get(trio_key, 0) + 1
        
        self.simulation_results = {
            "exacta_counts": exacta_counts,
            "quinella_counts": quinella_counts,
            "trifecta_counts": trifecta_counts,
            "trio_counts": trio_counts,
            "num_simulations": num_simulations
        }
        
        logger.info(f"Monte Carlo simulation complete with {len(exacta_counts)} exacta, "
                   f"{len(quinella_counts)} quinella, {len(trifecta_counts)} trifecta, "
                   f"and {len(trio_counts)} trio combinations")

    def estimate_exacta_probabilities(self) -> Dict[str, float]:
        """
        Estimate exacta probabilities based on simulation results.
        
        Returns:
            Dictionary mapping horse number combinations to exacta probabilities.
        """
        exacta_probs = {}
        exacta_counts = self.simulation_results.get("exacta_counts", {})
        num_simulations = self.simulation_results.get("num_simulations", 1)
        
        for combo, count in exacta_counts.items():
            exacta_probs[combo] = count / num_simulations
        
        return exacta_probs

    def estimate_quinella_probabilities(self) -> Dict[str, float]:
        """
        Estimate quinella probabilities based on simulation results.
        
        Returns:
            Dictionary mapping horse number combinations to quinella probabilities.
        """
        quinella_probs = {}
        quinella_counts = self.simulation_results.get("quinella_counts", {})
        num_simulations = self.simulation_results.get("num_simulations", 1)
        
        for combo, count in quinella_counts.items():
            quinella_probs[combo] = count / num_simulations
        
        return quinella_probs

    def estimate_trifecta_probabilities(self) -> Dict[str, float]:
        """
        Estimate trifecta probabilities based on simulation results.
        
        Returns:
            Dictionary mapping horse number combinations to trifecta probabilities.
        """
        trifecta_probs = {}
        trifecta_counts = self.simulation_results.get("trifecta_counts", {})
        num_simulations = self.simulation_results.get("num_simulations", 1)
        
        for combo, count in trifecta_counts.items():
            trifecta_probs[combo] = count / num_simulations
        
        return trifecta_probs

    def estimate_trio_probabilities(self) -> Dict[str, float]:
        """
        Estimate trio probabilities based on simulation results.
        
        Returns:
            Dictionary mapping horse number combinations to trio probabilities.
        """
        trio_probs = {}
        trio_counts = self.simulation_results.get("trio_counts", {})
        num_simulations = self.simulation_results.get("num_simulations", 1)
        
        for combo, count in trio_counts.items():
            trio_probs[combo] = count / num_simulations
        
        return trio_probs

    def conditional_probability(self, condition_func, target_func) -> float:
        """
        Calculate conditional probability P(target|condition).
        
        Args:
            condition_func: Function that takes a race result and returns True if condition is met
            target_func: Function that takes a race result and returns True if target is met
            
        Returns:
            Conditional probability
        """
        condition_count = 0
        target_and_condition_count = 0
        
        for _ in range(1000):  # Use a smaller number of simulations for efficiency
            result = self._simulate_race()
            
            if condition_func(result):
                condition_count += 1
                if target_func(result):
                    target_and_condition_count += 1
        
        if condition_count == 0:
            return 0.0
        
        return target_and_condition_count / condition_count

    def _simulate_race(self) -> List[str]:
        """
        Simulate a single race and return the finishing order.
        
        Returns:
            List of horse numbers in finishing order
        """
        horse_values = {}
        for umaban, win_prob in self.win_probabilities.items():
            lambda_param = -math.log(win_prob) * 5
            random_value = random.expovariate(lambda_param)
            horse_values[umaban] = random_value
        
        sorted_horses = sorted(horse_values.items(), key=lambda x: x[1])
        
        return [horse[0] for horse in sorted_horses]
