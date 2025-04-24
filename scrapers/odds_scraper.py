"""
Scraping functions related to odds and payouts.
"""
import re # Added import
import time
from datetime import datetime
from itertools import zip_longest
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.remote.webdriver import WebDriver # Import WebDriver for type hinting
from selenium.webdriver.common.by import By # Added import
from selenium.common.exceptions import NoSuchElementException, TimeoutException # Added import
from selenium.webdriver.support.ui import WebDriverWait # Added import
from selenium.webdriver.support import expected_conditions as EC # Added import


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

            # Check if payout_yen_text is a string before replacing
            payout_yen_str = payout_yen_text.replace(",", "") if isinstance(payout_yen_text, str) else ""
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
            elif bet_type == "fuku": # 複勝 (Place) - Revised Parsing
                # Attempt to find individual entries within the cells
                num_cell, pay_cell, pop_cell = tds[0], tds[1], tds[2] if len(tds) > 2 else None
                # Find potential entries (e.g., separated by <br> or within simple tags)
                # This is a guess - might need find_all('span') or similar depending on actual structure
                nums_raw = [clean_text(t) for t in num_cell.find_all(string=True, recursive=False) if clean_text(t)] or \
                           [clean_text(num_cell.text)] # Fallback to full text
                # Add check for string before replace, including in the fallback - Revised
                pays_from_children = [clean_text(t).replace(",", "") for t in pay_cell.find_all(string=True, recursive=False) if isinstance(clean_text(t), str)]
                if not pays_from_children:
                    pay_cell_text = clean_text(pay_cell.text)
                    pays_raw = [pay_cell_text.replace(",", "") if isinstance(pay_cell_text, str) else ""]
                else:
                    pays_raw = pays_from_children
                pops_raw = []
                if pop_cell:
                    pops_raw = [clean_text(t) for t in pop_cell.find_all(string=True, recursive=False) if clean_text(t)] or \
                               [clean_text(pop_cell.text)]

                # Clean up empty strings that might result from splitting/finding
                nums = [n for n in nums_raw if n]
                pays = [p for p in pays_raw if p]
                pops = [p for p in pops_raw if p]

                logger.debug(f"Fuku raw parsed: nums={nums}, pays={pays}, pops={pops}")

                payouts["place"] = []
                for n, p, pop in zip_longest(nums, pays, pops, fillvalue=None):
                    try:
                        payout_val = int(p) if p and p.isdigit() else None
                        pop_val = int(pop) if pop and pop.isdigit() else None
                    except (ValueError, TypeError):
                        payout_val = None
                        pop_val = None
                    payouts["place"].append({"umaban": n, "payout": payout_val, "popularity": pop_val})

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

            # Check if payout_yen_text is a string before replacing
            payout_yen_str = payout_yen_text.replace(",", "") if isinstance(payout_yen_text, str) else ""
            popularity_str = popularity_text if popularity_text else None

            try:
                payout_yen = int(payout_yen_str) if payout_yen_str.isdigit() else None
                popularity = int(popularity_str) if popularity_str and popularity_str.isdigit() else None
            except ValueError:
                 logger.warning(f"Could not convert payout/popularity to int for {bet_type}: {payout_yen_str}, {popularity_str}")
                 payout_yen = None
                 popularity = None

            if bet_type == "wide": # ワイド (Wide) - Revised Parsing
                num_cell, pay_cell, pop_cell = tds[0], tds[1], tds[2] if len(tds) > 2 else None
                # Find potential entries (e.g., separated by <br> or within simple tags)
                nums_raw = [clean_text(t) for t in num_cell.find_all(string=True, recursive=False) if clean_text(t)] or \
                           [clean_text(num_cell.text)]
                # Add check for string before replace, including in the fallback - Revised
                pays_from_children = [clean_text(t).replace(",", "") for t in pay_cell.find_all(string=True, recursive=False) if isinstance(clean_text(t), str)]
                if not pays_from_children:
                    pay_cell_text = clean_text(pay_cell.text)
                    pays_raw = [pay_cell_text.replace(",", "") if isinstance(pay_cell_text, str) else ""]
                else:
                    pays_raw = pays_from_children
                pops_raw = []
                if pop_cell:
                    pops_raw = [clean_text(t) for t in pop_cell.find_all(string=True, recursive=False) if clean_text(t)] or \
                               [clean_text(pop_cell.text)]

                # Clean up empty strings
                nums = [n for n in nums_raw if n]
                pays = [p for p in pays_raw if p]
                pops = [p for p in pops_raw if p]

                logger.debug(f"Wide raw parsed: nums={nums}, pays={pays}, pops={pops}")

                payouts["wide"] = []
                for n, p, pop in zip_longest(nums, pays, pops, fillvalue=None):
                    try:
                        # Wide payout might be a range "XXX-XXX" or single value
                        payout_val_str = p
                        pop_val = int(pop) if pop and pop.isdigit() else None
                    except (ValueError, TypeError):
                        payout_val_str = None
                        pop_val = None
                    payouts["wide"].append({"umaban_pair": n, "payout": payout_val_str, "popularity": pop_val})

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
    """Scrapes live odds information using Selenium, including multiple bet types.""" # Updated docstring
    logger.info(f"Scraping live odds for race {race_id}...")
    live_odds_data = {"race_id": race_id, "timestamp": datetime.now().isoformat(), "odds": {}} # Initialize with timestamp and odds dict
    odds_url = f"https://race.netkeiba.com/odds/index.html?race_id={race_id}" # Common odds page

    if not driver:
        logger.error("WebDriver not initialized. Cannot scrape live odds.")
        return live_odds_data

    try:
        logger.info(f"Fetching live odds page with Selenium: {odds_url}")
        driver.get(odds_url)
        # Use WebDriverWait for initial page load check with multiple possible selectors
        try:
            # Try multiple possible selectors for odds container
            try:
                WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                    EC.presence_of_element_located((By.ID, "odds_tanpuku_list"))
                )
                logger.debug("Initial odds page loaded (traditional odds_tanpuku_list found).")
            except TimeoutException:
                try:
                    WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "Odds_Table"))
                    )
                    logger.debug("Initial odds page loaded (Odds_Table class found).")
                except TimeoutException:
                    WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "RaceOdds_HorseList"))
                    )
                    logger.debug("Initial odds page loaded (RaceOdds_HorseList class found).")
            
            try:
                odds_timestamp_element = driver.find_element(By.CLASS_NAME, "RaceOdds_UpdateTime")
                if odds_timestamp_element:
                    live_odds_data["odds_update_time"] = clean_text(odds_timestamp_element.text)
            except NoSuchElementException:
                try:
                    odds_timestamp_element = driver.find_element(By.CLASS_NAME, "UpdateTime")
                    if odds_timestamp_element:
                        live_odds_data["odds_update_time"] = clean_text(odds_timestamp_element.text)
                except NoSuchElementException:
                    logger.warning("Could not find odds update timestamp element.")
        except TimeoutException:
            logger.error(f"Timeout waiting for any odds page elements on {odds_url}")
            return live_odds_data

        # --- Helper function to get soup after potential AJAX loads ---
        def get_current_soup(webdriver):
            return BeautifulSoup(webdriver.page_source, "html.parser")

        # --- Scrape Tan/Fuku (Initial View) ---
        soup = get_current_soup(driver)
        
        # Try multiple possible containers for Tan/Fuku odds
        odds_container = None
        tan_fuku_table = None
        
        odds_container = soup.find("div", id="odds_tanpuku_list")
        if odds_container and isinstance(odds_container, Tag):
            logger.debug("Found traditional odds_tanpuku_list container")
            tan_fuku_table = odds_container.find("table")
            
        # Try 2025 format containers if traditional not found
        if not tan_fuku_table:
            odds_tables = soup.find_all("table", class_=re.compile(r"Odds_Table|RaceOdds_Table"))
            for table in odds_tables:
                header_row = table.find("tr", class_=re.compile(r"Header|Heading"))
                if header_row:
                    header_cells = header_row.find_all(["th", "td"])
                    header_texts = [clean_text(cell.text) for cell in header_cells]
                    # Check if this table has Win/Place odds
                    if any(win_text in " ".join(header_texts) for win_text in ["単勝", "Win", "win"]):
                        tan_fuku_table = table
                        logger.debug(f"Found 2025 format Tan/Fuku table with headers: {header_texts}")
                        break
        
        if not tan_fuku_table:
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                if len(rows) > 1:  # At least one header row and one data row
                    first_data_row = rows[1]
                    cells = first_data_row.find_all(["td", "th"])
                    # Check if this row has a horse number and potential odds
                    if len(cells) >= 3 and re.match(r'^\d+$', clean_text(cells[0].text)):
                        tan_fuku_table = table
                        logger.debug("Found potential Tan/Fuku table by structure analysis")
                        break
        
        if tan_fuku_table and isinstance(tan_fuku_table, Tag):
            live_odds_data["odds"]["tan_fuku"] = []
            rows = tan_fuku_table.find_all("tr")
            
            start_idx = 1 if len(rows) > 1 and rows[0].find("th") else 0
            
            for row in rows[start_idx:]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:  # Basic validation
                    try:
                        umaban_cell = cells[0]
                        
                        if umaban_cell.has_attr('data-sort-value'):
                            umaban = umaban_cell['data-sort-value']
                        else:
                            umaban = clean_text(umaban_cell.text)
                            
                        if not umaban or not re.match(r'^\d+$', umaban):
                            continue
                        
                        # Extract horse name - usually in second column or in a specific span
                        horse_name = None
                        if len(cells) > 1:
                            horse_name_tag = cells[1].find("span", class_=re.compile(r"HorseName|Horse_Name"))
                            if horse_name_tag:
                                horse_name = clean_text(horse_name_tag.text)
                            else:
                                horse_name = clean_text(cells[1].text)
                                
                                if re.match(r'^[\d.]+$', horse_name):
                                    horse_name = None
                        
                        tan_odds = None
                        fuku_odds = None
                        
                        # Check if we have at least 3 columns
                        if len(cells) > 2:
                            for i in range(1, min(4, len(cells))):
                                cell_text = clean_text(cells[i].text) if cells[i].text else ""
                                if cell_text and (re.match(r'^[\d.]+$', cell_text) or re.match(r'^[\d.]+-[\d.]+$', cell_text)):
                                    if tan_odds is None:
                                        tan_odds = cell_text
                                    elif fuku_odds is None:
                                        fuku_odds = cell_text
                                elif cell_text and horse_name is None and re.search(r'[ぁ-んァ-ンー一-龯]', cell_text):
                                    horse_name = cell_text
                        
                        if tan_odds is None and len(cells) > 2:
                            tan_odds_text = clean_text(cells[2].text)
                            if tan_odds_text and tan_odds_text != "---":
                                odds_match = re.search(r'([\d.]+)', tan_odds_text)
                                if odds_match:
                                    tan_odds = odds_match.group(1)
                        
                        if fuku_odds is None and len(cells) > 3:
                            fuku_text = clean_text(cells[3].text)
                            if fuku_text and fuku_text != "---":
                                odds_match = re.search(r'([\d.]+-[\d.]+|[\d.]+)', fuku_text)
                                if odds_match:
                                    fuku_odds = odds_match.group(1)
                        
                        popularity = None
                        if len(cells) > 4:
                            popularity = clean_text(cells[4].text)
                        
                        odds_entry = {
                            "umaban": umaban,
                            "horse_name": horse_name if horse_name and horse_name != "--" else None,
                            "tan_odds": tan_odds,  # 単勝 (Win)
                            "fuku_odds": fuku_odds,  # 複勝 (Place)
                            "popularity": popularity  # Current popularity based on win odds
                        }
                        
                        # Clean up None values
                        odds_entry = {k: v for k, v in odds_entry.items() if v is not None}
                        
                        live_odds_data["odds"]["tan_fuku"].append(odds_entry)
                    except Exception as e:
                        logger.warning(f"Error parsing Tan/Fuku row: {e}", exc_info=True)
            
            logger.info(f"Successfully scraped Tan/Fuku odds ({len(live_odds_data['odds']['tan_fuku'])} entries).")
        else:
            logger.warning(f"Could not find any Tan/Fuku odds table for race {race_id}")

        # --- Function to click tab and parse matrix/list odds ---
        # Updated to wait for content within the main form div to change/appear
        def click_and_parse_odds(tab_selector_tuple, target_element_locator, odds_key, parse_func):
            # target_element_locator: A tuple (By, selector) for an element expected inside the loaded content
            main_content_div_id = "odds_view_form" # Div where content is loaded
            try:
                logger.info(f"Attempting to click tab: {tab_selector_tuple}")
                tab_element = WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                    EC.element_to_be_clickable(tab_selector_tuple)
                )
                # Get current content signature before click (e.g., first few chars of the div)
                # This helps detect if content actually changed, though not foolproof
                try:
                    before_content_sig = driver.find_element(By.ID, main_content_div_id).text[:50]
                except:
                    before_content_sig = "" # Handle case where div might be empty initially

                tab_element.click()
                logger.info(f"Clicked tab {tab_selector_tuple}. Waiting for target element {target_element_locator} within #{main_content_div_id}...")

                # Wait for a specific element expected within the newly loaded content
                WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f"#{main_content_div_id} {target_element_locator[1]}"))
                    # Example: Wait for a table inside the form: EC.presence_of_element_located((By.CSS_SELECTOR, f"#{main_content_div_id} table"))
                )
                # Optional: Add a small sleep or check if content signature changed
                time.sleep(1.5) # Increased buffer slightly for JS rendering

                logger.debug(f"Target element {target_element_locator} found. Parsing content within #{main_content_div_id}...")
                current_soup = get_current_soup(driver)
                # Pass the main container soup to the parsing function
                main_content_soup = current_soup.find("div", id=main_content_div_id)
                if not main_content_soup:
                     logger.warning(f"Could not find main content div #{main_content_div_id} after clicking tab.")
                     return # Exit if main container not found

                odds_list = parse_func(main_content_soup) # Pass the container's soup
                if odds_list:
                    # Handle combined results like umaren/wide
                    if isinstance(odds_list, dict) and odds_key == "umaren_wide":
                         if odds_list.get("umaren"):
                             live_odds_data["odds"]["umaren"] = odds_list["umaren"]
                             logger.info(f"Successfully scraped umaren odds ({len(odds_list['umaren'])} entries).")
                         if odds_list.get("wide"):
                             live_odds_data["odds"]["wide"] = odds_list["wide"]
                             logger.info(f"Successfully scraped wide odds ({len(odds_list['wide'])} entries).")
                    elif isinstance(odds_list, list) and odds_list:
                         live_odds_data["odds"][odds_key] = odds_list
                         logger.info(f"Successfully scraped {odds_key} odds ({len(odds_list)} entries).")
                    else:
                         logger.warning(f"Parsing function returned empty or invalid data for {odds_key}.")
                else:
                    # Corrected log message: container_id is not defined here anymore
                    logger.warning(f"Parsing function returned no data for {odds_key}.")

            except TimeoutException:
                logger.warning(f"Timeout waiting for tab {tab_selector_tuple} or target element {target_element_locator}.")
            except NoSuchElementException:
                logger.warning(f"Could not find tab element {tab_selector_tuple}.")
            except Exception as e:
                logger.error(f"Error clicking tab {tab_selector_tuple} or parsing {main_content_div_id}: {e}", exc_info=True)

        # --- Parsing Functions for Different Odds Types ---
        # Updated functions to accept the container soup directly
        def parse_umaren_wide(container_soup):
            """Parses Umaren (馬連) and Wide (ワイド) odds from their shared container soup."""
            odds_data = {"umaren": [], "wide": []}
            if not container_soup or not isinstance(container_soup, Tag):
                logger.warning(f"Invalid container soup passed to parse_umaren_wide.")
                return None

            # Find Umaren table: Look for the first table within the container,
            # potentially checking for a header containing '馬連' if needed for robustness.
            umaren_table = container_soup.find("table") # Find the first table
            # Optional check: if umaren_table and not umaren_table.find("th", string=re.compile("馬連")): umaren_table = None

            if umaren_table and isinstance(umaren_table, Tag):
                logger.debug("Found potential Umaren table within container.")
                rows = umaren_table.find_all("tr")
                header_cells = rows[0].find_all("th") if rows else []
                # Get horse numbers from header (skip first cell)
                header_nums = [clean_text(th.text) for th in header_cells[1:]]

                for row in rows[1:]: # Skip header row
                    cells = row.find_all("td")
                    row_header_th = row.find("th")
                    if not row_header_th or len(cells) != len(header_nums): continue # Check alignment
                    row_num = clean_text(row_header_th.text)

                    for i, cell in enumerate(cells):
                        col_num = header_nums[i]
                        # Ensure numbers are valid strings and digits before combining/comparing
                        if isinstance(row_num, str) and row_num.isdigit() and \
                           isinstance(col_num, str) and col_num.isdigit() and \
                           int(row_num) < int(col_num):
                            odds_val = clean_text(cell.text)
                            if odds_val and odds_val != '---': # Check for valid odds
                                odds_data["umaren"].append({
                                    "umaban_pair": f"{row_num}-{col_num}",
                                    "odds": odds_val
                                })
            else:
                logger.warning(f"Umaren table not found or invalid within the provided container soup.")

            # Find Wide table: Often follows Umaren or is the second table.
            # This assumes Wide data might be in a *separate* table following Umaren.
            # If they are in the *same* table, this logic needs adjustment.
            all_tables = container_soup.find_all("table")
            wide_table = None
            if len(all_tables) > 1:
                 # Try the second table, potentially check header for 'ワイド'
                 wide_table_candidate = all_tables[1]
                 # Optional check: if wide_table_candidate.find("th", string=re.compile("ワイド")): wide_table = wide_table_candidate
                 # For now, assume the second table is Wide if it exists
                 wide_table = wide_table_candidate
            elif umaren_table: # If only one table, assume it might contain Wide too (less likely based on typical structure)
                 logger.debug("Only one table found, assuming Wide might be combined or absent.")
                 # wide_table = umaren_table # Uncomment if Wide is in the same table

            if wide_table and isinstance(wide_table, Tag):
                 logger.debug("Found potential Wide table within container.")
                 rows = wide_table.find_all("tr")
                 header_cells = rows[0].find_all("th") if rows else []
                 header_nums = [clean_text(th.text) for th in header_cells[1:]]

                 for row in rows[1:]:
                     cells = row.find_all("td")
                     row_header_th = row.find("th")
                     if not row_header_th or len(cells) != len(header_nums): continue
                     row_num = clean_text(row_header_th.text)

                     for i, cell in enumerate(cells):
                         col_num = header_nums[i]
                         # Ensure numbers are valid strings and digits before combining/comparing
                         if isinstance(row_num, str) and row_num.isdigit() and \
                            isinstance(col_num, str) and col_num.isdigit() and \
                            int(row_num) < int(col_num):
                             # Wide odds often have min-max
                             odds_range = clean_text(cell.text)
                             if odds_range and odds_range != '---':
                                 odds_data["wide"].append({
                                     "umaban_pair": f"{row_num}-{col_num}",
                                     "odds_range": odds_range
                                 })
            else:
                logger.warning(f"Wide table not found or invalid within the provided container soup.")

            # Return combined data only if at least one type was found
            return odds_data if odds_data["umaren"] or odds_data["wide"] else None


        def parse_umatan(container_soup):
            """Parses Umatan (馬単) odds from the container soup."""
            odds_list = []
            if not container_soup or not isinstance(container_soup, Tag):
                logger.warning(f"Invalid container soup passed to parse_umatan.")
                return None
            # Umatan often uses a matrix table. Find the first table in the container.
            umatan_table = container_soup.find("table") # Find the first table
            # Optional check: if umatan_table and not umatan_table.find("th", string=re.compile("馬単")): umatan_table = None

            if umatan_table and isinstance(umatan_table, Tag):
                logger.debug("Found potential Umatan table within container.")
                rows = umatan_table.find_all("tr")
                header_cells = rows[0].find_all("th") if rows else []
                header_nums = [clean_text(th.text) for th in header_cells[1:]] # 2nd place horse

                for row in rows[1:]: # Skip header row
                    cells = row.find_all("td")
                    row_header_th = row.find("th")
                    if not row_header_th or len(cells) != len(header_nums): continue
                    first_place_num = clean_text(row_header_th.text) # 1st place horse

                    for i, cell in enumerate(cells):
                        second_place_num = header_nums[i]
                        # Ensure numbers are valid strings and digits and different
                        if isinstance(first_place_num, str) and first_place_num.isdigit() and \
                           isinstance(second_place_num, str) and second_place_num.isdigit() and \
                           first_place_num != second_place_num:
                            odds_val = clean_text(cell.text)
                            if odds_val and odds_val != '---':
                                odds_list.append({
                                    "umaban_order": f"{first_place_num}-{second_place_num}",
                                    "odds": odds_val
                                })
            else:
                logger.warning(f"Umatan table not found or invalid within the provided container soup.")
            return odds_list if odds_list else None

        def parse_sanrenpuku(container_soup):
            """Parses Sanrenpuku (３連複) odds from the container soup."""
            # Sanrenpuku is complex. Placeholder logic remains.
            odds_list = []
            if not container_soup or not isinstance(container_soup, Tag):
                logger.warning(f"Invalid container soup passed to parse_sanrenpuku.")
                return None
            # Example: Find tables associated with each 1st axis horse (adjust selector)
            # tables = container_soup.find_all("table", class_="Odds_Table_Small") # Example class
            # for table in tables:
            #     # Parse combinations and odds within each table
            #     pass
            logger.warning(f"Sanrenpuku parsing logic is complex and not fully implemented. Needs specific page analysis.")
            # Placeholder: Try finding any odds-like text within the container
            odds_elements = container_soup.find_all(string=re.compile(r"\d+\.\d+")) # Find text matching odds pattern
            if odds_elements:
                 logger.debug(f"Found {len(odds_elements)} potential Sanrenpuku odds elements (unstructured).")
                 odds_list.append({"raw_data_found": len(odds_elements)}) # Indicate data was found but not parsed structuredly
            else:
                 logger.warning("No potential Sanrenpuku odds elements found in container.")
            return odds_list if odds_list else None


        def parse_sanrentan(container_soup):
            """Parses Sanrentan (３連単) odds from the container soup."""
            # Sanrentan is even more complex. Placeholder logic remains.
            odds_list = []
            if not container_soup or not isinstance(container_soup, Tag):
                logger.warning(f"Invalid container soup passed to parse_sanrentan.")
                return None
            # Example: May involve selecting 1st, then 2nd, then seeing odds for 3rd
            # Requires significant interaction simulation or complex table parsing
            logger.warning(f"Sanrentan parsing logic is extremely complex and not fully implemented. Needs specific page analysis.")
            # Placeholder: Try finding any odds-like text within the container
            odds_elements = container_soup.find_all(string=re.compile(r"\d+\.\d+")) # Find text matching odds pattern
            if odds_elements:
                 logger.debug(f"Found {len(odds_elements)} potential Sanrentan odds elements (unstructured).")
                 odds_list.append({"raw_data_found": len(odds_elements)}) # Indicate data was found but not parsed structuredly
            else:
                 logger.warning("No potential Sanrentan odds elements found in container.")
            return odds_list if odds_list else None


        # --- Click Tabs and Parse ---
        # Using corrected tab selectors and waiting logic

        # Define target elements to wait for within each loaded section (these are guesses)
        # We wait for a table element as a general indicator content has loaded
        table_locator = (By.TAG_NAME, "table")

        # Umaren / Wide (Tab b4 / b5) - Often loaded together
        umaren_tab_selector = (By.CSS_SELECTOR, "li#odds_navi_b4 a")
        # Click Umaren tab, expect a table, parse both Umaren and Wide
        click_and_parse_odds(umaren_tab_selector, table_locator, "umaren_wide", parse_umaren_wide)
        # Note: Wide tab (b5) might load the same content, so clicking it might be redundant
        # If they load separately, add:
        # wide_tab_selector = (By.CSS_SELECTOR, "li#odds_navi_b5 a")
        # click_and_parse_odds(wide_tab_selector, table_locator, "wide", parse_umaren_wide) # Need adjusted parse func if separate

        # Umatan (Tab b6)
        umatan_tab_selector = (By.CSS_SELECTOR, "li#odds_navi_b6 a")
        click_and_parse_odds(umatan_tab_selector, table_locator, "umatan", parse_umatan)

        # Sanrenpuku (Tab b7)
        sanrenpuku_tab_selector = (By.CSS_SELECTOR, "li#odds_navi_b7 a")
        # Target element might be different if not a simple table
        click_and_parse_odds(sanrenpuku_tab_selector, table_locator, "sanrenpuku", parse_sanrenpuku)

        # Sanrentan (Tab b8)
        sanrentan_tab_selector = (By.CSS_SELECTOR, "li#odds_navi_b8 a")
        # Target element might be different if not a simple table
        click_and_parse_odds(sanrentan_tab_selector, table_locator, "sanrentan", parse_sanrentan)


    except Exception as e:
        logger.error(f"Error scraping live odds for {race_id}: {e}", exc_info=True)

    # Update log message based on what was actually scraped
    scraped_types = list(live_odds_data["odds"].keys())
    logger.info(f"Finished scraping live odds for race {race_id}. Scraped types: {scraped_types}")
    return live_odds_data
