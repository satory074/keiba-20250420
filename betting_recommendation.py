"""
Betting recommendation program for horse racing prediction.

This program analyzes collected race data and outputs betting recommendations
based on the strategic framework in docs/main.md and the workflow in docs/workflow.md.
"""
import argparse
import json
import os
from typing import Dict, List, Any, Optional

from logger_config import get_logger
from betting_analyzer import analyze_race

logger = get_logger(__name__)


def format_recommendation(recommendation: Dict[str, Any]) -> str:
    """
    Format a betting recommendation for display.
    
    Args:
        recommendation: Dictionary containing betting recommendation details
        
    Returns:
        Formatted recommendation string
    """
    if recommendation["bet_type"] == "no_bet":
        return f"推奨: 賭けない\n理由: {recommendation['reason']}"
    
    elif recommendation["bet_type"] == "error":
        return f"エラー: {recommendation['reason']}"
    
    elif recommendation["bet_type"] == "tan":
        return (
            f"推奨: 単勝 {recommendation['horse']}番 {recommendation['horse_name']}\n"
            f"金額: {recommendation['amount']}円\n"
            f"オッズ: {recommendation['odds']}\n"
            f"期待値: {recommendation['expected_value']:.2f}\n"
            f"推定確率: {recommendation['probability']}\n"
            f"理由: {recommendation['reason']}"
        )
    
    elif recommendation["bet_type"] == "fuku":
        return (
            f"推奨: 複勝 {recommendation['horse']}番 {recommendation['horse_name']}\n"
            f"金額: {recommendation['amount']}円\n"
            f"オッズ: {recommendation['odds']}\n"
            f"期待値: {recommendation['expected_value']:.2f}\n"
            f"推定確率: {recommendation['probability']}\n"
            f"理由: {recommendation['reason']}"
        )
    
    elif recommendation["bet_type"] == "umaren":
        return (
            f"推奨: 馬連 {'-'.join(recommendation['horses'])}番 ({'-'.join(recommendation['horse_names'])})\n"
            f"金額: {recommendation['amount']}円\n"
            f"オッズ: {recommendation['odds']}\n"
            f"期待値: {recommendation['expected_value']:.2f}\n"
            f"理由: {recommendation['reason']}"
        )
    
    else:
        return f"未対応の賭け種類: {recommendation['bet_type']}"


def main():
    """
    Main function to run the betting recommendation program.
    """
    parser = argparse.ArgumentParser(description="Generate betting recommendations for a horse race.")
    parser.add_argument("race_id", help="The netkeiba race ID (e.g., 202306050811)")
    args = parser.parse_args()
    
    race_id = args.race_id
    race_data_file = f"race_data_{race_id}.json"
    
    logger.info(f"Generating betting recommendations for race {race_id}")
    
    if not os.path.exists(race_data_file):
        logger.error(f"Race data file not found: {race_data_file}")
        print(f"エラー: レースデータファイルが見つかりません: {race_data_file}")
        print("先に以下のコマンドを実行してレースデータを収集してください:")
        print(f"python main.py {race_id}")
        return
    
    recommendations = analyze_race(race_data_file)
    
    print("\n===== 馬券推奨 =====")
    print(f"レースID: {race_id}")
    
    try:
        with open(race_data_file, 'r', encoding='utf-8') as f:
            race_data = json.load(f)
            race_name = race_data.get("race_name", "不明")
            print(f"レース名: {race_name}")
    except Exception:
        print("レース名: 不明")
    
    print("\n")
    
    if not recommendations:
        print("推奨: なし")
        print("理由: 分析中にエラーが発生しました。")
    else:
        for i, recommendation in enumerate(recommendations, 1):
            print(f"推奨 {i}:")
            print(format_recommendation(recommendation))
            print("\n")
    
    output_file = f"betting_recommendation_{race_id}.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(recommendations, f, ensure_ascii=False, indent=2)
        logger.info(f"Recommendations saved to {output_file}")
        print(f"推奨内容を {output_file} に保存しました。")
    except Exception as e:
        logger.error(f"Error saving recommendations to file: {e}")
        print(f"推奨内容の保存中にエラーが発生しました: {e}")


if __name__ == "__main__":
    main()
