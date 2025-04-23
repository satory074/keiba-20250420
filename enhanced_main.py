"""
Enhanced main script for horse racing prediction with improved robustness.
"""
import argparse
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

# Import utilities
from utils import get_soup, initialize_driver
from headless_browser import initialize_driver_with_fallback, safe_get_with_retry
from logger_config import get_logger

# Get logger instance
logger = get_logger(__name__)


def load_test_data(race_id: str) -> Optional[Dict[str, Any]]:
    """
    Load test data for a race if available.
    
    Args:
        race_id: Race ID to load test data for
        
    Returns:
        Dictionary containing race data or None if test data not found
    """
    test_filename = f"test_data/flora_stakes_test.json"
    
    if os.path.exists(test_filename):
        try:
            with open(test_filename, "r", encoding="utf-8") as f:
                race_data = json.load(f)
            logger.info(f"Loaded test data for race {race_id} from {test_filename}")
            return race_data
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing test data JSON: {e}")
    
    return None


def main(race_id: str, use_headless: bool = True, use_cache: bool = True, use_test_data: bool = True):
    """
    Enhanced main function to scrape race data with improved robustness.
    
    Args:
        race_id: Race ID to scrape data for
        use_headless: Whether to use headless browser
        use_cache: Whether to use cached data if available
        use_test_data: Whether to use test data if available
    """
    logger.info(f"Starting enhanced data collection for race {race_id}")
    
    # Check if cached data exists
    cache_filename = f"race_data_{race_id}.json"
    if use_cache and os.path.exists(cache_filename):
        logger.info(f"Found cached data for race {race_id}. Loading from {cache_filename}")
        try:
            with open(cache_filename, "r", encoding="utf-8") as f:
                race_data = json.load(f)
            logger.info(f"Successfully loaded cached data for race {race_id}")
            return race_data
        except Exception as e:
            logger.warning(f"Error loading cached data: {e}. Will try test data or scrape fresh data.")
    
    # Try to load test data if enabled
    if use_test_data:
        test_data = load_test_data(race_id)
        if test_data:
            logger.info(f"Using test data for race {race_id}")
            
            # Save test data to race data file
            with open(cache_filename, "w", encoding="utf-8") as f:
                json.dump(test_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved test data to {cache_filename}")
            
            return test_data
    
    # If we reach here, we need to scrape fresh data
    logger.info(f"No cached or test data available for race {race_id}. Scraping fresh data...")
    
    # Initialize WebDriver with fallback mechanisms
    driver = None
    if use_headless:
        driver = initialize_driver_with_fallback()
    else:
        driver = initialize_driver()
    
    if not driver:
        logger.error("Failed to initialize WebDriver. Cannot scrape data that requires Selenium.")
        logger.info("Falling back to minimal data collection...")
    
    # Initialize race data dictionary
    race_data = {"race_id": race_id}
    
    # Scrape basic race info from DB page
    logger.info(f"Fetching race DB page: https://db.netkeiba.com/race/{race_id}")
    soup = get_soup(f"https://db.netkeiba.com/race/{race_id}")
    
    if soup:
        # Import scraper functions here to avoid circular imports
        from scrapers.race_scraper import scrape_race_info, scrape_detailed_race_results
        from scrapers.horse_scraper import scrape_horse_list
        
        logger.info("Extracting race info...")
        race_info = scrape_race_info(soup, race_id)
        race_data.update(race_info)
        
        logger.info("Extracting horse list...")
        horses = scrape_horse_list(soup)
        if horses:
            race_data["horses"] = horses
        else:
            logger.warning(f"Failed to extract horse list from race DB page. Data might be incomplete.")
    else:
        logger.warning(f"Failed to fetch race DB page for race {race_id}. Data might be incomplete.")
    
    # If we have a driver, scrape dynamic content
    if driver:
        # Import scraper functions that require Selenium
        from scrapers.shutuba_scraper import scrape_shutuba_past
        from scrapers.odds_scraper import scrape_live_odds
        from scrapers.paddock_scraper import scrape_paddock_info
        from scrapers.announcement_scraper import scrape_race_announcements
        
        # Scrape shutuba_past page (past performance data)
        from config import SHUTUBA_PAST_URL
        shutuba_url = SHUTUBA_PAST_URL.format(race_id)
        logger.info(f"Fetching shutuba_past page with Selenium: {shutuba_url}")
        
        if safe_get_with_retry(driver, shutuba_url):
            shutuba_data = scrape_shutuba_past(driver, race_id)
            
            # Update horse list if not already populated
            if not race_data.get("horses") and shutuba_data.get("horses"):
                race_data["horses"] = shutuba_data.get("horses", [])
            # Otherwise merge the data
            elif race_data.get("horses") and shutuba_data.get("horses"):
                # Create a mapping of horses by umaban
                horse_map = {horse.get("umaban"): horse for horse in race_data["horses"]}
                
                # Update with shutuba data
                for shutuba_horse in shutuba_data.get("horses", []):
                    umaban = shutuba_horse.get("umaban")
                    if umaban in horse_map:
                        horse_map[umaban].update(shutuba_horse)
                
                # Replace horses list with updated mapping values
                race_data["horses"] = list(horse_map.values())
        else:
            logger.warning(f"Failed to fetch shutuba_past page for race {race_id}. Data might be incomplete.")
        
        # Scrape Live Odds
        logger.info("Scraping live odds...")
        live_odds = scrape_live_odds(driver, race_id)
        race_data["live_odds_data"] = live_odds
        
        # Scrape Paddock Information
        logger.info("Scraping paddock information...")
        paddock_info = scrape_paddock_info(driver, race_id)
        race_data["paddock_info"] = paddock_info
        
        # Scrape Race Announcements
        logger.info("Scraping race announcements...")
        announcements = scrape_race_announcements(driver, race_id)
        race_data["announcements"] = announcements
        
        # Close the WebDriver
        driver.quit()
        logger.info("WebDriver closed.")
    
    # Scrape additional data that doesn't require Selenium
    # Import remaining scraper functions
    from scrapers.race_scraper import scrape_course_details
    from scrapers.horse_scraper import scrape_horse_details, scrape_horse_results, scrape_pedigree, scrape_training
    from scrapers.jockey_scraper import scrape_jockey_profile
    from scrapers.trainer_scraper import scrape_trainer_profile
    from scrapers.odds_scraper import scrape_odds
    from scrapers.speed_figure_scraper import scrape_speed_figures
    
    # Fetch details for each horse
    logger.info(f"Fetching details for {len(race_data.get('horses', []))} horses...")
    
    for i, horse in enumerate(race_data.get("horses", [])):
        horse_id = horse.get("horse_id")
        if not horse_id:
            continue
        
        # Scrape horse details
        horse_details = scrape_horse_details(horse_id)
        if horse_details:
            horse.update(horse_details)
        
        # Scrape horse results
        horse_results = scrape_horse_results(horse_id)
        if horse_results:
            horse["recent_results"] = horse_results
        
        # Scrape pedigree
        pedigree_data = scrape_pedigree(horse_id)
        if pedigree_data:
            horse["pedigree_data"] = pedigree_data
        
        # Scrape training data
        training_data = scrape_training(horse_id)
        if training_data:
            horse["training_data"] = training_data
        
        # Scrape jockey profile
        jockey_id = horse.get("jockey_id")
        if jockey_id:
            jockey_profile = scrape_jockey_profile(jockey_id)
            if jockey_profile:
                horse["jockey_profile"] = jockey_profile
        
        # Scrape trainer profile
        trainer_id = horse.get("trainer_id")
        if trainer_id:
            trainer_profile = scrape_trainer_profile(trainer_id)
            if trainer_profile:
                horse["trainer_profile"] = trainer_profile
        
        logger.info(f"Processed horse {i+1}/{len(race_data.get('horses', []))}: {horse.get('horse_name', 'Unknown')}")
        
        # Add a small delay to avoid overloading the server
        time.sleep(0.5)
    
    # Scrape detailed race results
    logger.info("Scraping detailed race results page (lap times, time diffs)...")
    detailed_results = scrape_detailed_race_results(race_id)
    if detailed_results:
        race_data.update(detailed_results)
    
    # Scrape odds data
    logger.info("Scraping odds data...")
    odds_data = scrape_odds(race_id)
    if odds_data:
        race_data["odds_data"] = odds_data
    
    # Scrape Speed Figures
    logger.info("Scraping speed figures...")
    speed_figures = scrape_speed_figures(race_id)
    race_data["speed_figures"] = speed_figures
    
    # Scrape Course Details
    if "venue_name" in race_data:
        logger.info(f"Scraping course details for venue {race_data['venue_name']}...")
        course_details = scrape_course_details(race_data["venue_name"])
        race_data["course_details"] = course_details
    else:
        logger.warning("Cannot scrape course details as venue_name is missing in race_data.")
    
    # Save to JSON
    output_filename = f"race_data_{race_id}.json"
    logger.info(f"Saving data to {output_filename}...")
    
    # Add timestamp to the data
    race_data["timestamp"] = datetime.now().isoformat()
    
    try:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(race_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Data saved to {output_filename}")
    except Exception as e:
        logger.error(f"Error saving data: {e}", exc_info=True)
    
    return race_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced scraper for horse racing data from netkeiba.com")
    parser.add_argument("race_id", help="Race ID to scrape data for")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache usage")
    parser.add_argument("--no-test-data", action="store_true", help="Disable test data usage")
    
    args = parser.parse_args()
    
    try:
        race_data = main(args.race_id, not args.no_headless, not args.no_cache, not args.no_test_data)
        logger.info(f"Data collection complete for race {args.race_id}")
        
        # Run betting recommendation
        logger.info(f"Generating betting recommendations for race {args.race_id}")
        from betting_recommendation import generate_recommendations
        generate_recommendations(args.race_id)
    except Exception as e:
        logger.error(f"Error in main function: {e}", exc_info=True)
