"""
Test script for non-Selenium parts of the scraping system.
"""
import json
import re
from datetime import datetime

# Import configurations and utilities
from config import BASE_URL_NETKEIBA
from logger_config import get_logger
from utils import get_soup

# Import scraper functions
from scrapers.race_scraper import scrape_race_info, scrape_detailed_race_results, scrape_course_details
from scrapers.horse_scraper import (
    scrape_horse_list,
    scrape_horse_details,
    scrape_horse_results,
    scrape_pedigree,
)
from scrapers.jockey_scraper import scrape_jockey_profile
from scrapers.trainer_scraper import scrape_trainer_profile
from scrapers.odds_scraper import scrape_odds

# Get logger instance
logger = get_logger(__name__)


def main(race_id):
    """Main function to orchestrate the scraping process."""
    logger.info(f"Starting non-Selenium test for race_id: {race_id}")
    
    # Initialize data structure
    race_data = {"race_id": race_id}
    
    try:
        # 1. Scrape Race Info
        logger.info(f"Fetching race DB page: {BASE_URL_NETKEIBA}/race/{race_id}")
        race_url = f"{BASE_URL_NETKEIBA}/race/{race_id}"
        race_soup = get_soup(race_url)
        
        if race_soup:
            # Extract basic race info
            race_info = scrape_race_info(race_soup, race_id)
            race_data.update(race_info)
            logger.info(f"Extracted basic race info: {race_info.get('race_name', 'Unknown')}")
            
            # 2. Scrape Horse List
            logger.info("Extracting horse list...")
            horses = scrape_horse_list(race_soup)
            race_data["horses"] = horses
            logger.info(f"Found {len(horses)} horses in the race.")
            
            # 3. Scrape Detailed Results
            logger.info("Scraping detailed race results...")
            detailed_results = scrape_detailed_race_results(race_id)
            race_data.update(detailed_results)
            
            # 4. Scrape Course Details
            if "venue_name" in race_data:
                logger.info(f"Scraping course details for venue {race_data['venue_name']}...")
                course_details = scrape_course_details(race_data["venue_name"])
                race_data["course_details"] = course_details
            else:
                logger.warning("Cannot scrape course details as venue_name is missing in race_data.")
            
            # 5. Extract Payout Info
            logger.info("Extracting payout info...")
            payout_data = scrape_odds(race_soup, race_id)
            race_data["payouts"] = payout_data.get("payouts", {})
            
            # 6. Process each horse
            for i, horse in enumerate(horses):
                horse_id = horse.get("horse_id")
                if horse_id:
                    logger.info(f"Processing horse {i+1}/{len(horses)}: {horse.get('horse_name', 'Unknown')} (ID: {horse_id})")
                    
                    # 6.1 Scrape Horse Details
                    horse_details = scrape_horse_details(horse_id)
                    horses[i].update(horse_details)
                    
                    # 6.2 Scrape Horse Results
                    horse_results = scrape_horse_results(horse_id)
                    horses[i]["past_results"] = horse_results
                    
                    # 6.3 Scrape Pedigree
                    pedigree_data = scrape_pedigree(horse_id)
                    horses[i]["pedigree_data"] = pedigree_data
                    
                    # 6.4 Scrape Jockey Profile
                    jockey_id = horse.get("jockey_id")
                    if jockey_id:
                        jockey_profile = scrape_jockey_profile(jockey_id)
                        horses[i]["jockey_profile"] = jockey_profile
                    
                    # 6.5 Scrape Trainer Profile
                    trainer_id = horse.get("trainer_id")
                    if trainer_id:
                        trainer_profile = scrape_trainer_profile(trainer_id)
                        horses[i]["trainer_profile"] = trainer_profile
                else:
                    logger.warning(f"No horse_id found for horse {i+1}, skipping detailed scraping.")
            
            # 7. Save to JSON
            output_filename = f"test_race_data_{race_id}.json"
            logger.info(f"Saving data to {output_filename}...")
            
            # Add timestamp to the data
            race_data["timestamp"] = datetime.now().isoformat()
            
            try:
                with open(output_filename, "w", encoding="utf-8") as f:
                    json.dump(race_data, f, ensure_ascii=False, indent=2)
                logger.info(f"Data saved to {output_filename}")
                
                # Create validation report
                validation_report = {
                    "filename": output_filename,
                    "race_id": race_data.get("race_id", None),
                    "race_name": race_data.get("race_name", None),
                    "horse_count": len(race_data.get("horses", [])),
                    "course_details": "course_details" in race_data,
                    "payouts": bool(race_data.get("payouts", {})),
                }
                
                report_filename = f"test_validation_report_{race_id}.json"
                with open(report_filename, "w", encoding="utf-8") as f:
                    json.dump(validation_report, f, ensure_ascii=False, indent=2)
                logger.info(f"Test validation report saved to {report_filename}")
                
            except Exception as e:
                logger.error(f"Error saving data: {e}", exc_info=True)
        else:
            logger.error(f"Failed to fetch race page for {race_id}")
    
    except Exception as e:
        logger.error(f"An error occurred during scraping: {e}", exc_info=True)
    
    logger.info("Non-Selenium test completed.")
    return race_data


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test non-Selenium parts of the Netkeiba scraper.")
    parser.add_argument("race_id", help="Race ID to scrape (e.g., 202306050811)")
    args = parser.parse_args()
    
    main(args.race_id)
