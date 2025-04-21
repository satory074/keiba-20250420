"""
Scraping functions related to odds and payouts.
"""
import time
from datetime import datetime
from itertools import zip_longest
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.remote.webdriver import WebDriver # Import WebDriver for type hinting

# Import shared utilities and config
from utils import clean_text
from logger_config import get_logger
from config import SELENIUM_WAIT_TIME

# Get logger instance
logger = get_logger(__name__)


def scrape_odds(race_soup: BeautifulSoup, race_id: str):
    """Scrapes odds/payout information (D1 - Payouts only) from the main race result page soup."""
    odds_data = {"timestamp": datetime.now().isoformat(), "payouts": {}}
    logger.info(f"Attempting to scrape odds/payouts for race {race_id} from main page soup.")

    try:
        pay_block = race_soup.find("dl", class_="pay_block")
        if not pay_block:
            logger.warning(f"Payout block 'dl.pay_block' not found for race {race_id}")
            return odds_data

        # Check if pay_block is a Tag object before calling find_all
        if not isinstance(pay_block, Tag):
             logger.error(f"Expected pay_block to be a Tag, but got {type(pay_block)}. Cannot proceed.")
             return odds_data

        pay_tables = pay_block.find_all("table", class_="pay_table_01")
        if len(pay_tables) < 2:
            logger.warning(f"Expected at least 2 'pay_table_01' tables within 'pay_block', found {len(pay_tables)} for race {race_id}")
            return odds_data

        # --- Table 1: Win, Place, Waku, Umaren ---
        table1 = pay_tables[0]
        rows1 = table1.find_all("tr")
        payouts = {}
        for row in rows1:
            th = row.find("th")
            tds = row.find_all("td")
            if not th or len(tds) < 2: continue

            bet_type = clean_text(th.get("class")[0]) if th.get("class") else clean_text(th.text) # Use class or text
            numbers = clean_text(tds[0].text)
            payout_yen_text = clean_text(tds[1].text)
            popularity_text = clean_text(tds[2].text) if len(tds) > 2 else None

            payout_yen_str = payout_yen_text.replace(",", "") if payout_yen_text else ""
            popularity_str = popularity_text if popularity_text else None

            try:
                payout_yen = int(payout_yen_str) if payout_yen_str.isdigit() else None
                popularity = int(popularity_str) if popularity_str and popularity_str.isdigit() else None
            except ValueError:
                 logger.warning(f"Could not convert payout/popularity to int for {bet_type}: {payout_yen_str}, {popularity_str}")
                 payout_yen = None
                 popularity = None

            if bet_type == "tan": # 単勝
                payouts["win"] = {"umaban": numbers, "payout": payout_yen, "popularity": popularity}
            elif bet_type == "fuku": # 複勝
                # Check if numbers and pays are not None before splitting
                nums = numbers.split() if numbers else []
                pays = payout_yen_str.split() if payout_yen_str else []
                pops = popularity_str.split() if popularity_str else []
                # Use zip_longest to handle lists of potentially different lengths (extend calls removed)
                payouts["place"] = [{"umaban": n, "payout": p, "popularity": pop} for n, p, pop in zip_longest(nums, pays, pops, fillvalue=None)]
            elif bet_type == "waku": # 枠連
                payouts["wakuren"] = {"waku_pair": numbers, "payout": payout_yen, "popularity": popularity}
            elif bet_type == "uren": # 馬連
                payouts["umaren"] = {"umaban_pair": numbers, "payout": payout_yen, "popularity": popularity}

        # --- Table 2: Wide, Utan, Sanfuku, Santan ---
        table2 = pay_tables[1]
        rows2 = table2.find_all("tr")
        for row in rows2:
            th = row.find("th")
            tds = row.find_all("td")
            if not th or len(tds) < 2: continue

            bet_type = clean_text(th.get("class")[0]) if th.get("class") else clean_text(th.text)
            numbers = clean_text(tds[0].text)
            payout_yen_text = clean_text(tds[1].text)
            popularity_text = clean_text(tds[2].text) if len(tds) > 2 else None

            payout_yen_str = payout_yen_text.replace(",", "") if payout_yen_text else ""
            popularity_str = popularity_text if popularity_text else None

            try:
                payout_yen = int(payout_yen_str) if payout_yen_str.isdigit() else None
                popularity = int(popularity_str) if popularity_str and popularity_str.isdigit() else None
            except ValueError:
                 logger.warning(f"Could not convert payout/popularity to int for {bet_type}: {payout_yen_str}, {popularity_str}")
                 payout_yen = None
                 popularity = None

            if bet_type == "wide": # ワイド
                # Check if numbers and pays are not None before splitting
                nums = numbers.split() if numbers else []
                pays = payout_yen_str.split() if payout_yen_str else []
                pops = popularity_str.split() if popularity_str else []
                # Use zip_longest to handle lists of potentially different lengths (extend calls removed)
                payouts["wide"] = [{"umaban_pair": n, "payout": p, "popularity": pop} for n, p, pop in zip_longest(nums, pays, pops, fillvalue=None)]
            elif bet_type == "utan": # 馬単
                payouts["umatan"] = {"umaban_order": numbers, "payout": payout_yen, "popularity": popularity}
            elif bet_type == "sanfuku": # ３連複
                payouts["sanrenpuku"] = {"umaban_combo": numbers, "payout": payout_yen, "popularity": popularity}
            elif bet_type == "santan": # ３連単
                payouts["sanrentan"] = {"umaban_order": numbers, "payout": payout_yen, "popularity": popularity}

        odds_data["payouts"] = payouts
        logger.info(f"Successfully scraped payout data for race {race_id}")

    except Exception as e:
        logger.error(f"Error scraping odds/payouts for race {race_id}: {e}", exc_info=True)

    logger.debug(f"Finished scraping odds/payouts for race {race_id}: {odds_data}")
    return odds_data


def scrape_live_odds(driver: WebDriver, race_id: str): # Accept driver instance
    """Scrapes live odds information using Selenium."""
    logger.info(f"Scraping live odds for race {race_id}...")
    live_odds_data = {"race_id": race_id, "timestamp": datetime.now().isoformat(), "odds": {}} # Initialize with timestamp and odds dict
    odds_url = f"https://race.netkeiba.com/odds/index.html?race_id={race_id}" # Common odds page

    if not driver:
        logger.error("WebDriver not initialized. Cannot scrape live odds.")
        return live_odds_data

    try:
        logger.info(f"Fetching live odds page with Selenium: {odds_url}")
        driver.get(odds_url)
        time.sleep(SELENIUM_WAIT_TIME) # Wait for odds tables to potentially load/update
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        logger.debug(f"Successfully fetched live odds page source for race {race_id}")

        # --- Extract Odds Tables (D1.1 - D1.7) ---
        odds_container = soup.find("div", id="odds_tanpuku_list") # Main container for Tan/Fuku
        if odds_container and isinstance(odds_container, Tag):
            # Tan/Fuku Table (D1.1, D1.2)
            tanfuku_table = odds_container.find("table") # Usually the first table inside
            if tanfuku_table and isinstance(tanfuku_table, Tag):
                live_odds_data["odds"]["tan_fuku"] = []
                rows = tanfuku_table.find_all("tr")
                for row in rows[1:]: # Skip header
                    cells = row.find_all("td")
                    if len(cells) >= 5: # Umaban, Horse Name, Tan Odds, Fuku Odds (Min-Max), Popularity
                        try:
                            umaban = clean_text(cells[0].text)
                            horse_name_tag = cells[1].find("span", class_="HorseName") # Find the specific span
                            horse_name = clean_text(horse_name_tag.text) if horse_name_tag else None
                            tan_odds = clean_text(cells[2].text)
                            fuku_odds = clean_text(cells[3].text)
                            popularity = clean_text(cells[4].text)
                            odds_entry = {
                                "umaban": umaban,
                                "horse_name": horse_name,
                                "tan_odds": tan_odds, # 単勝 (Win)
                                "fuku_odds": fuku_odds, # 複勝 (Place)
                                "popularity": popularity # Current popularity based on win odds
                            }
                            live_odds_data["odds"]["tan_fuku"].append(odds_entry)
                            logger.debug(f"Added Tan/Fuku odds: {odds_entry}")
                        except Exception as e:
                            logger.warning(f"Error parsing Tan/Fuku row: {row}. Error: {e}")
            else:
                logger.warning(f"Tan/Fuku odds table not found within 'odds_tanpuku_list' for race {race_id}")
        else:
            logger.warning(f"Odds container 'odds_tanpuku_list' not found for race {race_id}")

        # --- TODO: Extract other odds types (Umaren, Wide, Umatan, Sanfuku, Santan) ---
        # These are often in different sections/tabs or loaded via JavaScript interactions.
        # Requires further investigation of the odds page structure and potentially clicking tabs/buttons with Selenium.
        # Example selectors (might need adjustment):
        # umaren_wide_container = soup.find("div", id="odds_umaren_list")
        # umatan_container = soup.find("div", id="odds_umatan_list")
        # sanfuku_container = soup.find("div", id="odds_sanrenpuku_list")
        # santan_container = soup.find("div", id="odds_sanrentan_list")
        logger.warning(f"Scraping for Umaren, Wide, Umatan, Sanfuku, Santan odds is not yet implemented for race {race_id}.")


    except Exception as e:
        logger.error(f"Error scraping live odds for {race_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping live odds (Tan/Fuku only) for race {race_id}.")
    return live_odds_data
