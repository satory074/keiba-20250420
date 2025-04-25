"""
Advanced probability models for horse racing prediction.

This module implements sophisticated probability estimation techniques based on the strategic framework
in docs/main.md, including Bayesian estimation, conditional probabilities, and Monte Carlo simulation.
リアルタイムデータ更新に対応し、オッズや馬場状態の変化に応じて予測を更新します。
"""
import math
import random
import numpy as np
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set

from logger_config import get_logger

logger = get_logger(__name__)


class ProbabilityModels:
    """
    Implements advanced probability estimation models for horse racing.
    リアルタイムデータ更新に対応した競馬予測モデル。
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
        
        self.last_update_time = time.time()
        self.last_full_recalculation_time = time.time()
        self.cached_probabilities = {}
        self.previous_odds_data = self._extract_odds_data()
        self.previous_track_condition = self._extract_track_condition()
        self.previous_weather_data = self._extract_weather_data()
        
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
        
    def _extract_odds_data(self) -> Dict[str, Any]:
        """
        現在のオッズデータを抽出します。
        
        Returns:
            オッズデータを含む辞書
        """
        odds_data = {}
        
        if "live_odds_data" in self.race_data:
            odds_data = self.race_data["live_odds_data"]
        elif "odds_data" in self.race_data:
            odds_data = self.race_data["odds_data"]
            
        return odds_data
        
    def _extract_track_condition(self) -> Dict[str, Any]:
        """
        現在の馬場状態を抽出します。
        
        Returns:
            馬場状態を含む辞書
        """
        track_condition = {}
        
        if "track_condition" in self.race_data:
            track_condition = self.race_data["track_condition"]
            
        return track_condition
        
    def _extract_weather_data(self) -> Dict[str, Any]:
        """
        現在の気象データを抽出します。
        
        Returns:
            気象データを含む辞書
        """
        weather_data = {}
        
        if "weather_data" in self.race_data:
            weather_data = self.race_data["weather_data"]
        elif "weather" in self.race_data:
            weather_data = {"weather": self.race_data["weather"]}
            
        return weather_data
        
    def update_race_data(self, new_data: Dict[str, Any]) -> None:
        """
        レースデータを更新し、必要に応じて確率を再計算します。
        
        Args:
            new_data: 新しいレースデータ（部分的な更新も可能）
        """
        logger.info("レースデータを更新します")
        
        previous_odds_data = self.previous_odds_data
        previous_track_condition = self.previous_track_condition
        previous_weather_data = self.previous_weather_data
        
        if isinstance(new_data, dict):
            self.race_data.update(new_data)
        else:
            self.race_data = new_data
            
        if "horses" in new_data:
            self.horses = new_data["horses"]
            self.horse_count = len(self.horses)
            
        current_odds_data = self._extract_odds_data()
        current_track_condition = self._extract_track_condition()
        current_weather_data = self._extract_weather_data()
        
        self.previous_odds_data = current_odds_data
        self.previous_track_condition = current_track_condition
        self.previous_weather_data = current_weather_data
        
        recalculation_needed = self._check_recalculation_needed(
            previous_odds_data, current_odds_data,
            previous_track_condition, current_track_condition,
            previous_weather_data, current_weather_data
        )
        
        if recalculation_needed:
            logger.info("データ変更により確率の再計算が必要です")
            
            self.market_priors = self._calculate_market_priors()
            
            self.cached_probabilities = {}
            
            self.estimate_all_probabilities()
            
            self.last_full_recalculation_time = time.time()
        else:
            logger.info("データ変更は小さいため、確率の再計算は不要です")
            
        self.last_update_time = time.time()
        
    def _check_recalculation_needed(
        self,
        previous_odds_data: Dict[str, Any],
        current_odds_data: Dict[str, Any],
        previous_track_condition: Dict[str, Any],
        current_track_condition: Dict[str, Any],
        previous_weather_data: Dict[str, Any],
        current_weather_data: Dict[str, Any]
    ) -> bool:
        """
        確率の再計算が必要かどうかを判断します。
        
        Args:
            previous_odds_data: 前回のオッズデータ
            current_odds_data: 現在のオッズデータ
            previous_track_condition: 前回の馬場状態
            current_track_condition: 現在の馬場状態
            previous_weather_data: 前回の気象データ
            current_weather_data: 現在の気象データ
            
        Returns:
            再計算が必要な場合はTrue、そうでない場合はFalse
        """
        if time.time() - self.last_full_recalculation_time > 1800:
            logger.info("前回の完全再計算から30分経過したため、再計算を実行します")
            return True
            
        if previous_track_condition.get("condition") != current_track_condition.get("condition"):
            logger.info(f"馬場状態が変化しました: {previous_track_condition.get('condition')} -> {current_track_condition.get('condition')}")
            return True
            
        prev_moisture = previous_track_condition.get("moisture", 0)
        curr_moisture = current_track_condition.get("moisture", 0)
        if abs(curr_moisture - prev_moisture) >= 2:
            logger.info(f"馬場含水率が大幅に変化しました: {prev_moisture} -> {curr_moisture}")
            return True
            
        if previous_weather_data.get("weather") != current_weather_data.get("weather"):
            logger.info(f"天候が変化しました: {previous_weather_data.get('weather')} -> {current_weather_data.get('weather')}")
            return True
            
        prev_precip = previous_weather_data.get("precipitation_prob", 0)
        curr_precip = current_weather_data.get("precipitation_prob", 0)
        if abs(curr_precip - prev_precip) >= 20:
            logger.info(f"降水確率が大幅に変化しました: {prev_precip}% -> {curr_precip}%")
            return True
            
        prev_wind = previous_weather_data.get("wind_speed", 0)
        curr_wind = current_weather_data.get("wind_speed", 0)
        if curr_wind >= 5 and prev_wind < 5:
            logger.info(f"風速が大幅に上昇しました: {prev_wind}m/s -> {curr_wind}m/s")
            return True
            
        if "tan" in previous_odds_data and "tan" in current_odds_data:
            prev_tan = previous_odds_data["tan"]
            curr_tan = current_odds_data["tan"]
            
            for umaban, prev_odds_str in prev_tan.items():
                if umaban in curr_tan:
                    try:
                        prev_odds = float(prev_odds_str)
                        curr_odds = float(curr_tan[umaban])
                        
                        if prev_odds > 0:
                            change_rate = abs(curr_odds - prev_odds) / prev_odds
                            
                            if change_rate >= 0.15:
                                logger.info(f"単勝オッズが大幅に変動しました: 馬番 {umaban}, {prev_odds} -> {curr_odds} (変動率: {change_rate:.2f})")
                                return True
                    except (ValueError, TypeError):
                        continue
            
            try:
                prev_top3 = sorted(prev_tan.items(), key=lambda x: float(x[1]))[:3]
                curr_top3 = sorted(curr_tan.items(), key=lambda x: float(x[1]))[:3]
                
                prev_top3_nums = [x[0] for x in prev_top3]
                curr_top3_nums = [x[0] for x in curr_top3]
                
                if prev_top3_nums != curr_top3_nums:
                    logger.info(f"人気順が変動しました: {prev_top3_nums} -> {curr_top3_nums}")
                    return True
            except (ValueError, TypeError):
                pass
                
        if "horses" in self.race_data:
            for horse in self.race_data["horses"]:
                umaban = horse.get("umaban")
                weight = horse.get("weight")
                weight_diff = horse.get("weight_diff")
                
                if umaban and weight and weight_diff:
                    try:
                        diff = float(weight_diff.replace("+", "").replace("-", ""))
                        if diff > 6:
                            logger.info(f"馬体重が大幅に変化しました: 馬番 {umaban}, 変化量 {weight_diff}kg")
                            return True
                    except (ValueError, TypeError, AttributeError):
                        continue
        
        return False
        
    def get_cached_probabilities(self) -> Dict[str, Dict[str, float]]:
        """
        キャッシュされた確率を取得します。キャッシュがない場合は計算します。
        
        Returns:
            全ての確率を含む辞書
        """
        if not self.cached_probabilities:
            self.cached_probabilities = self.estimate_all_probabilities()
            
        return self.cached_probabilities
        
    def get_last_update_time(self) -> str:
        """
        最終更新時刻を取得します。
        
        Returns:
            最終更新時刻（ISO形式）
        """
        return datetime.fromtimestamp(self.last_update_time).isoformat()
        
    def get_last_recalculation_time(self) -> str:
        """
        最終再計算時刻を取得します。
        
        Returns:
            最終再計算時刻（ISO形式）
        """
        return datetime.fromtimestamp(self.last_full_recalculation_time).isoformat()
