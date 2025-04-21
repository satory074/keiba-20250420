"""
Scraping functions related to jockey profiles and statistics.
"""
import re
from bs4 import Tag

# Import shared utilities and config
from utils import get_soup, clean_text
from logger_config import get_logger
from config import BASE_URL_NETKEIBA

# Get logger instance
logger = get_logger(__name__)


def scrape_jockey_profile(jockey_id):
    """Scrapes profile information for a jockey."""
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
            if not header_row or not isinstance(header_row, Tag): continue # Add Tag check
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
            elif headers and ("競馬場" in headers or "コース" in headers) and "勝率" in headers: # Check headers is not empty
                logger.debug(f"Parsing venue/course summary table: {headers}")
                first_header = headers[0] # Get the first header
                if isinstance(first_header, str) and first_header: # Check if it's a non-empty string
                    table_key = f"summary_{first_header.lower()}" # e.g., summary_競馬場, summary_コース
                else:
                    logger.warning(f"Could not determine table key from first header: {first_header}. Skipping this stats table.")
                    continue # Skip this table if the key cannot be determined

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
