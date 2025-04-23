"""
Scraping functions related to trainer profiles and statistics.
"""
import re
from bs4 import Tag

# Import shared utilities and config
from utils import get_soup, clean_text
from logger_config import get_logger
from config import BASE_URL_NETKEIBA

# Get logger instance
logger = get_logger(__name__)


def scrape_trainer_profile(trainer_id):
    """Scrapes profile information for a trainer."""
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
            if not header_row or not isinstance(header_row, Tag): continue # Add Tag check
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
                if isinstance(first_header, str) and first_header: # Check if first_header is truthy (not None, not empty string)
                    # Ensure first_header is not None before calling lower()
                    table_key_base = first_header.lower().replace("・", "_") # e.g., 競馬場 -> 競馬場, 芝・ダート -> 芝_ダート
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

            # --- Add parsing for other specific table types ---

            # Rotation Summary (C2.6) - Header guess: "ローテーション" or "間隔"
            elif headers and ("ローテーション" in headers or "間隔" in headers) and "勝率" in headers:
                logger.debug(f"Parsing rotation summary table: {headers}")
                table_key = "summary_rotation"
                trainer_data["stats"][table_key] = []
                body = table.find("tbody")
                if body and isinstance(body, Tag):
                    rows = body.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= len(headers):
                            item_data = {headers[i]: clean_text(cells[i].text) for i in range(len(headers))}
                            trainer_data["stats"][table_key].append(item_data)
                            logger.debug(f"  Added {table_key} data: {item_data}")
                else:
                    logger.warning(f"Could not find tbody in {table_key} table for trainer {trainer_id}")

            # Class Summary (C2.7) - Header guess: "クラス" or "条件"
            elif headers and ("クラス" in headers or "条件" in headers) and "勝率" in headers:
                logger.debug(f"Parsing class summary table: {headers}")
                table_key = "summary_class"
                trainer_data["stats"][table_key] = []
                body = table.find("tbody")
                if body and isinstance(body, Tag):
                    rows = body.find_all("tr")
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= len(headers):
                            item_data = {headers[i]: clean_text(cells[i].text) for i in range(len(headers))}
                            trainer_data["stats"][table_key].append(item_data)
                            logger.debug(f"  Added {table_key} data: {item_data}")
                else:
                    logger.warning(f"Could not find tbody in {table_key} table for trainer {trainer_id}")

            # Add more parsing logic for other table types if needed

        # --- Extract Stable Comments (C2.9) ---
        # !!! SELECTOR VERIFICATION NEEDED: Common patterns include divs with class 'Comment' or similar. !!!
        logger.debug("Looking for stable comments section...")
        # Comments might be associated with the profile or recent news sections
        comment_section = soup.find("div", class_=re.compile("comment", re.IGNORECASE)) # General guess
        trainer_data["comments"] = [] # Initialize comments list
        if comment_section and isinstance(comment_section, Tag):
            # Comments might be in <p> tags or list items <li>
            comments = comment_section.find_all(['p', 'li'])
            if comments:
                for comment in comments:
                    comment_text = clean_text(comment.text)
                    if comment_text:
                        trainer_data["comments"].append(comment_text)
                logger.info(f"Found {len(trainer_data['comments'])} potential stable comments for trainer {trainer_id}.")
            else:
                # Fallback: get all text if specific tags not found
                comment_text = clean_text(comment_section.text)
                if comment_text:
                    trainer_data["comments"].append(comment_text)
                    logger.info(f"Found comment section text (fallback) for trainer {trainer_id}.")
        else:
            logger.debug(f"Comment section (guessed class 'comment') not found for trainer {trainer_id}.")


    except Exception as e:
        logger.error(f"Error scraping trainer profile for {trainer_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping profile for trainer {trainer_id}.")
    return trainer_data
