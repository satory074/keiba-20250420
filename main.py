"""
Main script to orchestrate the Netkeiba race data scraping process.
"""
import argparse
import json
import re
from datetime import datetime

# Import configurations and utilities
from config import BASE_URL_NETKEIBA
from logger_config import get_logger
from utils import initialize_driver, get_soup

# Import scraper functions
from scrapers.race_scraper import scrape_race_info, scrape_detailed_race_results, scrape_course_details
from scrapers.horse_scraper import (
    scrape_horse_list,
    scrape_horse_details,
    scrape_horse_results,
    scrape_pedigree,
    scrape_training,
)
from scrapers.jockey_scraper import scrape_jockey_profile
from scrapers.trainer_scraper import scrape_trainer_profile
from scrapers.odds_scraper import scrape_odds, scrape_live_odds
from scrapers.shutuba_scraper import scrape_shutuba_past
from scrapers.paddock_scraper import scrape_paddock_info
from scrapers.speed_figure_scraper import scrape_speed_figures
from scrapers.announcement_scraper import scrape_race_announcements

# Get logger instance
logger = get_logger(__name__)


def main(race_id):
    """Main function to orchestrate the scraping process."""
    logger.info(f"Starting scraping for race_id: {race_id}")
    driver = None # Initialize driver to None
    race_data = {} # Initialize race_data

    try:
        driver = initialize_driver() # Initialize WebDriver

        # 1. Scrape Race Page (using requests)
        # Note: The race page URL structure might differ slightly (e.g., /race/ vs /db/race/)
        # Using the structure observed in the original scrape_race_info function
        race_db_url = f"{BASE_URL_NETKEIBA}/race/{race_id}"
        logger.info(f"Fetching race DB page: {race_db_url}")
        race_soup = get_soup(race_db_url)
        if not race_soup:
            logger.error(f"Failed to fetch race DB page: {race_db_url}. Exiting.")
            return

        # 2. Extract Race Info from race page soup
        logger.info("Extracting race info...")
        race_data = scrape_race_info(race_soup, race_id)

        # 3. Extract Horse List from race page soup
        logger.info("Extracting horse list...")
        horses_summary = scrape_horse_list(race_soup)
        if not horses_summary:
            logger.warning("Failed to extract horse list from race DB page. Data might be incomplete.")
            # Continue processing other parts if possible, but mark data as potentially incomplete
            race_data["horses"] = []
            # Consider if exiting is better if horse list is crucial
            # return

        # 4. Scrape Shutuba Past page (using Selenium)
        past_perf_by_umaban = scrape_shutuba_past(driver, race_id)

        # 5. Extract Detailed Horse Info (Iterate through horses) & Merge Past Perf
        logger.info(f"Fetching details for {len(horses_summary)} horses...")
        all_horse_details = []
        for i, horse_sum in enumerate(horses_summary):
            horse_id_str = horse_sum.get('horse_id', 'N/A')
            logger.info(f"  Fetching details for horse {i+1}/{len(horses_summary)} (ID: {horse_id_str})...")
            merged_details = horse_sum.copy() # Start with summary data

            if 'horse_id' in horse_sum:
                horse_id = horse_sum["horse_id"]
                details = scrape_horse_details(horse_id)
                merged_details.update(details) # Merge details

                horse_results = scrape_horse_results(horse_id)
                merged_details["full_results_data"] = horse_results

                pedigree_data = scrape_pedigree(horse_id)
                merged_details["pedigree_data"] = pedigree_data

                training_data = scrape_training(driver, horse_id)
                merged_details["training_data"] = training_data

                if merged_details.get("jockey_id"):
                    jockey_profile_data = scrape_jockey_profile(merged_details["jockey_id"])
                    merged_details["jockey_profile"] = jockey_profile_data
                if merged_details.get("trainer_id"):
                     trainer_profile_data = scrape_trainer_profile(merged_details["trainer_id"])
                     merged_details["trainer_profile"] = trainer_profile_data

            else:
                logger.warning(f"  Skipping detailed fetch for horse {i+1} due to missing ID.")

            # Merge past performance data if available, identified by umaban
            try:
                umaban_int = int(horse_sum.get("umaban", 0))
                if umaban_int in past_perf_by_umaban:
                    merged_details.update(past_perf_by_umaban[umaban_int])
                    logger.debug(f"Merged past performance for umaban {umaban_int}")
                else:
                    logger.debug(f"No past performance data found for umaban {umaban_int}")
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert umaban '{horse_sum.get('umaban')}' to int for merging past perf.")

            all_horse_details.append(merged_details)

        race_data["horses"] = all_horse_details # Assign horse details

        # 6. Scrape Detailed Race Results (Lap Times, Weather, Time Diffs etc.)
        logger.info("Scraping detailed race results page (lap times, time diffs)...")
        detailed_results = scrape_detailed_race_results(race_id)
        # Extract time diffs before merging the rest
        time_diffs = detailed_results.pop("time_diffs", {})
        race_data.update(detailed_results) # Merge lap times, weather etc. into main race_data

        # Merge Time Diffs into horse data
        logger.info("Merging time differences into horse data...")
        if "horses" in race_data: # Ensure horses list exists
            for horse_detail in race_data["horses"]:
                try:
                    umaban_int = int(horse_detail.get("umaban", 0))
                    if umaban_int in time_diffs:
                        horse_detail["time_diff_result_page"] = time_diffs[umaban_int] # B3.4
                        logger.debug(f"Merged time_diff '{time_diffs[umaban_int]}' for umaban {umaban_int}")
                    else:
                        logger.debug(f"No time diff data found for umaban {umaban_int} on results page.")
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert umaban '{horse_detail.get('umaban')}' to int for merging time diff.")
        else:
            logger.warning("Cannot merge time diffs as 'horses' key is missing in race_data.")


        # 7. Scrape Live Odds (using Selenium driver)
        logger.info("Scraping live odds...")
        live_odds = scrape_live_odds(driver, race_id) # Pass driver instance
        race_data["live_odds_data"] = live_odds # Add live odds under new key

        logger.info("Scraping paddock information...")
        paddock_info = scrape_paddock_info(driver, race_id)
        race_data["paddock_info"] = paddock_info

        logger.info("Scraping speed figures...")
        speed_figures = scrape_speed_figures(race_id)
        race_data["speed_figures"] = speed_figures

        logger.info("Scraping race announcements...")
        announcements = scrape_race_announcements(driver, race_id)
        race_data["announcements"] = announcements

        if "venue_name" in race_data:
            logger.info(f"Scraping course details for venue {race_data['venue_name']}...")
            course_details = scrape_course_details(race_data["venue_name"])
            race_data["course_details"] = course_details
        else:
            logger.warning("Cannot scrape course details as venue_name is missing in race_data.")

        # 12. Extract Payout Info (from main race page soup - already scraped)
        logger.info("Extracting payout info (from earlier race page scrape)...")
        # Need the race_soup obtained in step 1
        if race_soup:
            payout_data = scrape_odds(race_soup, race_id)
            race_data["payouts"] = payout_data.get("payouts", {}) # Extract only the payouts dict
        else:
            logger.warning("Cannot extract payouts as race_soup is not available.")
            race_data["payouts"] = {}


        output_filename = f"race_data_{race_id}.json"
        logger.info(f"Validating and saving data to {output_filename}...")
        
        race_data["timestamp"] = datetime.now().isoformat()
        
        from validator import validate_and_save_race_data
        
        validation_result = validate_and_save_race_data(race_data, output_filename)
        if validation_result:
            logger.info("Data validation successful. All required fields are present.")
        else:
            logger.warning("Data validation found missing fields. See validation report for details.")

    except Exception as e:
        logger.error(f"An unexpected error occurred during the main process for race {race_id}: {e}", exc_info=True)
    finally:
        # --- Ensure WebDriver is closed ---
        if driver:
            logger.info("Quitting WebDriver...")
            driver.quit()
            logger.info("WebDriver quit.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape race data from netkeiba.com for a given race ID.")
    parser.add_argument("race_id", help="The netkeiba race ID (e.g., 202306050811 for the 2023 Japan Derby)")
    args = parser.parse_args()

    # Basic validation for race_id format (example: 12 digits)
    if not re.match(r"^\d{12}$", args.race_id):
        logger.error(f"Invalid race_id format '{args.race_id}'. Expected 12 digits.")
    else:
        main(args.race_id)
