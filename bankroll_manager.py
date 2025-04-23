"""
Bankroll management module for horse racing prediction.

This module implements advanced bankroll management strategies based on the strategic framework
in docs/main.md, including Kelly criterion, fixed percentage, and drawdown protection.
"""
import math
from typing import Dict, List, Any, Optional, Tuple

from logger_config import get_logger

logger = get_logger(__name__)


class BankrollManager:
    """
    Implements advanced bankroll management strategies for horse racing betting.
    """

    def __init__(self, initial_bankroll: float = 100000, max_risk_per_race: float = 0.05):
        """
        Initialize the bankroll manager with initial bankroll and risk parameters.
        
        Args:
            initial_bankroll: Initial bankroll amount in yen
            max_risk_per_race: Maximum percentage of bankroll to risk on a single race
        """
        self.initial_bankroll = initial_bankroll
        self.current_bankroll = initial_bankroll
        self.max_risk_per_race = max_risk_per_race
        
        self.bet_history = []
        self.performance_metrics = {
            "roi": 0.0,
            "hit_rate": 0.0,
            "drawdown": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0
        }
        
        logger.info(f"Initialized bankroll manager with {initial_bankroll}¥ and {max_risk_per_race:.1%} max risk per race")

    def calculate_bet_size(self, bet_type: str, expected_value: float, odds: float, 
                          probability: float, confidence: float = 0.8) -> int:
        """
        Calculate optimal bet size using Kelly criterion with adjustments.
        
        Args:
            bet_type: Type of bet (e.g., "tan", "fuku", "umaren")
            expected_value: Expected value of the bet
            odds: Decimal odds for the bet
            probability: Estimated probability of winning
            confidence: Confidence level in probability estimate (0-1)
            
        Returns:
            Recommended bet size in yen (rounded to nearest 100)
        """
        logger.info(f"Calculating bet size for {bet_type} bet with EV {expected_value:.2f}, odds {odds}, prob {probability:.2%}")
        
        
        if expected_value <= 1.0 or odds <= 1.0 or probability <= 0.0:
            logger.warning("Invalid parameters for Kelly calculation, returning minimum bet")
            return 100  # Minimum bet
        
        net_odds = odds - 1.0
        kelly_fraction = (net_odds * probability - (1 - probability)) / net_odds
        
        kelly_fraction *= confidence
        
        conservative_kelly = kelly_fraction / 4
        
        conservative_kelly = min(conservative_kelly, self.max_risk_per_race)
        
        bet_amount = self.current_bankroll * conservative_kelly
        
        rounded_amount = max(100, math.ceil(bet_amount / 100) * 100)
        
        logger.info(f"Kelly fraction: {kelly_fraction:.4f}, Conservative Kelly: {conservative_kelly:.4f}")
        logger.info(f"Recommended bet size: {rounded_amount}¥ ({conservative_kelly:.2%} of bankroll)")
        
        return rounded_amount

    def adjust_for_drawdown_protection(self, bet_amount: int) -> int:
        """
        Adjust bet size based on current drawdown to protect bankroll.
        
        Args:
            bet_amount: Initially calculated bet amount
            
        Returns:
            Adjusted bet amount with drawdown protection
        """
        drawdown = 1.0 - (self.current_bankroll / self.initial_bankroll)
        self.performance_metrics["drawdown"] = drawdown
        
        if drawdown > self.performance_metrics["max_drawdown"]:
            self.performance_metrics["max_drawdown"] = drawdown
        
        if drawdown > 0.2:  # More than 20% drawdown
            reduction_factor = 1.0 - (drawdown - 0.2) * 2  # Linear reduction
            reduction_factor = max(0.25, reduction_factor)  # At least 25% of original bet
            
            adjusted_amount = math.ceil(bet_amount * reduction_factor / 100) * 100
            logger.info(f"Applied drawdown protection: {drawdown:.1%} drawdown, reduced bet from {bet_amount}¥ to {adjusted_amount}¥")
            
            return adjusted_amount
        
        return bet_amount

    def record_bet(self, race_id: str, bet_type: str, horses: List[str], 
                  amount: int, odds: float, result: str, payout: int = 0) -> None:
        """
        Record a bet in the betting history and update bankroll.
        
        Args:
            race_id: Race identifier
            bet_type: Type of bet (e.g., "tan", "fuku", "umaren")
            horses: List of horse numbers involved in the bet
            amount: Bet amount in yen
            odds: Decimal odds for the bet
            result: Result of the bet ("win" or "lose")
            payout: Payout amount in yen (if won)
        """
        bet_record = {
            "race_id": race_id,
            "bet_type": bet_type,
            "horses": horses,
            "amount": amount,
            "odds": odds,
            "result": result,
            "payout": payout,
            "profit": payout - amount if result == "win" else -amount,
            "bankroll_before": self.current_bankroll,
        }
        
        if result == "win":
            self.current_bankroll += payout - amount
        else:
            self.current_bankroll -= amount
        
        bet_record["bankroll_after"] = self.current_bankroll
        self.bet_history.append(bet_record)
        
        logger.info(f"Recorded {bet_type} bet on {', '.join(horses)} for {amount}¥ at odds {odds}")
        logger.info(f"Result: {result.upper()}, Payout: {payout}¥, New bankroll: {self.current_bankroll}¥")
        
        self._update_performance_metrics()

    def _update_performance_metrics(self) -> None:
        """
        Update performance metrics based on betting history.
        """
        if not self.bet_history:
            return
        
        total_bets = len(self.bet_history)
        winning_bets = sum(1 for bet in self.bet_history if bet["result"] == "win")
        
        total_stakes = sum(bet["amount"] for bet in self.bet_history)
        total_returns = sum(bet["payout"] for bet in self.bet_history)
        total_profit = sum(bet["profit"] for bet in self.bet_history)
        
        winning_amount = sum(bet["profit"] for bet in self.bet_history if bet["profit"] > 0)
        losing_amount = sum(abs(bet["profit"]) for bet in self.bet_history if bet["profit"] < 0)
        
        self.performance_metrics["hit_rate"] = winning_bets / total_bets if total_bets > 0 else 0
        self.performance_metrics["roi"] = (total_returns / total_stakes - 1) if total_stakes > 0 else 0
        self.performance_metrics["profit_factor"] = winning_amount / losing_amount if losing_amount > 0 else float('inf')
        
        logger.info(f"Updated performance metrics: ROI {self.performance_metrics['roi']:.2%}, "
                   f"Hit rate {self.performance_metrics['hit_rate']:.2%}, "
                   f"Profit factor {self.performance_metrics['profit_factor']:.2f}")

    def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.
        
        Returns:
            Dictionary containing performance metrics and betting history
        """
        report = {
            "initial_bankroll": self.initial_bankroll,
            "current_bankroll": self.current_bankroll,
            "profit_loss": self.current_bankroll - self.initial_bankroll,
            "roi": self.performance_metrics["roi"],
            "hit_rate": self.performance_metrics["hit_rate"],
            "max_drawdown": self.performance_metrics["max_drawdown"],
            "profit_factor": self.performance_metrics["profit_factor"],
            "total_bets": len(self.bet_history),
            "bet_type_breakdown": self._get_bet_type_breakdown(),
            "recent_bets": self.bet_history[-10:] if len(self.bet_history) > 10 else self.bet_history
        }
        
        return report

    def _get_bet_type_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """
        Get performance breakdown by bet type.
        
        Returns:
            Dictionary with performance metrics for each bet type
        """
        breakdown = {}
        
        for bet_type in set(bet["bet_type"] for bet in self.bet_history):
            type_bets = [bet for bet in self.bet_history if bet["bet_type"] == bet_type]
            
            total_bets = len(type_bets)
            winning_bets = sum(1 for bet in type_bets if bet["result"] == "win")
            
            total_stakes = sum(bet["amount"] for bet in type_bets)
            total_returns = sum(bet["payout"] for bet in type_bets)
            
            breakdown[bet_type] = {
                "count": total_bets,
                "wins": winning_bets,
                "hit_rate": winning_bets / total_bets if total_bets > 0 else 0,
                "roi": (total_returns / total_stakes - 1) if total_stakes > 0 else 0,
                "profit": total_returns - total_stakes
            }
        
        return breakdown

    def recommend_bankroll_strategy(self) -> Dict[str, Any]:
        """
        Recommend adjustments to bankroll strategy based on performance.
        
        Returns:
            Dictionary with recommended strategy adjustments
        """
        recommendations = {
            "risk_adjustment": None,
            "bet_type_focus": [],
            "recovery_mode": False,
            "explanation": ""
        }
        
        if len(self.bet_history) < 10:
            recommendations["explanation"] = "Insufficient betting history for strategy recommendations."
            return recommendations
        
        current_drawdown = self.performance_metrics["drawdown"]
        if current_drawdown > 0.3:  # More than 30% drawdown
            recommendations["risk_adjustment"] = "decrease"
            recommendations["recovery_mode"] = True
            recommendations["explanation"] += "Significant drawdown detected. Reducing risk and entering recovery mode. "
        elif current_drawdown < 0.1 and self.performance_metrics["roi"] > 0.05:
            recommendations["risk_adjustment"] = "increase"
            recommendations["explanation"] += "Low drawdown with positive ROI. Consider slightly increasing risk. "
        
        bet_type_breakdown = self._get_bet_type_breakdown()
        profitable_types = [(bt, data) for bt, data in bet_type_breakdown.items() 
                           if data["roi"] > 0.05 and data["count"] >= 5]
        
        if profitable_types:
            profitable_types.sort(key=lambda x: x[1]["roi"], reverse=True)
            recommendations["bet_type_focus"] = [bt for bt, _ in profitable_types[:3]]
            recommendations["explanation"] += f"Focus on these profitable bet types: {', '.join(recommendations['bet_type_focus'])}. "
        
        return recommendations
