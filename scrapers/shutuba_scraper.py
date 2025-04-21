"""
Scraping functions related to the shutuba_past page (detailed past performance).
"""
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.remote.webdriver import WebDriver # Import WebDriver for type hinting

# Import shared utilities and config
from utils import clean_text
from logger_config import get_logger
from config import SHUTUBA_PAST_URL, SELENIUM_WAIT_TIME

# Get logger instance
logger = get_logger(__name__)


def scrape_shutuba_past(driver: WebDriver, race_id: str):
    """Scrapes detailed past performance (last 5 races) using Selenium."""
    shutuba_url = SHUTUBA_PAST_URL.format(race_id)
    logger.info(f"Fetching shutuba_past page with Selenium: {shutuba_url}")
    past_perf_data = {} # Store data by umaban: {umaban: {'past_5_races': [...]}}

    if not driver:
        logger.error("WebDriver not initialized. Cannot scrape shutuba_past.")
        return past_perf_data

    try:
        driver.get(shutuba_url)
        time.sleep(SELENIUM_WAIT_TIME) # Wait for JavaScript to load the table
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        logger.debug(f"Successfully fetched shutuba_past page source for race {race_id}")

        table = soup.find("table", class_="Shutuba_Past5_Table")
        if not table:
            logger.warning(f"Shutuba_Past5_Table not found on page: {shutuba_url}")
            # Check if it's a page indicating no race data exists
            no_data_msg = soup.find("div", class_="Race_Infomation_Box")
            if no_data_msg and "レース情報が見つかりませんでした" in no_data_msg.text:
                 logger.info(f"No race data found on shutuba_past page (likely invalid race ID or future race): {shutuba_url}")
            else:
                 logger.warning(f"Shutuba_Past5_Table not found on page, and no 'not found' message detected: {shutuba_url}")
            return past_perf_data

        # Check if table is a Tag object before calling find
        if not isinstance(table, Tag):
             logger.error(f"Expected table to be a Tag, but got {type(table)}. Cannot proceed.")
             return past_perf_data

        tbody = table.find("tbody")
        if not tbody:
             logger.warning(f"Tbody not found in Shutuba_Past5_Table on page: {shutuba_url}")
             return past_perf_data

        # Check if tbody is a Tag object before calling find_all
        if not isinstance(tbody, Tag):
             logger.error(f"Expected tbody to be a Tag, but got {type(tbody)}. Cannot proceed.")
             return past_perf_data

        rows = tbody.find_all("tr")
        logger.info(f"Found {len(rows)} rows in Shutuba_Past5_Table.")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 10: # Need at least enough cells for umaban and 5 past races
                logger.debug(f"Skipping row with insufficient cells: {row}")
                continue

            umaban_str = "unknown" # Initialize umaban_str
            try:
                umaban_str = clean_text(cells[1].text)
                if not umaban_str or not umaban_str.isdigit():
                    logger.warning(f"Could not parse umaban from cell: {cells[1]}")
                    continue
                umaban = int(umaban_str)
                horse_past_data = {'past_5_races': []}

                # Extract past 5 race details
                for i in range(5, 10): # Indices for past race cells
                    past_race_cell = cells[i]
                    race_detail = {}
                    # Check if the cell represents a past race entry
                    if "Past" in past_race_cell.get("class", []):
                        data_item = past_race_cell.find("div", class_="Data_Item")
                        if data_item:
                            data01 = data_item.find("div", class_="Data01")
                            data02 = data_item.find("div", class_="Data02")
                            if data01:
                                spans = data01.find_all("span")
                                if len(spans) > 1:
                                    # Extract date and attempt to parse
                                    date_text = clean_text(spans[0].text)
                                    date_str = date_text.split(" ")[0] if date_text else None # Example: 23.10.22
                                    if date_str:
                                        try:
                                            # Corrected format string for YYYY.MM.DD
                                            race_detail['date'] = datetime.strptime(date_str, "%Y.%m.%d").strftime("%Y-%m-%d")
                                        except ValueError:
                                            # Fallback for YY.MM.DD if the first fails
                                            try:
                                                race_detail['date'] = datetime.strptime(date_str, "%y.%m.%d").strftime("%Y-%m-%d")
                                            except ValueError:
                                                logger.warning(f"Could not parse date '{date_str}' with formats %Y.%m.%d or %y.%m.%d for umaban {umaban}, cell {i}")
                                                race_detail['date'] = date_str # Keep original if parsing fails
                                    else:
                                         race_detail['date'] = None
                                    race_detail['rank'] = clean_text(spans[1].text)
                            if data02:
                                spans = data02.find_all("span")
                                if len(spans) > 1:
                                     race_detail['venue_dist'] = clean_text(spans[0].text) # e.g., 東京芝1800
                                     race_detail['jockey_weight'] = clean_text(spans[1].text) # e.g., ルメール 57.0
                            # Add more details if needed from Data01/Data02 or other elements like time diff,上がり etc.
                            # Example: time_diff = data_item.find(...)
                            horse_past_data['past_5_races'].append(race_detail)
                        else:
                             logger.debug(f"No Data_Item div found in Past cell for umaban {umaban}, cell index {i}")
                             horse_past_data['past_5_races'].append(None) # Placeholder if no data item
                    else:
                        # logger.debug(f"Cell is not a 'Past' cell for umaban {umaban}, cell index {i}")
                        horse_past_data['past_5_races'].append(None) # Placeholder if not a past race cell

                past_perf_data[umaban] = horse_past_data
                logger.debug(f"Extracted past performance for umaban {umaban}: {horse_past_data}")

            except Exception as e:
                logger.error(f"Error processing row for umaban {umaban_str}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error scraping shutuba_past page {shutuba_url}: {e}", exc_info=True)

    return past_perf_data
