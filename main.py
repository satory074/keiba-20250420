import argparse
import datetime
import json
import logging  # Import logging module
import re
import time
from datetime import datetime # Import datetime class specifically
from itertools import zip_longest # Import zip_longest

import requests
from bs4 import BeautifulSoup, Tag # Import Tag for type checking
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,  # Set default logging level (INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__) # Get a logger instance

# --- Configuration ---
BASE_URL_NETKEIBA = "https://db.netkeiba.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}
REQUEST_DELAY = 1  # seconds between requests to avoid overloading server
SHUTUBA_PAST_URL = "https://race.netkeiba.com/race/shutuba_past.html?race_id={}&rf=shutuba_submenu"
SELENIUM_WAIT_TIME = 2 # seconds to wait for dynamic content to load

# --- Helper Functions ---

def initialize_driver():
    """Initializes a headless Chrome WebDriver."""
    logger.info("Initializing WebDriver...")
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox") # Often needed in restricted environments
        chrome_options.add_argument("--disable-dev-shm-usage") # Overcomes limited resource problems
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("WebDriver initialized successfully.")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {e}", exc_info=True)
        return None


def get_soup(url):
    """Fetches content from a URL using requests and returns a BeautifulSoup object."""
    logger.debug(f"Fetching URL with requests: {url}")
    try:
        time.sleep(REQUEST_DELAY)  # Be polite to the server
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        response.encoding = response.apparent_encoding  # Adjust encoding
        soup = BeautifulSoup(response.text, "html.parser")
        # logger.debug(response.text) # Optionally log the full HTML for debugging
        logger.debug(f"Successfully fetched and parsed URL: {url}")
        return soup
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None


def clean_text(text):
    """Removes extra whitespace and newline characters from text."""
    if text:
        # Ensure text is a string before calling replace
        if isinstance(text, str):
            return re.sub(r"\s+", " ", text).strip()
        else:
            # Handle cases where text might not be a string (e.g., from BeautifulSoup)
            try:
                return re.sub(r"\s+", " ", str(text)).strip()
            except Exception:
                 logger.warning(f"Could not convert non-string to string for cleaning: {type(text)}")
                 return None # Or return the original non-string object if appropriate
    return None


# --- Data Extraction Functions ---


def scrape_race_info(soup, race_id):
    """Scrapes basic race information from the race page soup."""
    race_info = {"race_id": race_id}
    try:
        # --- Extract Race Number ---
        race_num_tag = soup.find("div", class_="RaceNum")
        if race_num_tag:
            race_info["race_number"] = clean_text(race_num_tag.text)
            logger.debug(f"Found race_number: {race_info['race_number']}")
        else:
            logger.warning("Could not find 'RaceNum' div.")

        # --- Extract Race Name, Date, Venue etc. using updated selectors ---
        main_data_div = soup.find("div", class_="mainrace_data")
        if main_data_div:
            # Race Name
            race_name_h1 = main_data_div.select_one("dd h1")
            if race_name_h1:
                race_info["race_name"] = clean_text(race_name_h1.text)
                logger.debug(f"Found race_name: {race_info['race_name']}")

            # Race Details Span (Distance, Course, Weather, Condition)
            details_span = main_data_div.select_one("dd p span")
            if details_span:
                details_text = clean_text(details_span.text)
                logger.debug(f"Found details_span text: {details_text}")
                # Example: "芝右2500m / 天候 : 晴 / 芝 : 良 / 発走 : 15:40"
                # Parsing logic needs refinement based on variations
                if details_text: # Check if details_text is not None
                    parts = details_text.split('/')
                    if len(parts) >= 3:
                        # Distance, Course Type, Direction
                        course_match = re.match(r"(芝|ダ)(右|左)(\d+)m", parts[0].strip())
                        if course_match:
                            race_info["course_type"] = course_match.group(1)
                            race_info["direction"] = course_match.group(2)
                            race_info["distance_meters"] = course_match.group(3) + "m"
                        else: # Handle cases like "障..."
                             course_match_alt = re.match(r"(障)(?:・障害)?(\d+)m", parts[0].strip())
                             if course_match_alt:
                                 race_info["course_type"] = course_match_alt.group(1)
                                 race_info["direction"] = None # Direction might not apply or be listed for jumps
                                 race_info["distance_meters"] = course_match_alt.group(2) + "m"

                        # Weather
                        weather_match = re.search(r"天候\s*:\s*(\S+)", parts[1].strip())
                        if weather_match:
                            race_info["weather"] = weather_match.group(1)

                        # Track Condition
                        condition_match = re.search(r"(?:芝|ダ)\s*:\s*(\S+)", parts[2].strip())
                        if condition_match:
                            race_info["track_condition"] = condition_match.group(1)
                    else:
                        logger.warning(f"Could not parse details_span fully: {details_text}")
                else:
                    logger.warning("details_span text is None or empty.")


            # Date, Venue Detail, Class, Conditions (A1.1, A1.2, A1.8-A1.11)
            smalltxt_p = main_data_div.find_next_sibling("p", class_="smalltxt")
            if smalltxt_p:
                smalltxt_text = clean_text(smalltxt_p.text)
                logger.debug(f"Found smalltxt: {smalltxt_text}")
                # Example: "2023年12月24日 5回中山8日目 3歳以上オープン  (国際)(指)(定量)"
                if smalltxt_text:
                    parts = smalltxt_text.split(maxsplit=2) # Split into max 3 parts: date, venue_day, rest
                    if len(parts) >= 3:
                        # A1.1 Date
                        date_str = parts[0]
                        try:
                            # Convert "YYYY年MM月DD日" to "YYYY-MM-DD"
                            dt_obj = datetime.strptime(date_str, "%Y年%m月%d日")
                            race_info["date"] = dt_obj.strftime("%Y-%m-%d")
                            logger.debug(f"Parsed date: {race_info['date']}")
                        except ValueError:
                            logger.warning(f"Could not parse date string: {date_str}")
                            race_info["date_text"] = date_str # Keep original if parsing fails

                        # A1.2 Venue Name and Meeting Day
                        venue_detail_str = parts[1]
                        race_info["venue_meeting_day"] = venue_detail_str
                        # Extract venue name (e.g., 中山, 東京)
                        venue_match = re.search(r"(\d+回)?([^\d]+)(\d+日目)", venue_detail_str)
                        if venue_match:
                            race_info["venue_name"] = venue_match.group(2)
                            logger.debug(f"Parsed venue_name: {race_info['venue_name']}")
                        else:
                            logger.warning(f"Could not parse venue name from: {venue_detail_str}")

                        # A1.8, A1.9, A1.10, A1.11 Class and Conditions
                        class_conditions_str = parts[2]
                        race_info["race_class_conditions_raw"] = class_conditions_str

                        # Extract Age Condition (e.g., 2歳, 3歳, 3歳以上, 4歳以上)
                        age_match = re.search(r"(\d歳(?:以上)?)", class_conditions_str)
                        if age_match:
                            race_info["age_condition"] = age_match.group(1) # A1.9
                            logger.debug(f"Parsed age_condition: {race_info['age_condition']}")

                        # Extract Sex Condition (e.g., 牡・牝, 牝) - Look within parentheses or specific terms
                        sex_condition = None
                        if "(牝)" in class_conditions_str or "牝馬限定" in class_conditions_str:
                            sex_condition = "牝" # A1.10
                        elif "(牡・牝)" in class_conditions_str or "混合" in class_conditions_str:
                             sex_condition = "混合" # A1.10
                        # Add more specific checks if needed (e.g., 牡馬限定)
                        if sex_condition:
                            race_info["sex_condition"] = sex_condition
                            logger.debug(f"Parsed sex_condition: {race_info['sex_condition']}")

                        # Extract Weight Condition (e.g., 馬齢, 別定, 定量, ハンデ) - Look within parentheses
                        weight_condition = None
                        if "(馬齢)" in class_conditions_str: weight_condition = "馬齢"
                        elif "(別定)" in class_conditions_str: weight_condition = "別定"
                        elif "(定量)" in class_conditions_str: weight_condition = "定量"
                        elif "(ハンデ)" in class_conditions_str: weight_condition = "ハンデ"
                        if weight_condition:
                            race_info["weight_condition"] = weight_condition # A1.11
                            logger.debug(f"Parsed weight_condition: {race_info['weight_condition']}")

                        # Extract Race Class (e.g., G1, G2, G3, L, オープン, 3勝クラス, etc.) - Often precedes age condition
                        # This is complex, try a few common patterns
                        class_match = re.search(r"(G[1-3]|L|オープン|[1-3]勝クラス|未勝利|新馬)", class_conditions_str)
                        if class_match:
                            race_info["race_class"] = class_match.group(1) # A1.8
                            logger.debug(f"Parsed race_class: {race_info['race_class']}")
                        else:
                            # Fallback: Take the part before age condition if found
                            if age_match:
                                potential_class = class_conditions_str[:age_match.start()].strip()
                                if potential_class:
                                     race_info["race_class"] = potential_class
                                     logger.debug(f"Parsed race_class (fallback): {race_info['race_class']}")


                    else:
                         logger.warning(f"Could not parse smalltxt fully (expected 3+ parts): {smalltxt_text}")
                else:
                    logger.warning("smalltxt text is None or empty.")
        else:
            logger.warning("Could not find 'mainrace_data' div.")

        # --- Extract Head Count (from horse list table header) ---
        # This might be better placed after horse list scraping, but trying here first
        try:
            race_table = soup.find("table", class_="race_table_01 nk_tb_common")
            if race_table and isinstance(race_table, Tag):
                header_row = race_table.find("tr")
                if header_row:
                    # Look for a header cell containing '頭数'
                    head_count_th_found = False
                    for th in header_row.find_all("th"):
                        # Ensure th is a Tag before accessing text
                        if isinstance(th, Tag) and re.search(r"頭数", clean_text(th.text) or ""):
                            head_count_th_found = True
                            break
                    # head_count_th = header_row.find("th", string=re.compile(r"頭数")) # Original line causing Pylance warning
                    if head_count_th_found:
                        # The actual count might be in the race info section, let's re-check main_data_div siblings or parents
                        # Re-checking smalltxt or similar for head count
                        smalltxt_p = main_data_div.find_next_sibling("p", class_="smalltxt")
                        if smalltxt_p:
                             smalltxt_text = clean_text(smalltxt_p.text)
                             # Example: "11頭 3歳以上オープン..."
                             # Ensure smalltxt_text is not None before searching
                             if smalltxt_text:
                                 head_count_match = re.search(r"(\d+)頭", smalltxt_text)
                                 if head_count_match:
                                     race_info["head_count"] = int(head_count_match.group(1))
                                     logger.debug(f"Found head_count: {race_info['head_count']}")
                                 else:
                                     logger.warning("Could not extract head_count from smalltxt.")
                             else:
                                 logger.warning("smalltxt_text was None, cannot search for head_count.")
                        else:
                             logger.warning("smalltxt not found again for head_count check.")
                    else:
                        logger.warning("Head count header '頭数' not found in race table.")
                else:
                    logger.warning("Header row not found in race table for head_count check.")
            else:
                logger.warning("Race table not found or not a Tag for head_count check.")
        except Exception as hc_err:
            logger.warning(f"Error trying to extract head_count: {hc_err}")


        # --- Placeholder for more detailed weather/track info (A3, A4) ---
        # These might require scraping other sections or pages (e.g., JRA site)
        # Example: Look for specific divs/spans containing humidity, wind, cushion value etc.
        # race_info["humidity"] = ...
        # race_info["wind_speed"] = ...
        # race_info["cushion_value"] = ...

        logger.info(f"Extracted race info: {race_info}")
        # Add more extraction logic for A1 items here based on actual HTML

    except Exception as e:
        logger.error(f"Error scraping race info for race {race_id}: {e}", exc_info=True)
    return race_info


def scrape_horse_list(soup):
    """Scrapes the list of horses and their IDs from the race page soup."""
    horses = []
    try:
        # Corrected selector based on HTML analysis and blog post reference
        logger.debug("Searching for horse list table with classes 'race_table_01 nk_tb_common'")
        race_table = soup.find("table", class_="race_table_01 nk_tb_common")
        if not race_table:
            logger.warning(f"Horse list table 'race_table_01 nk_tb_common' not found for race {soup.find('title').text if soup.find('title') else 'Unknown Race'}.")
            return horses

        # Check if race_table is a Tag object before calling find_all
        if not isinstance(race_table, Tag):
             logger.error(f"Expected race_table to be a Tag, but got {type(race_table)}. Cannot proceed.")
             return horses

        # Extra check for Pylance warning, though the above should suffice
        assert isinstance(race_table, Tag), f"Type check failed unexpectedly for race_table: {type(race_table)}"
        # Add another explicit check before find_all for Pylance
        if isinstance(race_table, Tag):
            rows = race_table.find_all("tr") # Line 241
        else:
            logger.error("race_table is not a Tag object, cannot find rows.")
            return horses # Return empty list if table is not a Tag

        for row in rows[1:]:  # Skip header row
            horse_data = {}
            cells = row.find_all("td")
            if len(cells) > 3:  # Basic check for valid row
                # Extract Horse ID from link
                horse_link_tag = cells[3].find("a", href=re.compile(r"/horse/\d+"))
                if horse_link_tag:
                    horse_id_match = re.search(r"/horse/(\d+)", horse_link_tag["href"])
                    if horse_id_match:
                        horse_data["horse_id"] = horse_id_match.group(1)

                # Extract other basic info directly from the race table
                horse_data["wakuban"] = clean_text(cells[0].text) # B1.3
                horse_data["umaban"] = clean_text(cells[1].text) # B1.2
                horse_data["horse_name"] = clean_text(cells[3].text) # B1.1

                # Parse Sex and Age (B1.4, B1.5) from combined field (e.g., "牡4")
                sex_age_text = clean_text(cells[4].text)
                if sex_age_text:
                    match = re.match(r"([牡牝セ])(\d+)", sex_age_text) # Match 性別 (Sex) and 年齢 (Age)
                    if match:
                        horse_data["sex"] = match.group(1) # B1.4
                        horse_data["age"] = int(match.group(2)) # B1.5
                        logger.debug(f"Parsed sex: {horse_data['sex']}, age: {horse_data['age']}")
                    else:
                        logger.warning(f"Could not parse sex/age from: {sex_age_text}")
                        horse_data["sex_age_raw"] = sex_age_text # Keep raw if parsing fails
                else:
                     horse_data["sex_age_raw"] = None


                horse_data["burden_weight"] = clean_text(cells[5].text) # B1.6

                # Extract Jockey Name and ID (C1.1)
                jockey_cell = cells[6]
                jockey_link = jockey_cell.find("a", href=re.compile(r"/jockey/"))
                if jockey_link:
                    horse_data["jockey"] = clean_text(jockey_link.text)
                    jockey_id_match = re.search(r"/jockey/result/recent/(\w+)/", jockey_link["href"]) # Or just /jockey/(\w+)/
                    if jockey_id_match:
                        horse_data["jockey_id"] = jockey_id_match.group(1)
                        logger.debug(f"Parsed jockey: {horse_data['jockey']}, id: {horse_data['jockey_id']}")
                    else:
                         logger.warning(f"Found jockey link but could not parse ID: {jockey_link['href']}")
                         horse_data["jockey_id"] = None
                else:
                    horse_data["jockey"] = clean_text(jockey_cell.text) # Fallback to text if no link
                    horse_data["jockey_id"] = None
                    logger.debug(f"Parsed jockey (no link/ID): {horse_data['jockey']}")


                # Corrected indices based on HTML analysis (0-based)
                # Extract Trainer Name and ID (B1.7 / C2.1)
                if len(cells) > 18: # Check if trainer cell exists
                    trainer_cell = cells[18]
                    trainer_link = trainer_cell.find('a', href=re.compile(r"/trainer/"))
                    if trainer_link:
                        horse_data["trainer"] = clean_text(trainer_link.text)
                        # Refined regex to capture digits specifically for the ID
                        trainer_id_match = re.search(r"/trainer/(\d+)/", trainer_link["href"])
                        if trainer_id_match:
                            horse_data["trainer_id"] = trainer_id_match.group(1)
                            logger.debug(f"Parsed trainer: {horse_data['trainer']}, id: {horse_data['trainer_id']}")
                        else:
                            logger.warning(f"Found trainer link but could not parse ID: {trainer_link['href']}")
                            horse_data["trainer_id"] = None
                    else:
                        horse_data["trainer"] = clean_text(trainer_cell.text) # Fallback to text
                        horse_data["trainer_id"] = None
                        logger.debug(f"Parsed trainer (no link/ID): {horse_data['trainer']}")
                else:
                    horse_data["trainer"] = None
                    horse_data["trainer_id"] = None
                    logger.debug(f"Trainer cell missing for row: {row}")

                if len(cells) > 14: # Check if weight cell exists
                    horse_data["weight_diff"] = clean_text(cells[14].text) # Weight/Diff is in the 15th cell (index 14)
                else:
                     horse_data["weight_diff"] = None
                     horse_data["weight_diff_raw"] = None # Keep raw field name consistent
                     logger.debug(f"Weight cell missing for row: {row}")

                # Parse Horse Weight and Diff (B3.17) from combined field
                weight_diff_text = horse_data.pop("weight_diff", None) # Get and remove the raw string field
                if weight_diff_text:
                    match = re.match(r"(\d+)\(([-+]\d+|新|計不)\)", weight_diff_text) # Match weight and diff (e.g., 480(+2), 500(新), ???(計不))
                    if match:
                        horse_data["horse_weight"] = int(match.group(1))
                        horse_data["horse_weight_diff"] = match.group(2) # Keep diff as string (+2, -4, 新, 計不)
                        logger.debug(f"Parsed weight: {horse_data['horse_weight']}, diff: {horse_data['horse_weight_diff']}")
                    else:
                        # Handle cases where only weight is present (e.g., "480")
                        if weight_diff_text.isdigit():
                             horse_data["horse_weight"] = int(weight_diff_text)
                             horse_data["horse_weight_diff"] = None # No diff info
                             logger.debug(f"Parsed weight (no diff): {horse_data['horse_weight']}")
                        else:
                             logger.warning(f"Could not parse weight/diff from: {weight_diff_text}")
                             horse_data["weight_diff_raw"] = weight_diff_text # Store raw if parsing fails
                else:
                    horse_data["horse_weight"] = None
                    horse_data["horse_weight_diff"] = None


                # Attempt to extract Win Odds and Popularity from results table
                if len(cells) > 13: # Check if odds/popularity cells exist (indices 12 and 13)
                    horse_data["win_odds"] = clean_text(cells[12].text) # D1.1 (Final odds)
                    horse_data["popularity"] = clean_text(cells[13].text) # D2.1 (Final popularity)
                    logger.debug(f"Extracted odds: {horse_data['win_odds']}, popularity: {horse_data['popularity']}")
                else:
                    horse_data["win_odds"] = None
                    horse_data["popularity"] = None
                    logger.debug(f"Odds/Popularity cells missing for row: {row}")

                # Add more extraction logic for B1 items available in the table

                if "horse_id" in horse_data:  # Only add if we got the ID
                    logger.debug(f"Found horse summary: {horse_data}")
                    horses.append(horse_data)

    except Exception as e:
        logger.error(f"Error scraping horse list: {e}", exc_info=True)
    # Correct indentation for the return statement (align with try block)
    return horses


def scrape_horse_details(horse_id):
    """Scrapes detailed information for a single horse from its profile page."""
    horse_details = {"horse_id": horse_id}
    horse_url = f"{BASE_URL_NETKEIBA}/horse/{horse_id}"
    soup = get_soup(horse_url)
    if not soup:
        logger.warning(f"Could not fetch horse details page for {horse_id}")
        return horse_details  # Return basic ID if page fetch fails

    try:
        # --- Extract Basic Info (B1) ---
        profile_table = soup.find("table", class_="db_prof_table")
        if profile_table and isinstance(profile_table, Tag): # Check if it's a Tag
            rows = profile_table.find_all("tr")
            for row in rows:
                header = row.find("th")
                data = row.find("td") # Corrected indentation
                if header and data:
                    header_text = clean_text(header.text)
                    data_text = clean_text(data.text)
                    # Check header_text is not None before using 'in'
                    if header_text and "生年月日" in header_text:
                        horse_details["birth_date"] = data_text
                    elif header_text and "調教師" in header_text:
                        horse_details["trainer_full"] = data_text  # Often includes affiliation
                    elif header_text and "馬主" in header_text:
                        horse_details["owner"] = data_text
                    elif header_text and "生産者" in header_text:
                        horse_details["producer"] = data_text
                    elif header_text and "産地" in header_text:
                        horse_details["origin"] = data_text
                    elif header_text and "毛色" in header_text: # B1.10
                        horse_details["coat_color"] = data_text
                    elif header_text and "馬主" in header_text: # B1.8
                        horse_details["owner"] = data_text
                    elif header_text and "生産者" in header_text: # B1.9
                        horse_details["producer"] = data_text
                    # Add more B1 items if found in this table
        else:
            logger.warning(f"Profile table 'db_prof_table' not found or not a Tag for horse {horse_id}")

        # --- Extract Pedigree Info (B4 Basic) ---
        blood_table = soup.find("table", class_="blood_table")
        if blood_table and isinstance(blood_table, Tag): # Check if it's a Tag
            rows = blood_table.find_all("tr")
            # Safer access to pedigree data with checks
            if len(rows) > 0:
                cells = rows[0].find_all("td")
                if len(cells) > 0:
                     horse_details["father"] = clean_text(cells[0].text)
            if len(rows) > 1:
                 cells = rows[1].find_all("td")
                 if len(cells) > 0:
                    horse_details["mother"] = clean_text(cells[0].text)
            if len(rows) > 2:
                 cells = rows[2].find_all("td")
                 if len(cells) > 0:
                    horse_details["mother_father"] = clean_text(cells[0].text)
            # Add more B4 items if available directly
        else:
            logger.warning(f"Blood table 'blood_table' not found or not a Tag for horse {horse_id}")

        # --- Extract Recent Results (B3 Summary from Horse Page) ---
        # Note: This table might only show a summary. Detailed past perf needs shutuba_past.
        results_table = soup.find("table", class_="db_h_race_results")
        horse_details["recent_results_summary"] = [] # Rename to avoid conflict with shutuba_past data
        if results_table and isinstance(results_table, Tag): # Check if it's a Tag
            # Correct indentation for this block (should be indented under the if)
            rows = results_table.find_all("tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                # Check length before accessing potentially non-existent cells like cells[11] (Indent this block)
                if len(cells) > 11: # Check if enough cells exist for rank etc.
                    race_name_tag = cells[4].find('a')
                    race_name = clean_text(race_name_tag.text) if race_name_tag else clean_text(cells[4].text)
                    result = {
                         "date": clean_text(cells[0].text),
                         "venue": clean_text(cells[1].text),
                         "weather": clean_text(cells[2].text),
                         "race_number": clean_text(cells[3].text),
                         "race_name": race_name,
                         "rank": clean_text(cells[11].text) # Rank is often further down
                         # Add more B3 summary items like distance, jockey, time diff etc.
                     }
                    logger.debug(f"Added recent result summary for horse {horse_id}: {result}")
                    horse_details["recent_results_summary"].append(result)
                else:
                    logger.debug(f"Skipping row in recent results summary due to insufficient cells: {row}")
        else:
             logger.warning(f"Results table 'db_h_race_results' not found or not a Tag for horse {horse_id}")


    except Exception as e:
        logger.error(f"Error scraping details for horse {horse_id}: {e}", exc_info=True)

    logger.debug(f"Finished scraping details for horse {horse_id}: {horse_details}")
    return horse_details


def scrape_horse_results(horse_id):
    """Scrapes detailed race results and performance data for a horse."""
    logger.info(f"Scraping full results for horse {horse_id}...")
    results_data = {"conditions": {}, "results": []}
    results_url = f"{BASE_URL_NETKEIBA}/horse/result/{horse_id}"
    soup = get_soup(results_url)
    if not soup:
        logger.warning(f"Could not fetch horse results page for {horse_id}")
        return results_data # Return empty data if page fetch fails

    try:
        # --- Extract condition-specific summaries (B2) ---
        logger.debug(f"Looking for condition summary tables (db_prof_table) on {results_url}...")
        summary_tables = soup.find_all("table", class_="db_prof_table")
        condition_summary = {}
        # Typically, the second db_prof_table contains condition summaries. Verify this assumption.
        summary_table_found = False
        if len(summary_tables) > 1:
            summary_table = summary_tables[1] # Adjust index if needed based on actual page structure
            if isinstance(summary_table, Tag):
                summary_table_found = True
                rows = summary_table.find_all("tr")
                current_main_condition = None # e.g., "芝", "距離別"
                logger.info(f"Found {len(rows)} rows in potential condition summary table for horse {horse_id}.")
                for row in rows:
                    header_tag = row.find("th")
                    data_cell = row.find("td") # Usually only one data cell per row

                    if header_tag and data_cell:
                        header_text = clean_text(header_tag.text)
                        data_text = clean_text(data_cell.text)

                        # Check if this row defines a new main condition
                        is_main_condition = header_tag.has_attr('rowspan') or header_text in [
                            "全成績", "芝", "ダート", "距離別", "競馬場別", "馬場状態", "クラス別", "騎手別", "厩舎別", # Add other potential main headers
                            "芝・重賞", "ダート・重賞" # More specific headers often seen
                        ]

                        if is_main_condition:
                            current_main_condition = header_text
                            condition_key = current_main_condition # B2.1, B2.2, B2.3 etc.
                        elif current_main_condition:
                            # This is likely a sub-condition (e.g., "1600m" under "距離別")
                            condition_key = f"{current_main_condition}_{header_text}" # B2.4, B2.5 etc.
                        else:
                            # If no main condition context, use the header itself
                            condition_key = header_text

                        # Parse the performance data like "[1-2-0-5]"
                        perf_match = None
                        if isinstance(data_text, str): # Ensure data_text is a string before regex
                            perf_match = re.search(r"\[(\d+)-(\d+)-(\d+)-(\d+)\]", data_text)

                        if perf_match:
                            condition_summary[condition_key] = {
                                "raw_text": data_text, # Keep original text
                                "wins": int(perf_match.group(1)),
                                "place_2nd": int(perf_match.group(2)),
                                "place_3rd": int(perf_match.group(3)),
                                "other": int(perf_match.group(4)),
                            }
                        else:
                            # Store raw text if parsing fails or no bracketed data
                            condition_summary[condition_key] = {"raw_text": data_text}
                        logger.debug(f"Parsed condition '{condition_key}': {condition_summary[condition_key]}")
                    else:
                        logger.debug(f"Skipping row in condition summary table, missing header or data cell: {row}")

                results_data["conditions"] = condition_summary # Assign the parsed data
                logger.info(f"Extracted {len(condition_summary)} condition summaries for {horse_id}.")
            else:
                 logger.warning(f"Condition summary table (index 1) is not a Tag for horse {horse_id}")
        else:
            logger.warning(f"Could not find enough summary tables (expected > 1, found {len(summary_tables)}) for horse {horse_id}")

        if not summary_table_found:
             logger.warning(f"No suitable condition summary table (db_prof_table at index 1) found on {results_url}")


        # --- Extract detailed race results (B3 extension) ---
        logger.debug("Looking for detailed results table (db_h_race_results nk_tb_common)...")
        results_table = soup.find("table", class_="db_h_race_results nk_tb_common") # More specific selector
        if results_table and isinstance(results_table, Tag):
            rows = results_table.find_all("tr")
        #    for row in rows[1:]: # Skip header
        #        cells = row.find_all("td")
        #        if len(cells) > 20: # Example check
        #             race_result = {
        #                 "date": clean_text(cells[0].text),
        #                 # ... extract all B3 fields ...
        #                 "time_diff": clean_text(cells[12].text), # Example
        #                 "corner_passes": clean_text(cells[15].text), # Example
        #                 "上がり3F": clean_text(cells[19].text), # Example
        #             }
        #             results_data["results"].append(race_result)
        # else:
            for row in rows[1:]: # Skip header
                cells = row.find_all("td")
                # Adjust expected cell count based on the actual table structure
                # Corrected indices based on typical netkeiba horse result table structure
                if len(cells) > 24: # Need at least 25 cells for 賞金 etc.
                     # Extract data based on corrected cell index
                     race_result = {
                         "date": clean_text(cells[0].text),             # 日付
                          "venue": clean_text(cells[1].text),            # 開催
                          "weather": clean_text(cells[2].text),          # 天気
                          "race_number": clean_text(cells[3].text),      # R
                          "race_name": clean_text(cells[4].text),        # レース名
                          "head_count": clean_text(cells[6].text),       # 頭数
                          "waku": clean_text(cells[7].text),             # 枠番
                          "umaban": clean_text(cells[8].text),           # 馬番
                          "odds": clean_text(cells[9].text),             # オッズ
                          "popularity": clean_text(cells[10].text),      # 人気
                          "rank": clean_text(cells[11].text),            # 着順
                          "jockey": clean_text(cells[12].text),          # 騎手
                          "burden_weight": clean_text(cells[13].text),   # 斤量
                          "distance": clean_text(cells[14].text),        # 距離
                          "track_condition": clean_text(cells[15].text), # 馬場
                          # "time_index": clean_text(cells[16].text),    # 指数 - Skip for now
                          "time": clean_text(cells[17].text),            # タイム
                          "time_diff": clean_text(cells[18].text),       # 着差
                          # "prize_money_alt": clean_text(cells[19].text), # ﾀｲﾑ差 - Skip for now
                          "corner_passes": clean_text(cells[20].text),   # 通過
                          "pace": clean_text(cells[21].text),            # ペース
                          "agari_3f": clean_text(cells[22].text),        # 上り
                          "horse_weight": clean_text(cells[23].text),    # 馬体重
                          "prize": clean_text(cells[24].text),           # 賞金 (may need adjustment)
                          # TODO: B3.5 Time diff to 2nd place - often not directly here, might need calculation or different page
                          # Add more fields if needed
                      }
                     # Clean up potentially empty fields
                     race_result = {k: v for k, v in race_result.items() if v}
                     results_data["results"].append(race_result)
                     logger.debug(f"Added detailed result for horse {horse_id}: {race_result}")
                else:
                     logger.debug(f"Skipping row in detailed results due to insufficient cells ({len(cells)}): {row}")
        else:
            logger.warning(f"Detailed results table 'db_h_race_results nk_tb_common' not found or not a Tag for horse {horse_id}")
        # pass # Placeholder removed

    except Exception as e:
        logger.error(f"Error scraping results for horse {horse_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping results for horse {horse_id}.")
    return results_data


def scrape_pedigree(horse_id):
    """Scrapes detailed pedigree information (5 generations, crosses) for a horse."""
    logger.info(f"Scraping pedigree for horse {horse_id}...")
    pedigree_data = {"pedigree_5gen": {}, "crosses": []} # Initialize pedigree_5gen as dict
    pedigree_url = f"{BASE_URL_NETKEIBA}/horse/ped/{horse_id}"
    soup = get_soup(pedigree_url)
    if not soup:
        logger.warning(f"Could not fetch horse pedigree page for {horse_id}")
        return pedigree_data # Return empty data if page fetch fails

    try:
        # --- Extract 5-Generation Pedigree (B4.6) ---
        logger.debug("Looking for 5-generation pedigree table (blood_table)...")
        ped_table = soup.find("table", class_="blood_table")
        pedigree_5gen_data = {} # Use a dictionary to store generations
        if ped_table and isinstance(ped_table, Tag):
            rows = ped_table.find_all("tr")
            # --- Basic Parsing Attempt (Likely needs refinement) ---
            # This assumes a relatively consistent structure which might not hold true.
            # It tries to extract key ancestors based on typical cell positions.
            try:
                # Generation 1 (Parents)
                if len(rows) > 0:
                    cells_g1 = rows[0].find_all("td")
                    if len(cells_g1) > 0 and cells_g1[0].find("a"): pedigree_5gen_data["father"] = {"name": clean_text(cells_g1[0].text), "url": cells_g1[0].find("a").get("href")}
                if len(rows) > 16: # Mother is often much lower due to rowspan
                     cells_g1_mother = rows[16].find_all("td")
                     if len(cells_g1_mother) > 0 and cells_g1_mother[0].find("a"): pedigree_5gen_data["mother"] = {"name": clean_text(cells_g1_mother[0].text), "url": cells_g1_mother[0].find("a").get("href")}

                # Generation 2 (Grandparents)
                if len(rows) > 0: # Father's Father (FF)
                    cells_g2_ff = rows[0].find_all("td")
                    if len(cells_g2_ff) > 1 and cells_g2_ff[1].find("a"): pedigree_5gen_data["father_father"] = {"name": clean_text(cells_g2_ff[1].text), "url": cells_g2_ff[1].find("a").get("href")}
                if len(rows) > 8: # Father's Mother (FM)
                    cells_g2_fm = rows[8].find_all("td")
                    if len(cells_g2_fm) > 0 and cells_g2_fm[0].find("a"): pedigree_5gen_data["father_mother"] = {"name": clean_text(cells_g2_fm[0].text), "url": cells_g2_fm[0].find("a").get("href")}
                if len(rows) > 16: # Mother's Father (MF)
                    cells_g2_mf = rows[16].find_all("td")
                    if len(cells_g2_mf) > 1 and cells_g2_mf[1].find("a"): pedigree_5gen_data["mother_father"] = {"name": clean_text(cells_g2_mf[1].text), "url": cells_g2_mf[1].find("a").get("href")}
                if len(rows) > 24: # Mother's Mother (MM)
                    cells_g2_mm = rows[24].find_all("td")
                    if len(cells_g2_mm) > 0 and cells_g2_mm[0].find("a"): pedigree_5gen_data["mother_mother"] = {"name": clean_text(cells_g2_mm[0].text), "url": cells_g2_mm[0].find("a").get("href")}

                # Generation 3 (Great-Grandparents) - Indices are estimates based on typical structure
                # Father's side
                if len(rows) > 0: # FFF
                    cells_g3_fff = rows[0].find_all("td")
                    if len(cells_g3_fff) > 2 and cells_g3_fff[2].find("a"): pedigree_5gen_data["father_father_father"] = {"name": clean_text(cells_g3_fff[2].text), "url": cells_g3_fff[2].find("a").get("href")}
                if len(rows) > 4: # FFM
                    cells_g3_ffm = rows[4].find_all("td")
                    if len(cells_g3_ffm) > 1 and cells_g3_ffm[1].find("a"): pedigree_5gen_data["father_father_mother"] = {"name": clean_text(cells_g3_ffm[1].text), "url": cells_g3_ffm[1].find("a").get("href")}
                if len(rows) > 8: # FMF
                    cells_g3_fmf = rows[8].find_all("td")
                    if len(cells_g3_fmf) > 1 and cells_g3_fmf[1].find("a"): pedigree_5gen_data["father_mother_father"] = {"name": clean_text(cells_g3_fmf[1].text), "url": cells_g3_fmf[1].find("a").get("href")}
                if len(rows) > 12: # FMM
                    cells_g3_fmm = rows[12].find_all("td")
                    if len(cells_g3_fmm) > 0 and cells_g3_fmm[0].find("a"): pedigree_5gen_data["father_mother_mother"] = {"name": clean_text(cells_g3_fmm[0].text), "url": cells_g3_fmm[0].find("a").get("href")}
                # Mother's side
                if len(rows) > 16: # MFF
                    cells_g3_mff = rows[16].find_all("td")
                    if len(cells_g3_mff) > 2 and cells_g3_mff[2].find("a"): pedigree_5gen_data["mother_father_father"] = {"name": clean_text(cells_g3_mff[2].text), "url": cells_g3_mff[2].find("a").get("href")}
                if len(rows) > 20: # MFM
                    cells_g3_mfm = rows[20].find_all("td")
                    if len(cells_g3_mfm) > 1 and cells_g3_mfm[1].find("a"): pedigree_5gen_data["mother_father_mother"] = {"name": clean_text(cells_g3_mfm[1].text), "url": cells_g3_mfm[1].find("a").get("href")}
                if len(rows) > 24: # MMF
                    cells_g3_mmf = rows[24].find_all("td")
                    if len(cells_g3_mmf) > 1 and cells_g3_mmf[1].find("a"): pedigree_5gen_data["mother_mother_father"] = {"name": clean_text(cells_g3_mmf[1].text), "url": cells_g3_mmf[1].find("a").get("href")}
                if len(rows) > 28: # MMM
                    cells_g3_mmm = rows[28].find_all("td")
                    if len(cells_g3_mmm) > 0 and cells_g3_mmm[0].find("a"): pedigree_5gen_data["mother_mother_mother"] = {"name": clean_text(cells_g3_mmm[0].text), "url": cells_g3_mmm[0].find("a").get("href")}

                # TODO: Extend logic for Generations 4, 5 - Requires even more complex mapping.
                logger.info(f"Partially parsed 5-gen pedigree (attempted Gen 1-3) for horse {horse_id}.")

            except Exception as ped_parse_err:
                logger.error(f"Error during basic pedigree parsing for {horse_id}: {ped_parse_err}", exc_info=True)

            pedigree_data["pedigree_5gen"] = pedigree_5gen_data # Store the parsed data
        else:
            logger.warning(f"Pedigree table 'blood_table' not found or not a Tag for horse {horse_id}")

        # --- Extract Crosses (Inbreeding - B4.7) --- - Moved outside the table check
        logger.debug("Looking for inbreeding information...")
        inbreed_div = soup.find("div", class_="blood_inbreed") # Adjust selector if needed
        if inbreed_div and isinstance(inbreed_div, Tag):
            cross_links = inbreed_div.find_all("a")
            for link in cross_links:
                cross_text = clean_text(link.text)
                if cross_text:
                    pedigree_data["crosses"].append(cross_text)
            logger.debug(f"Found crosses for {horse_id}: {pedigree_data['crosses']}")
        else:
            logger.debug(f"Inbreeding div not found for horse {horse_id}")


    except Exception as e:
        logger.error(f"Error scraping pedigree for horse {horse_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping pedigree for horse {horse_id}.")
    return pedigree_data


def scrape_training(driver, horse_id): # Accept driver as argument
    """Scrapes training information (B5) for a horse using Selenium."""
    logger.info(f"Scraping training info for horse {horse_id}...")
    training_data = {"workouts": []}
    if not driver:
        logger.error("WebDriver not initialized. Cannot scrape training info.")
        return training_data
    training_url = f"{BASE_URL_NETKEIBA}/horse/training/{horse_id}" # Assumed URL structure
    logger.info(f"Fetching training page with Selenium: {training_url}")

    try:
        driver.get(training_url)
        time.sleep(SELENIUM_WAIT_TIME) # Wait for potential dynamic content
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        logger.debug(f"Successfully fetched training page source for horse {horse_id}")

        # --- Extract Training Details (B5.1 - B5.12) ---
        logger.debug(f"Looking for training table (guessed class 'oikiri_table') on {training_url}...")
        # !!! GUESSING SELECTOR: Assumed table class 'oikiri_table'. Needs verification. !!!
        training_table = soup.find("table", class_="oikiri_table") # Example: Common class for training tables

        if training_table and isinstance(training_table, Tag):
            rows = training_table.find_all("tr")
            logger.info(f"Found {len(rows)-1} potential workout rows in training table for {horse_id}.")
            for row in rows[1:]: # Skip header
                cells = row.find_all("td")
                # !!! GUESSING INDICES: Assumed cell order. Needs verification. !!!
                # Example: Date(0), Location(1), Course(2), Condition(3), TotalTime(4), LapTimes(5), Intensity(6), Partner(7)
                if len(cells) > 7: # Check if enough cells exist based on assumption
                    # Combine location/course/condition if needed
                    location_detail = f"{clean_text(cells[1].text)} {clean_text(cells[2].text)} ({clean_text(cells[3].text)})"

                    workout = {
                        "date": clean_text(cells[0].text),              # B5.1, B5.5 (日付)
                        "location_detail": location_detail,             # B5.1, B5.5 (場所, コース, 馬場状態)
                        "time_total": clean_text(cells[4].text),        # B5.2, B5.5 (全体時計)
                        "time_laps": clean_text(cells[5].text),         # B5.3, B5.5 (ラップタイム)
                        "intensity": clean_text(cells[6].text),         # B5.4, B5.5 (強度)
                        "partner_info": clean_text(cells[7].text),      # B5.7 (併せ馬情報)
                        # TODO: Extract other B5 fields if available (e.g., B5.8-B5.12 - comments, form etc. might be elsewhere)
                    }
                    # Clean up potentially empty fields
                    workout = {k: v for k, v in workout.items() if v}
                    training_data["workouts"].append(workout)
                    logger.debug(f"Added workout for {horse_id}: {workout}")
                else:
                    logger.debug(f"Skipping training row due to insufficient cells ({len(cells)}): {row}")
        else:
             logger.warning(f"Training table ('oikiri_table' guess) not found or not a Tag on {training_url} for horse {horse_id}. Needs investigation.")


    except Exception as e:
        logger.error(f"Error scraping training info for horse {horse_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping training info for horse {horse_id}.") # Log moved outside try block
    return training_data


def scrape_odds(race_soup, race_id):
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

def scrape_shutuba_past(driver, race_id):
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
                logger.error(f"Error processing row for umaban {umaban_str if 'umaban_str' in locals() else 'unknown'}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error scraping shutuba_past page {shutuba_url}: {e}", exc_info=True)

    return past_perf_data


def scrape_detailed_race_results(race_id):
    """Scrapes detailed results like lap times from the race result page."""
    logger.info(f"Scraping detailed results (lap times, weather, track details) for race {race_id}...")
    detailed_results_data = {"weather_track_details": {}} # Initialize with sub-dict
    # Construct the URL for the race result page (different from the DB page)
    result_page_url = f"https://race.netkeiba.com/race/result.html?race_id={race_id}"
    soup = get_soup(result_page_url)
    if not soup:
        logger.warning(f"Could not fetch detailed race result page: {result_page_url}")
        return detailed_results_data

    try:
        # --- Extract Weather/Track Details (A3, A4) ---
        logger.debug("Looking for weather/track detail information (RaceData01)...")
        race_data01_div = soup.find("div", class_="RaceData01")
        if race_data01_div and isinstance(race_data01_div, Tag):
            details_text = clean_text(race_data01_div.text)
            logger.debug(f"Found RaceData01 text: {details_text}")
            # Example: "芝:良 / ダート:稍重  天候:晴  芝:良  発走時間:15:40" - This is often less detailed
            # Look for more specific elements if available, e.g., within spans or specific classes
            # This section on the result page might be less detailed than desired.
            # Let's store the raw text for now.
            detailed_results_data["weather_track_details"]["summary_text"] = details_text

            # Attempt to parse common patterns (might be redundant with scrape_race_info but good fallback)
            # Add check to ensure details_text is a string before searching
            if isinstance(details_text, str):
                weather_match = re.search(r"天候:(\S+)", details_text)
                if weather_match:
                    detailed_results_data["weather_track_details"]["weather"] = weather_match.group(1) # A3.6

                condition_match_shiba = re.search(r"芝:(\S+)", details_text)
                if condition_match_shiba:
                     detailed_results_data["weather_track_details"]["track_condition_shiba"] = condition_match_shiba.group(1) # A4.1

                condition_match_dirt = re.search(r"ダート:(\S+)", details_text)
                if condition_match_dirt:
                     detailed_results_data["weather_track_details"]["track_condition_dirt"] = condition_match_dirt.group(1) # A4.1
            else:
                logger.warning(f"RaceData01 details_text was not a string, skipping regex search for race {race_id}")

            # --- TODO: Look for more specific A3/A4 items if present ---
            # e.g., Temperature, Wind, Cushion Value, Moisture - These might be in different divs or require JRA site scraping.
            # logger.debug("Searching for specific weather/track elements...")
            # temp_span = soup.find(...)
            # if temp_span: detailed_results_data["weather_track_details"]["temperature"] = clean_text(temp_span.text) # A3.6
            # cushion_span = soup.find(...)
            # if cushion_span: detailed_results_data["weather_track_details"]["cushion_value"] = clean_text(cushion_span.text) # A4.4

        else:
            logger.warning(f"Could not find weather/track details section ('div.RaceData01') on page: {result_page_url}")


        # --- Extract Lap Times (B3.9) ---
        logger.debug("Looking for lap time information (RaceData02)...")
        lap_time_div = soup.find("div", class_="RaceData02") # Common location for lap/pace data
        if lap_time_div and isinstance(lap_time_div, Tag):
             # Lap times (B3.9)
             lap_time_dd = lap_time_div.find("dd", class_="LapTime")
             lap_time_dd = lap_time_div.find("dd", class_="LapTime")
             if lap_time_dd and isinstance(lap_time_dd, Tag):
                 lap_spans = lap_time_dd.find_all("span")
                 laps_raw = [clean_text(span.text) for span in lap_spans]
                 laps_filtered = [lap for lap in laps_raw if lap]
                 if laps_filtered:
                     detailed_results_data["lap_times"] = "-".join(laps_filtered)
                     logger.info(f"Found lap times: {detailed_results_data['lap_times']}")
                 else:
                     logger.warning(f"Found LapTime dd but no valid lap spans inside for race {race_id}")
             else:
                 logger.warning(f"Could not find 'dd.LapTime' within 'div.RaceData02' for race {race_id}")

             # Extract Pace (B3.10) - Often in the same RaceData02 div
             pace_container = lap_time_div # Check within the same div first
             # Pace might be in <dd class="Pace"> or similar structure
             # Example: <dt>ペース</dt><dd><span>34.7</span>-<span>36.0</span>-<span>34.8</span></dd>
             pace_dt = pace_container.find("dt", string=re.compile("ペース"))
             if pace_dt:
                 pace_dd = pace_dt.find_next_sibling("dd")
                 if pace_dd and isinstance(pace_dd, Tag): # Add Tag check
                     # Add assert for Pylance check (line 1107)
                     assert isinstance(pace_dd, Tag), f"Type check failed unexpectedly for pace_dd: {type(pace_dd)}"
                     pace_spans = pace_dd.find_all("span")
                     paces_raw = [clean_text(span.text) for span in pace_spans]
                     paces_filtered = [p for p in paces_raw if p]
                     if paces_filtered:
                         # Store individual pace segments if available (e.g., first 3F, mid, last 3F)
                         detailed_results_data["pace_segments"] = "-".join(paces_filtered)
                         logger.info(f"Found pace segments: {detailed_results_data['pace_segments']}")
                         # Basic Pace Judgment (B3.10) - Infer from first/last segments if possible (heuristic)
                         try:
                             first_pace = float(paces_filtered[0])
                             last_pace = float(paces_filtered[-1])
                             # Very basic heuristic: Faster finish -> likely Slower pace overall, Faster start -> likely Faster pace
                             # Ensure the target dictionary exists before assignment
                             if "weather_track_details" not in detailed_results_data:
                                 detailed_results_data["weather_track_details"] = {} # Initialize if missing

                             # Assign to the correct sub-dictionary
                             if last_pace < first_pace - 1.0: # Significantly faster finish
                                 detailed_results_data["weather_track_details"]["pace_judgment_heuristic"] = "Slow"
                             elif first_pace < last_pace - 1.0: # Significantly faster start
                                 detailed_results_data["weather_track_details"]["pace_judgment_heuristic"] = "High"
                             else:
                                 detailed_results_data["weather_track_details"]["pace_judgment_heuristic"] = "Middle"
                             logger.info(f"Heuristic pace judgment: {detailed_results_data['weather_track_details']['pace_judgment_heuristic']}")
                         except (ValueError, IndexError, TypeError): # Added TypeError for float conversion
                             logger.warning(f"Could not calculate heuristic pace judgment for race {race_id}")
                     else:
                          logger.warning(f"Found Pace dt/dd but no pace spans inside for race {race_id}")
                 else:
                     logger.warning(f"Found Pace dt but no following dd for race {race_id}")
             else:
                 logger.debug(f"Pace dt not found in RaceData02 for race {race_id}")

        else:
            logger.warning(f"Could not find lap time/pace section ('div.RaceData02') on page: {result_page_url}")

    except Exception as e:
        logger.error(f"Error scraping detailed race results page for {race_id}: {e}", exc_info=True)

    # --- Extract Time Differences (B3.4, B3.5) from Result Table ---
    logger.debug(f"Looking for main results table (RaceTable01) on {result_page_url}...")
    results_table = soup.find("table", class_="RaceTable01")
    time_diffs_by_umaban = {}
    if results_table and isinstance(results_table, Tag):
        rows = results_table.find_all("tr")
        logger.info(f"Found {len(rows)-1} rows in main results table for time diff extraction.")
        for row in rows[1:]: # Skip header
            cells = row.find_all("td")
            # Indices need verification: Umaban(2), TimeDiff(8) are common guesses
            if len(cells) > 8:
                try:
                    umaban_str = clean_text(cells[2].text)
                    time_diff_str = clean_text(cells[8].text) # 着差 column

                    if umaban_str and umaban_str.isdigit():
                        umaban = int(umaban_str)
                        # Store the raw time diff string (e.g., "クビ", "ハナ", "1.1/2", "0.0", "-0.1")
                        time_diffs_by_umaban[umaban] = time_diff_str
                        logger.debug(f"Extracted time_diff '{time_diff_str}' for umaban {umaban}")
                    else:
                        logger.warning(f"Could not parse umaban from cell 2: {cells[2].text}")
                except (IndexError, ValueError, TypeError) as e:
                    logger.warning(f"Error processing row for time diff: {row}. Error: {e}")
            else:
                logger.debug(f"Skipping row in main results table due to insufficient cells ({len(cells)}) for time diff.")
        # Add the extracted time diffs to the data dictionary
        detailed_results_data["time_diffs"] = time_diffs_by_umaban
    else:
        logger.warning(f"Could not find main results table ('table.RaceTable01') on page: {result_page_url}")


    logger.info(f"Finished scraping detailed results page for race {race_id}.")
    return detailed_results_data


def scrape_jockey_profile(jockey_id):
    """Scrapes profile information for a jockey (placeholder)."""
    logger.info(f"Scraping profile for jockey {jockey_id}...")
    jockey_data = {"jockey_id": jockey_id, "profile": {}, "stats": {}} # Initialize with profile and stats keys
    profile_url = f"{BASE_URL_NETKEIBA}/jockey/profile/{jockey_id}" # Assumed URL
    soup = get_soup(profile_url)
    if not soup:
        logger.warning(f"Could not fetch jockey profile page: {profile_url}")
        return jockey_data

    try:
        # --- Extract Basic Profile Info ---
        logger.debug(f"Looking for jockey profile table (db_prof_table) on {profile_url}...")
        profile_table = soup.find("table", class_="db_prof_table")
        if profile_table and isinstance(profile_table, Tag):
            # Correct indentation for this block
            rows = profile_table.find_all("tr")
            for row in rows:
                header = row.find("th")
                data = row.find("td") # Corrected indentation
                if header and data:
                    header_text = clean_text(header.text)
                    data_text = clean_text(data.text) # Corrected indentation
                    if header_text: # Check header_text is not None
                        # Store basic profile info like name, affiliation, etc.
                         jockey_data["profile"][header_text] = data_text
                         logger.debug(f"Jockey Profile: Found '{header_text}': '{data_text}'")
        else:
             logger.warning(f"Could not find profile table (db_prof_table) for jockey {jockey_id}")

        # --- Extract Jockey Stats (C1.2 - C1.7) ---
        # Stats are often in subsequent tables. Let's look for tables with class 'race_table_01' or similar.
        logger.debug(f"Looking for jockey stats tables (e.g., race_table_01 nk_tb_common) on {profile_url}...")
        stats_tables = soup.find_all("table", class_=re.compile(r"race_table_01|nk_tb_common")) # Find potential stats tables

        if not stats_tables:
             logger.warning(f"Could not find any potential stats tables for jockey {jockey_id}")

        for table in stats_tables:
            if not isinstance(table, Tag): continue # Skip if not a Tag

            # Identify table type by caption or preceding header if possible
            caption = table.find("caption")
            table_title = clean_text(caption.text) if caption else "Unknown Stats Table"
            logger.debug(f"Processing stats table: '{table_title}'")

            # Heuristic: Assume tables with headers like '年度', '競馬場', 'コース' contain relevant stats
            header_row = table.find("tr")
            if not header_row: continue
            headers = [clean_text(th.text) for th in header_row.find_all("th")]

            # Example: Parsing a yearly summary table
            if "年度" in headers and "勝率" in headers and "連対率" in headers:
                logger.debug(f"Parsing yearly summary table: {headers}")
                jockey_data["stats"]["yearly_summary"] = []
                body = table.find("tbody")
                if body and isinstance(body, Tag):
                    # Correct indentation for this block (should be indented under the if)
                    assert isinstance(body, Tag), f"Type check failed unexpectedly for body: {type(body)}"
                    # Add another explicit check before find_all for Pylance
                    if isinstance(body, Tag):
                        rows = body.find_all("tr") # Line 1208
                    else:
                        logger.error(f"tbody in yearly summary table is not a Tag object for jockey {jockey_id}, cannot find rows.")
                        continue # Skip this table if tbody is invalid

                    for row in rows: # Indent this loop
                        cells = row.find_all("td") # Indent this block
                        if len(cells) >= len(headers): # Basic check # Indent this block
                            year_data = {headers[i]: clean_text(cells[i].text) for i in range(len(headers))}
                            jockey_data["stats"]["yearly_summary"].append(year_data)
                            logger.debug(f"  Added yearly data: {year_data}")
                else:
                    logger.warning(f"Could not find tbody in yearly summary table for jockey {jockey_id}")

            # Example: Parsing a course/venue summary table
            elif ("競馬場" in headers or "コース" in headers) and "勝率" in headers:
                logger.debug(f"Parsing venue/course summary table: {headers}")
                table_key = f"summary_{headers[0].lower()}" # e.g., summary_競馬場, summary_コース
                jockey_data["stats"][table_key] = []
                body = table.find("tbody")
                if body and isinstance(body, Tag):
                    rows = body.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= len(headers):
                            item_data = {headers[i]: clean_text(cells[i].text) for i in range(len(headers))}
                            jockey_data["stats"][table_key].append(item_data)
                            logger.debug(f"  Added {table_key} data: {item_data}")
                else:
                    logger.warning(f"Could not find tbody in {table_key} table for jockey {jockey_id}")

            # Add more parsing logic for other table types (track condition, distance, etc.) based on headers

    except Exception as e:
        logger.error(f"Error scraping jockey profile for {jockey_id}: {e}", exc_info=True)


    logger.info(f"Finished scraping profile for jockey {jockey_id}.")
    return jockey_data


def scrape_trainer_profile(trainer_id):
    """Scrapes profile information for a trainer (placeholder)."""
    logger.info(f"Scraping profile for trainer {trainer_id}...")
    trainer_data = {"trainer_id": trainer_id, "profile": {}, "stats": {}} # Initialize with profile and stats keys
    profile_url = f"{BASE_URL_NETKEIBA}/trainer/profile/{trainer_id}" # Assumed URL
    soup = get_soup(profile_url)
    if not soup:
        logger.warning(f"Could not fetch trainer profile page: {profile_url}")
        return trainer_data

    try:
        # --- Extract Basic Profile Info ---
        logger.debug(f"Looking for trainer profile table (db_prof_table) on {profile_url}...")
        profile_table = soup.find("table", class_="db_prof_table")
        if profile_table and isinstance(profile_table, Tag):
            rows = profile_table.find_all("tr")
            for row in rows:
                header = row.find("th")
                data = row.find("td")
                if header and data:
                    header_text = clean_text(header.text)
                    data_text = clean_text(data.text)
                    if header_text: # Check header_text is not None
                        # Store basic profile info like name, affiliation, etc.
                        trainer_data["profile"][header_text] = data_text
                        logger.debug(f"Trainer Profile: Found '{header_text}': '{data_text}'")
        else:
            logger.warning(f"Could not find profile table (db_prof_table) for trainer {trainer_id}")

        # --- Extract Trainer Stats (C2.2 - C2.7) ---
        # Similar to jockey, stats are often in subsequent tables.
        logger.debug(f"Looking for trainer stats tables (e.g., race_table_01 nk_tb_common) on {profile_url}...")
        stats_tables = soup.find_all("table", class_=re.compile(r"race_table_01|nk_tb_common")) # Find potential stats tables

        if not stats_tables:
             logger.warning(f"Could not find any potential stats tables for trainer {trainer_id}")

        for table in stats_tables:
            if not isinstance(table, Tag): continue # Skip if not a Tag

            caption = table.find("caption")
            table_title = clean_text(caption.text) if caption else "Unknown Stats Table"
            logger.debug(f"Processing stats table: '{table_title}'")

            header_row = table.find("tr")
            if not header_row: continue
            headers = [clean_text(th.text) for th in header_row.find_all("th")]

            # Example: Parsing a yearly summary table
            if "年度" in headers and "勝率" in headers and "連対率" in headers:
                logger.debug(f"Parsing yearly summary table: {headers}")
                trainer_data["stats"]["yearly_summary"] = []
                body = table.find("tbody")
                if body and isinstance(body, Tag):
                    rows = body.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= len(headers):
                            year_data = {headers[i]: clean_text(cells[i].text) for i in range(len(headers))}
                            trainer_data["stats"]["yearly_summary"].append(year_data)
                            logger.debug(f"  Added yearly data: {year_data}")
                else:
                    logger.warning(f"Could not find tbody in yearly summary table for trainer {trainer_id}")

            # Example: Parsing a course/venue/condition summary table
            elif headers and ("競馬場" in headers or "コース" in headers or "芝・ダート" in headers or "距離" in headers or "馬場状態" in headers) and "勝率" in headers:
                # Check if headers[0] is not None and not empty before calling lower()
                first_header = headers[0] if headers else None # Get first header safely
                if first_header: # Check if first_header is truthy (not None, not empty string)
                    # Ensure first_header is not None before calling lower()
                    table_key_base = first_header.lower().replace("・", "_") if first_header else "unknown_header" # e.g., 競馬場 -> 競馬場, 芝・ダート -> 芝_ダート
                    table_key = f"summary_{table_key_base}"
                    logger.debug(f"Parsing {table_key} summary table: {headers}")
                    trainer_data["stats"][table_key] = []
                    # This block should be indented to be part of the 'if first_header:' (Corrected indentation below)
                    body = table.find("tbody")
                    if body and isinstance(body, Tag):
                        # Add assert for Pylance check (line 1295)
                        assert isinstance(body, Tag), f"Type check failed unexpectedly for body: {type(body)}"
                        # Add another explicit check before find_all for Pylance
                        if isinstance(body, Tag):
                            rows = body.find_all("tr") # Line 1317
                            for row in rows: # Moved loop inside the 'if' block
                                cells = row.find_all("td")
                                if len(cells) >= len(headers): # Corrected indentation
                                    item_data = {headers[i]: clean_text(cells[i].text) for i in range(len(headers))}
                                    trainer_data["stats"][table_key].append(item_data)
                                    logger.debug(f"  Added {table_key} data: {item_data}")
                        else:
                            logger.error(f"tbody in {table_key} table is not a Tag object for trainer {trainer_id}, cannot find rows.")
                            # Removed the misplaced 'continue' from the previous attempt
                    else: # This else corresponds to 'if body and isinstance(body, Tag):'
                        logger.warning(f"Could not find tbody in {table_key} table for trainer {trainer_id}")
                else:
                    logger.warning(f"Skipping stats table parsing because first header was None or empty: {headers}")
                    continue # Skip this table if the first header is invalid

            # Add more parsing logic for other table types if needed

    except Exception as e:
        logger.error(f"Error scraping trainer profile for {trainer_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping profile for trainer {trainer_id}.")
    return trainer_data


def scrape_live_odds(driver, race_id): # Accept driver instance
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
                            horse_name = clean_text(cells[1].find("span", class_="HorseName").text) if cells[1].find("span", class_="HorseName") else None
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


# --- Main Execution ---


def main(race_id):
    """Main function to orchestrate the scraping process."""
    logger.info(f"Starting scraping for race_id: {race_id}")
    driver = None # Initialize driver to None
    try: # Add the main try block here
        driver = initialize_driver() # Initialize WebDriver

        # 1. Scrape Race Page (using requests)
        race_url = f"{BASE_URL_NETKEIBA}/race/{race_id}"
        logger.info(f"Fetching race page: {race_url}")
        race_soup = get_soup(race_url)
        if not race_soup:
            logger.error("Failed to fetch race page. Exiting.")
            return
        # return # This was causing the script to exit prematurely

        # 2. Extract Race Info from race page soup
        logger.info("Extracting race info...")
        race_data = scrape_race_info(race_soup, race_id)

        # 3. Extract Horse List from race page soup
        logger.info("Extracting horse list...")
        horses_summary = scrape_horse_list(race_soup)
        if not horses_summary:
            logger.error("Failed to extract horse list. Exiting.")
            # if driver: driver.quit() # Quit driver if exiting early - moved to finally
            return

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
                details = scrape_horse_details(horse_sum["horse_id"])
                # Merge details into summary, prioritizing details if keys overlap (shouldn't much)
                merged_details.update(details)

                # --- Call new scraping functions ---
                horse_results = scrape_horse_results(horse_sum["horse_id"])
                merged_details["full_results_data"] = horse_results # Add results under a new key

                # Call scrape_pedigree and merge
                pedigree_data = scrape_pedigree(horse_sum["horse_id"])
                merged_details["pedigree_data"] = pedigree_data

                # Call scrape_training and merge (pass driver)
                training_data = scrape_training(driver, horse_sum["horse_id"])
                merged_details["training_data"] = training_data

                # Call jockey/trainer profile scrapers if IDs exist
                if merged_details.get("jockey_id"):
                    jockey_profile_data = scrape_jockey_profile(merged_details["jockey_id"])
                    merged_details["jockey_profile"] = jockey_profile_data # Add under new key
                if merged_details.get("trainer_id"):
                     trainer_profile_data = scrape_trainer_profile(merged_details["trainer_id"])
                     merged_details["trainer_profile"] = trainer_profile_data # Add under new key

            else:
                logger.warning(f"  Skipping horse details, results, pedigree, training, jockey/trainer profiles fetch for horse {i+1} due to missing ID.")

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


        race_data["horses"] = all_horse_details # Assign horse details before merging time diffs

        # 6. Scrape Detailed Race Results (Lap Times, Time Diffs etc.)
        logger.info("Scraping detailed race results (lap times, time diffs)...")
        detailed_results = scrape_detailed_race_results(race_id)
        # Extract time diffs before merging the rest
        time_diffs = detailed_results.pop("time_diffs", {})
        race_data.update(detailed_results) # Merge lap times, weather etc. into main race_data

        # Merge Time Diffs into horse data
        logger.info("Merging time differences into horse data...")
        for horse_detail in race_data["horses"]: # Iterate through the list already in race_data
            try:
                umaban_int = int(horse_detail.get("umaban", 0))
                if umaban_int in time_diffs:
                    # Add the time difference from the main results page
                    # Use a distinct key to avoid overwriting time_diff from horse results page
                    horse_detail["time_diff_result_page"] = time_diffs[umaban_int] # B3.4
                    logger.debug(f"Merged time_diff '{time_diffs[umaban_int]}' for umaban {umaban_int}")
                else:
                    logger.debug(f"No time diff data found for umaban {umaban_int} on results page.")
            except (ValueError, TypeError):
                logger.warning(f"Could not convert umaban '{horse_detail.get('umaban')}' to int for merging time diff.")


        # 7. Scrape Live Odds (using Selenium driver)
        logger.info("Scraping live odds...")
        live_odds = scrape_live_odds(driver, race_id) # Pass driver instance
        race_data["live_odds_data"] = live_odds # Add live odds under new key

        # 8. Extract Payout Info (from main race page soup - already scraped)
        logger.info("Extracting payout info (from earlier race page scrape)...")
        # Payouts are scraped earlier via scrape_odds using race_soup
        # Ensure the key name is consistent if needed, e.g., race_data["payouts"] = race_data.pop("odds_payouts", {}).get("payouts", {})
        # Let's keep it as race_data["odds_payouts"] for now as set previously.

        # 9. Save to JSON
        output_filename = f"race_data_{race_id}.json"
        logger.info(f"Saving data to {output_filename}...")
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(race_data, f, ensure_ascii=False, indent=2)
            logger.info("Data saved successfully.")
        except IOError as e:
            logger.error(f"Error saving file {output_filename}: {e}")
        except Exception as e:
                logger.error(f"An unexpected error occurred during file saving: {e}", exc_info=True)
    # Removed redundant outer except block, finally handles cleanup
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
