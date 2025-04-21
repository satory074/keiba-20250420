"""
Scraping functions related to horse information, results, pedigree, and training.
"""
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.remote.webdriver import WebDriver # Import WebDriver for type hinting

# Import shared utilities and config
from utils import get_soup, clean_text
from logger_config import get_logger
from config import BASE_URL_NETKEIBA, SELENIUM_WAIT_TIME

# Get logger instance
logger = get_logger(__name__)


def scrape_horse_list(soup: BeautifulSoup):
    """Scrapes the list of horses and their IDs from the race page soup."""
    horses = []
    try:
        # Corrected selector based on HTML analysis and blog post reference
        logger.debug("Searching for horse list table with classes 'race_table_01 nk_tb_common'")
        race_table = soup.find("table", class_="race_table_01 nk_tb_common")
        if not race_table:
            title_tag = soup.find('title')
            race_title = clean_text(title_tag.text) if title_tag else 'Unknown Race'
            logger.warning(f"Horse list table 'race_table_01 nk_tb_common' not found for race {race_title}.")
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


def scrape_training(driver: WebDriver, horse_id: str): # Accept driver as argument and add type hints
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
