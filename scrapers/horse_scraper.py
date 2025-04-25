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
    
    # Check if soup is None or not a BeautifulSoup object
    if soup is None:
        logger.error("Cannot scrape horse list: soup is None")
        return horses
    
    if not isinstance(soup, BeautifulSoup):
        logger.error(f"Cannot scrape horse list: soup is not a BeautifulSoup object, got {type(soup)}")
        return horses
        
    try:
        logger.debug("Searching for horse list table with multiple possible class names")
        race_table = None
        
        all_tables = soup.find_all("table")
        for table in all_tables:
            # Check if this is a horse table by looking for horse links
            if table.find("a", href=re.compile(r"/horse/\d+")):
                race_table = table
                logger.debug(f"Found horse list table with horse links")
                break
        
        # If not found, try with specific class names
        if not race_table:
            for table_class in ["Shutuba_Table", "race_table_01 nk_tb_common", "RaceTable01", "ShutsubaTable", 
                            "Shutuba_Table", "ShutubaTable", "RaceList_Table", "RaceCard_Table", 
                            "Shutuba_Past5_Table", "RaceList01", "ShutubaTable"]:
                race_table = soup.find("table", class_=table_class)
                if race_table:
                    logger.debug(f"Found horse list table with class '{table_class}'")
                    break
                    
            # If not found by exact class, try with partial class name
            if not race_table:
                for table in soup.find_all("table"):
                    if table.get("class") and any(cls.lower() in ["shutuba", "shutouba", "shutsuba", "race_table", "racetable"] for cls in table.get("class")):
                        race_table = table
                        logger.debug(f"Found horse list table with partial class match: {table.get('class')}")
                        break
        
        # Try regex match if no table found by exact class name
        if not race_table:
            race_table = soup.find("table", class_="ShutubaTable")
            if race_table:
                logger.debug("Found horse list table with exact class 'ShutubaTable'")
            else:
                race_table = soup.find("table", class_=re.compile(r"RaceTable|ShutsubaTable|Shutuba|Race_Table"))
                if race_table:
                    logger.debug("Found horse list table with regex class match")
        
        # Try to find the table by structure if still not found
        if not race_table:
            # First check for tables with horse links
            for table in soup.find_all("table"):
                if table.find("a", href=re.compile(r"/horse/\d+")):
                    race_table = table
                    logger.debug("Found horse list table by searching for horse links")
                    break
                
                # Check if table has umaban column
                header_row = table.find("tr")
                if header_row:
                    header_cells = header_row.find_all(["th", "td"])
                    header_texts = [clean_text(cell.text) for cell in header_cells]
                    if any(text in header_texts for text in ["馬番", "枠番", "Num", "番", "Horse", "馬名"]):
                        race_table = table
                        logger.debug(f"Found horse list table by header texts: {header_texts}")
                        break
            
            # Try to find table by looking for specific structure in the page
            if not race_table:
                candidate_tables = []
                for table in soup.find_all("table"):
                    rows = table.find_all("tr")
                    if len(rows) > 5:  # Reasonable number of horses
                        # Check if this table has numbered rows (likely horse numbers)
                        numbered_rows = 0
                        for row in rows[1:]:  # Skip header
                            cells = row.find_all(["td", "th"])
                            if len(cells) > 1:
                                # Check if first or second cell contains a number
                                first_cell = cells[0].text.strip() if cells[0].text else ""
                                second_cell = cells[1].text.strip() if cells[1].text else ""
                                if (re.match(r'^\d+$', first_cell) or 
                                    re.match(r'^\d+$', second_cell)):
                                    numbered_rows += 1
                        
                        if numbered_rows > 5:  # If at least 5 rows have numbers
                            candidate_tables.append((table, numbered_rows))
                
                candidate_tables.sort(key=lambda x: x[1], reverse=True)
                if candidate_tables:
                    race_table = candidate_tables[0][0]
                    logger.debug(f"Found horse list table with {candidate_tables[0][1]} numbered rows")
                
            if not race_table:
                for table in soup.find_all("table"):
                    rows = table.find_all("tr")
                    if len(rows) > 5:  # Reasonable number of horses
                        first_data_row = rows[1] if len(rows) > 1 else None
                        if first_data_row:
                            cells = first_data_row.find_all(["td", "th"])
                            # Check if first or second cell contains a number (likely umaban)
                            if len(cells) > 1:
                                first_cell_text = clean_text(cells[0].text)
                                second_cell_text = clean_text(cells[1].text)
                                if (re.match(r'^\d+$', first_cell_text) or 
                                    re.match(r'^\d+$', second_cell_text)):
                                    race_table = table
                                    logger.debug("Found horse list table by numbered rows")
                                    break
        
        if race_table:
            rows = race_table.find_all("tr")
            logger.debug(f"Found {len(rows)} rows in horse list table")
            
            start_idx = 1 if len(rows) > 1 and rows[0].find("th") else 0
            
            for row in rows[start_idx:]:
                horse_data = {}
                
                # Extract cells
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:  # Basic validation
                    continue
                
                # Extract umaban (horse number)
                umaban_cell = None
                for i, cell in enumerate(cells):
                    if cell.find("div", class_=re.compile(r"Num|Waku|HorseNum")):
                        umaban_cell = cell
                        break
                    elif i == 0 or i == 1:  # Usually in first or second column
                        cell_text = clean_text(cell.text)
                        if cell.text and re.match(r'^\d+$', cell_text):
                            umaban_cell = cell
                            break
                        elif cell.has_attr('data-sort-value') and re.match(r'^\d+$', cell['data-sort-value']):
                            umaban_cell = cell
                            break
                
                if umaban_cell:
                    # Try to get umaban from data-sort-value first
                    if umaban_cell.has_attr('data-sort-value'):
                        horse_data["umaban"] = umaban_cell['data-sort-value']
                    else:
                        horse_data["umaban"] = clean_text(umaban_cell.text)
                
                # Extract horse name and ID
                horse_link = row.find("a", href=re.compile(r"/horse/\d+"))
                if horse_link:
                    horse_data["horse_name"] = clean_text(horse_link.text)
                    horse_id_match = re.search(r"/horse/(\d+)", horse_link["href"])
                    if horse_id_match:
                        horse_data["horse_id"] = horse_id_match.group(1)
                
                # Extract jockey name and ID
                jockey_link = row.find("a", href=re.compile(r"/jockey/\d+"))
                if jockey_link:
                    horse_data["jockey"] = clean_text(jockey_link.text)
                    jockey_id_match = re.search(r"/jockey/(\d+)", jockey_link["href"])
                    if jockey_id_match:
                        horse_data["jockey_id"] = jockey_id_match.group(1)
                
                # Extract trainer name and ID
                trainer_link = row.find("a", href=re.compile(r"/trainer/\d+"))
                if trainer_link:
                    horse_data["trainer"] = clean_text(trainer_link.text)
                    trainer_id_match = re.search(r"/trainer/(\d+)", trainer_link["href"])
                    if trainer_id_match:
                        horse_data["trainer_id"] = trainer_id_match.group(1)
                
                # Extract sex and age with enhanced detection
                sex_age_cell = None
                for i, cell in enumerate(cells):
                    if cell.find("span", class_=re.compile(r"Sex|Age")):
                        sex_age_cell = cell
                        logger.debug(f"Found sex/age cell with span.Sex|Age: {clean_text(cell.text)}")
                        break
                    elif len(cells) > 3 and i == 2:  # Usually in third column
                        text = clean_text(cell.text)
                        if re.match(r'^[牡牝セ]\d+$', text):  # Pattern like "牡3" (male 3yo)
                            sex_age_cell = cell
                            logger.debug(f"Found sex/age cell in column 3: {text}")
                            break
                
                # If not found in the usual places, try all cells
                if not sex_age_cell:
                    for i, cell in enumerate(cells):
                        text = clean_text(cell.text)
                        if re.match(r'^[牡牝セ]\d+$', text):  # Pattern like "牡3" (male 3yo)
                            sex_age_cell = cell
                            logger.debug(f"Found sex/age cell in column {i}: {text}")
                            break
                        elif re.search(r'[牡牝セ]\d+', text):  # Pattern embedded in text
                            sex_age_cell = cell
                            logger.debug(f"Found embedded sex/age in column {i}: {text}")
                            break
                
                if sex_age_cell:
                    sex_age_text = clean_text(sex_age_cell.text)
                    sex_match = re.search(r'([牡牝セ])', sex_age_text)
                    age_match = re.search(r'(\d+)', sex_age_text)
                    
                    if sex_match:
                        sex_code = sex_match.group(1)
                        if sex_code == "牡":
                            horse_data["sex"] = "牡"  # Male
                        elif sex_code == "牝":
                            horse_data["sex"] = "牝"  # Female
                        elif sex_code == "セ":
                            horse_data["sex"] = "セ"  # Gelding
                        logger.debug(f"Extracted sex: {horse_data['sex']}")
                    
                    if age_match:
                        horse_data["age"] = age_match.group(1)
                        logger.debug(f"Extracted age: {horse_data['age']}")
                
                if not horse_data.get("sex") or not horse_data.get("age"):
                    # Try to extract from data-attribute if available
                    for cell in cells:
                        if cell.has_attr('data-sex') and not horse_data.get("sex"):
                            horse_data["sex"] = cell['data-sex']
                            logger.debug(f"Extracted sex from data-attribute: {horse_data['sex']}")
                        if cell.has_attr('data-age') and not horse_data.get("age"):
                            horse_data["age"] = cell['data-age']
                            logger.debug(f"Extracted age from data-attribute: {horse_data['age']}")
                        
                        if cell.has_attr('data-umaban') and not horse_data.get("umaban"):
                            horse_data["umaban"] = cell['data-umaban']
                            logger.debug(f"Extracted umaban from data-attribute: {horse_data['umaban']}")
                    
                    sex_age_spans = row.find_all("span", class_=re.compile(r"Barei|Seximal|Barei_Txt"))
                    for span in sex_age_spans:
                        span_text = clean_text(span.text)
                        sex_match = re.search(r'([牡牝セ])', span_text)
                        age_match = re.search(r'(\d+)', span_text)
                        
                        if sex_match and not horse_data.get("sex"):
                            horse_data["sex"] = sex_match.group(1)
                            logger.debug(f"Extracted sex from span: {horse_data['sex']}")
                        
                        if age_match and not horse_data.get("age"):
                            horse_data["age"] = age_match.group(1)
                            logger.debug(f"Extracted age from span: {horse_data['age']}")
                    
                    logger.debug(f"Could not extract sex/age for horse {horse_data.get('horse_name', 'unknown')}")
                
                # Extract weight with enhanced detection
                weight_cell = None
                for i, cell in enumerate(cells):
                    if cell.find("span", class_=re.compile(r"Weight|Burden")):
                        weight_cell = cell
                        logger.debug(f"Found weight cell with span.Weight|Burden: {clean_text(cell.text)}")
                        break
                    elif len(cells) > 4 and i == 3:  # Usually in fourth column
                        text = clean_text(cell.text)
                        if re.match(r'^\d+(\.\d+)?$', text):  # Pattern like "55.0"
                            weight_cell = cell
                            logger.debug(f"Found weight cell in column 4: {text}")
                            break
                
                # If not found in the usual places, try all cells
                if not weight_cell:
                    for i, cell in enumerate(cells):
                        text = clean_text(cell.text)
                        if re.match(r'^\d+(\.\d+)?$', text) and len(text) <= 5:  # Pattern like "55.0"
                            weight_cell = cell
                            logger.debug(f"Found weight cell in column {i}: {text}")
                            break
                        elif "kg" in text or "斤量" in text:  # Look for weight indicators
                            weight_match = re.search(r'(\d+(\.\d+)?)', text)
                            if weight_match:
                                weight_cell = cell
                                logger.debug(f"Found weight with indicator in column {i}: {text}")
                                break
                
                if weight_cell:
                    weight_text = clean_text(weight_cell.text)
                    weight_match = re.search(r'(\d+(\.\d+)?)', weight_text)
                    if weight_match:
                        horse_data["burden_weight"] = weight_match.group(1)
                        logger.debug(f"Extracted burden_weight: {horse_data['burden_weight']}")
                
                if not horse_data.get("burden_weight"):
                    # Try to extract from data-attribute if available
                    for cell in cells:
                        if cell.has_attr('data-weight') and not horse_data.get("burden_weight"):
                            horse_data["burden_weight"] = cell['data-weight']
                            logger.debug(f"Extracted burden_weight from data-attribute: {horse_data['burden_weight']}")
                    
                    # Try to extract from additional class patterns
                    weight_spans = row.find_all("span", class_=re.compile(r"Weight|Burden|Jockey_Weight"))
                    for span in weight_spans:
                        span_text = clean_text(span.text)
                        weight_match = re.search(r'(\d+(\.\d+)?)', span_text)
                        
                        if weight_match and not horse_data.get("burden_weight"):
                            horse_data["burden_weight"] = weight_match.group(1)
                            logger.debug(f"Extracted burden_weight from span: {horse_data['burden_weight']}")
                    
                    logger.debug(f"Could not extract burden_weight for horse {horse_data.get('horse_name', 'unknown')}")
                
                if "horse_name" in horse_data or "horse_id" in horse_data:
                    horses.append(horse_data)
            
            if horses:
                logger.info(f"Successfully extracted {len(horses)} horses from table structure")
                return horses
                    
        # If no table found or no horses extracted from table, try div structure
        if not horses:
            horse_list_div = soup.find("div", class_=re.compile(r"RaceTableArea|HorseList|RaceHorseArea"))
            if horse_list_div:
                logger.debug("Found horse list div instead of table")
                # Extract horses from div structure
                horse_items = horse_list_div.find_all("div", class_=re.compile(r"HorseItem|HorseList_Item"))
                if horse_items:
                    logger.debug(f"Found {len(horse_items)} horse items in div structure")
                    for item in horse_items:
                        horse_data = {}
                        
                        # Extract umaban (horse number)
                        umaban_div = item.find("div", class_=re.compile(r"Num|Waku|HorseNum"))
                        if umaban_div:
                            horse_data["umaban"] = clean_text(umaban_div.text)
                        
                        # Extract horse name and ID
                        horse_name_div = item.find("div", class_=re.compile(r"Horse_Name|HorseName"))
                        if horse_name_div:
                            horse_link = horse_name_div.find("a", href=re.compile(r"/horse/\d+"))
                            if horse_link:
                                horse_data["horse_name"] = clean_text(horse_link.text)
                                horse_id_match = re.search(r"/horse/(\d+)", horse_link["href"])
                                if horse_id_match:
                                    horse_data["horse_id"] = horse_id_match.group(1)
                        
                        # Extract jockey name and ID
                        jockey_div = item.find("div", class_=re.compile(r"Jockey|Jockey_Name"))
                        if jockey_div:
                            jockey_link = jockey_div.find("a", href=re.compile(r"/jockey/\d+"))
                            if jockey_link:
                                horse_data["jockey"] = clean_text(jockey_link.text)
                                jockey_id_match = re.search(r"/jockey/(\d+)", jockey_link["href"])
                                if jockey_id_match:
                                    horse_data["jockey_id"] = jockey_id_match.group(1)
                        
                        # Extract trainer name and ID
                        trainer_div = item.find("div", class_=re.compile(r"Trainer|Trainer_Name"))
                        if trainer_div:
                            trainer_link = trainer_div.find("a", href=re.compile(r"/trainer/\d+"))
                            if trainer_link:
                                horse_data["trainer"] = clean_text(trainer_link.text)
                                trainer_id_match = re.search(r"/trainer/(\d+)", trainer_link["href"])
                                if trainer_id_match:
                                    horse_data["trainer_id"] = trainer_id_match.group(1)
                        
                        if "horse_name" in horse_data or "horse_id" in horse_data:
                            horses.append(horse_data)
                    
                    if horses:
                        logger.info(f"Successfully extracted {len(horses)} horses from div structure")
                        return horses
        
        if not race_table:
            title_tag = soup.find('title')
            race_title = clean_text(title_tag.text) if title_tag else 'Unknown Race'
            logger.warning(f"Horse list table not found for race {race_title}.")
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
            
            # Check if this is a Shutuba_Table format (new format)
            is_shutuba_format = False
            if "Shutuba_Table" in str(race_table.get("class", "")):
                is_shutuba_format = True
                logger.debug("Processing row in Shutuba_Table format")
            
            if len(cells) > 3:  # Basic check for valid row
                # Extract Horse ID from link - handle both formats
                horse_link_tag = None
                
                if is_shutuba_format:
                    # In Shutuba_Table format, horse link might be in a different cell or have different structure
                    for cell in cells:
                        horse_link = cell.find("a", href=re.compile(r"/horse/\d+"))
                        if horse_link:
                            horse_link_tag = horse_link
                            break
                else:
                    horse_link_tag = cells[3].find("a", href=re.compile(r"/horse/\d+"))
                
                if horse_link_tag:
                    horse_id_match = re.search(r"/horse/(\d+)", horse_link_tag["href"])
                    if horse_id_match:
                        horse_data["horse_id"] = horse_id_match.group(1)
                        logger.debug(f"Found horse_id: {horse_data['horse_id']}")

                # Extract other basic info based on format
                if is_shutuba_format:
                    for i, cell in enumerate(cells):
                        # Extract wakuban (gate number) - check data-sort-value first
                        if i == 0:
                            if cell.has_attr('data-sort-value'):
                                horse_data["wakuban"] = cell['data-sort-value']  # B1.3
                                logger.debug(f"Extracted wakuban from data-sort-value: {horse_data['wakuban']}")
                            elif re.match(r"^\d+$", clean_text(cell.text)):
                                horse_data["wakuban"] = clean_text(cell.text)  # B1.3
                        
                        # Extract umaban (horse number) - check data-sort-value first
                        if i == 1:
                            if cell.has_attr('data-sort-value'):
                                horse_data["umaban"] = cell['data-sort-value']  # B1.2
                                logger.debug(f"Extracted umaban from data-sort-value: {horse_data['umaban']}")
                            elif re.match(r"^\d+$", clean_text(cell.text)):
                                horse_data["umaban"] = clean_text(cell.text)  # B1.2
                        
                        horse_link = cell.find("a", href=re.compile(r"/horse/\d+"))
                        if horse_link:
                            horse_data["horse_name"] = clean_text(horse_link.text)  # B1.1
                        
                        cell_text = clean_text(cell.text)
                        sex_age_match = re.search(r"([牡牝セ])(\d+)", cell_text)
                        if sex_age_match:
                            horse_data["sex"] = sex_age_match.group(1)  # B1.4
                            horse_data["age"] = int(sex_age_match.group(2))  # B1.5
                            logger.debug(f"Parsed sex: {horse_data['sex']}, age: {horse_data['age']}")
                else:
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


                # Extract burden weight (B1.6)
                if is_shutuba_format:
                    # In Shutuba_Table format, look for burden weight in cells
                    for cell in cells:
                        weight_match = re.search(r"(\d+\.\d+|\d+)", clean_text(cell.text))
                        if weight_match and len(weight_match.group(1)) <= 5:  # Avoid matching other numbers
                            horse_data["burden_weight"] = weight_match.group(1)
                            break
                else:
                    horse_data["burden_weight"] = clean_text(cells[5].text) # B1.6

                # Extract Jockey Name and ID (C1.1)
                if is_shutuba_format:
                    # In Shutuba_Table format, jockey might be in a cell with specific class
                    jockey_cell = None
                    jockey_link = None
                    
                    for cell in cells:
                        jockey_link_candidate = cell.find("a", href=re.compile(r"/jockey/"))
                        if jockey_link_candidate:
                            jockey_cell = cell
                            jockey_link = jockey_link_candidate
                            break
                else:
                    jockey_cell = cells[6]
                    jockey_link = jockey_cell.find("a", href=re.compile(r"/jockey/"))
                
                if jockey_link:
                    horse_data["jockey"] = clean_text(jockey_link.text)
                    jockey_id_match = re.search(r"/jockey/(?:result/recent/)?(\w+)/?", jockey_link["href"])
                    if jockey_id_match:
                        horse_data["jockey_id"] = jockey_id_match.group(1)
                        logger.debug(f"Parsed jockey: {horse_data['jockey']}, id: {horse_data['jockey_id']}")
                    else:
                        logger.warning(f"Found jockey link but could not parse ID: {jockey_link['href']}")
                        horse_data["jockey_id"] = None
                elif jockey_cell:
                    horse_data["jockey"] = clean_text(jockey_cell.text) # Fallback to text if no link
                    horse_data["jockey_id"] = None
                    logger.debug(f"Parsed jockey (no link/ID): {horse_data['jockey']}")
                else:
                    logger.warning("Could not find jockey information")
                    horse_data["jockey"] = None
                    horse_data["jockey_id"] = None

                # Extract Trainer Name and ID (B1.7 / C2.1)
                if is_shutuba_format:
                    # In Shutuba_Table format, trainer might be in a cell with specific class
                    trainer_cell = None
                    trainer_link = None
                    
                    for cell in cells:
                        trainer_link_candidate = cell.find("a", href=re.compile(r"/trainer/"))
                        if trainer_link_candidate:
                            trainer_cell = cell
                            trainer_link = trainer_link_candidate
                            break
                elif len(cells) > 18: # Check if trainer cell exists in original format
                    trainer_cell = cells[18]
                    trainer_link = trainer_cell.find("a", href=re.compile(r"/trainer/")) if trainer_cell else None
                else:
                    trainer_cell = None
                    trainer_link = None
                
                if trainer_link:
                    horse_data["trainer"] = clean_text(trainer_link.text)
                    # Made regex more general to capture alphanumeric IDs and handle potential path variations
                    trainer_id_match = re.search(r"/trainer/(\w+)/", trainer_link["href"])
                    if trainer_id_match:
                        horse_data["trainer_id"] = trainer_id_match.group(1)
                        logger.debug(f"Parsed trainer: {horse_data['trainer']}, id: {horse_data['trainer_id']}")
                    else:
                        logger.warning(f"Found trainer link but could not parse ID: {trainer_link['href']}")
                        horse_data["trainer_id"] = None
                elif trainer_cell:
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
    """Scrapes detailed race results and performance data for a horse, including improved condition summaries.""" # Updated docstring
    logger.info(f"Scraping full results for horse {horse_id}...")
    results_data = {"conditions": {}, "results": []}
    results_url = f"{BASE_URL_NETKEIBA}/horse/result/{horse_id}"
    soup = get_soup(results_url)
    if not soup:
        logger.warning(f"Could not fetch horse results page for {horse_id}")
        return results_data # Return empty data if page fetch fails

    try:
        # --- Remove B2 condition summary scraping attempt as it's unreliable/missing on this page ---
        logger.info(f"Skipping B2 conditional summary scraping on results page for horse {horse_id} (data often missing/inconsistent here).")
        results_data["conditions"] = {} # Ensure key exists but is empty

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
    """Scrapes detailed pedigree information (5 generations, crosses, siblings) for a horse.""" # Updated docstring
    logger.info(f"Scraping pedigree for horse {horse_id}...")
    pedigree_data = {"pedigree_5gen": {}, "crosses": [], "siblings": []} # Added siblings key
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
            # !!! WARNING: The following parsing uses fixed indices and is highly likely to be inaccurate !!!
            # !!! due to varying rowspan values in the pedigree table. A robust parser would need     !!!
            # !!! to analyze rowspan attributes to correctly map ancestors. This is a basic attempt.   !!!
            logger.warning(f"Pedigree parsing for {horse_id} uses fixed indices and may be inaccurate due to complex table structure (rowspan).")
            rows = ped_table.find_all("tr")
            try:
                # Generation 1 (Parents) - Basic attempt
                if len(rows) > 0:
                    cells_g1 = rows[0].find_all("td")
                    if len(cells_g1) > 0 and cells_g1[0].find("a"): pedigree_5gen_data["father"] = {"name": clean_text(cells_g1[0].text), "url": cells_g1[0].find("a").get("href")}
                if len(rows) > 16: # Mother is often much lower due to rowspan
                     cells_g1_mother = rows[16].find_all("td")
                     if len(cells_g1_mother) > 0 and cells_g1_mother[0].find("a"): pedigree_5gen_data["mother"] = {"name": clean_text(cells_g1_mother[0].text), "url": cells_g1_mother[0].find("a").get("href")}

                # Generation 2 (Grandparents) - Basic attempt
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

                # Generation 3 (Great-Grandparents) - Basic attempt (Indices are estimates)
                # ... (Existing G3 parsing kept, but still potentially inaccurate) ...
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

                # TODO: Extend logic for Generations 4, 5 - Requires robust rowspan parsing.
                logger.info(f"Partially parsed 5-gen pedigree (attempted Gen 1-3, accuracy limited) for horse {horse_id}.")

            except Exception as ped_parse_err:
                logger.error(f"Error during basic pedigree parsing for {horse_id}: {ped_parse_err}", exc_info=True)

            pedigree_data["pedigree_5gen"] = pedigree_5gen_data # Store the parsed data
        else:
            logger.warning(f"Pedigree table 'blood_table' not found or not a Tag for horse {horse_id}")

        # --- Extract Crosses (Inbreeding - B4.7) ---
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

        # --- Extract Siblings (B4.5) ---
        logger.debug("Looking for sibling information (兄弟馬)...")
        # Sibling info might be in a table with class 'list_table' or similar, often after pedigree
        sibling_section = soup.find("h3", string=re.compile("兄弟馬")) # Find header for siblings
        if sibling_section:
            sibling_table = sibling_section.find_next_sibling("table", class_=re.compile("race_table|list_table")) # Find next table
            if sibling_table and isinstance(sibling_table, Tag):
                rows = sibling_table.find_all("tr")
                for row in rows[1:]: # Skip header
                    cells = row.find_all("td")
                    if len(cells) > 1: # Need at least name and maybe wins
                        sibling_link = cells[0].find("a")
                        sibling_name = clean_text(sibling_link.text) if sibling_link else clean_text(cells[0].text)
                        sibling_url = sibling_link.get("href") if sibling_link else None
                        # Extract other details like wins/status if available
                        sibling_status = clean_text(cells[1].text) if len(cells) > 1 else None
                        pedigree_data["siblings"].append({
                            "name": sibling_name,
                            "url": sibling_url,
                            "status_or_wins": sibling_status
                        })
                logger.debug(f"Found {len(pedigree_data['siblings'])} siblings for horse {horse_id}.")
            else:
                logger.debug(f"Sibling header found but no subsequent table found for horse {horse_id}.")
        else:
            logger.debug(f"Sibling section header not found for horse {horse_id}.")


    except Exception as e:
        logger.error(f"Error scraping pedigree for horse {horse_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping pedigree for horse {horse_id}.")
    return pedigree_data


def scrape_training(driver: WebDriver, horse_id: str): # Accept driver as argument and add type hints
    """Scrapes training information (B5) for a horse using Selenium."""
    logger.info(f"Scraping training info for horse {horse_id}...")
    training_data = {"workouts": [], "comments": []} # Added comments key
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

        # --- Extract Training Details (B5.1 - B5.7) ---
        logger.debug(f"Looking for training tables...")
        
        training_tables = []
        for table_class in ["WorkDataTable", "oikiri_table", "table_slide_body WorkDataTable"]:
            tables = soup.find_all("table", class_=table_class)
            if tables:
                training_tables.extend(tables)
        
        if training_tables:
            training_data["workouts"] = []
            
            for training_table in training_tables:
                if not isinstance(training_table, Tag):
                    continue
                    
                rows = training_table.find_all("tr")
                for row in rows[1:]:  # Skip header
                    cells = row.find_all("td")
                    
                    if len(cells) >= 8:  # Basic check for valid row
                        # Combine location details for better context
                        location_detail = f"{clean_text(cells[1].text)} {clean_text(cells[2].text)} ({clean_text(cells[3].text)})"
                        
                        workout = {
                            "date": clean_text(cells[0].text),              # B5.1, B5.5 (日付)
                            "location_detail": location_detail,             # B5.1, B5.5 (場所, コース, 馬場状態 - B5.8 partially)
                            "time_total": clean_text(cells[4].text),        # B5.2, B5.5 (全体時計)
                            "time_laps": clean_text(cells[5].text),         # B5.3, B5.5 (ラップタイム)
                            "intensity": clean_text(cells[6].text),         # B5.4, B5.5 (強度)
                            "partner_info": clean_text(cells[7].text),      # B5.7 (併せ馬情報)
                        }
                        
                        # Extract additional details for B5.8, B5.9
                        slope_match = re.search(r"坂路\s*([^(]*)", location_detail)
                        if slope_match:
                            workout["slope_condition"] = clean_text(slope_match.group(1))
                            
                        wcourse_match = re.search(r"W(内|外|直)", location_detail)
                        if wcourse_match:
                            workout["wcourse_position"] = wcourse_match.group(1)
                            
                        video_link = row.find("a", href=re.compile(r"video"))
                        if video_link and "href" in video_link.attrs:
                            workout["video_url"] = video_link["href"]
                        
                        # Clean up potentially empty fields
                        workout = {k: v for k, v in workout.items() if v}
                        training_data["workouts"].append(workout)
                        logger.debug(f"Added workout data: {workout}")
            
            logger.info(f"Found {len(training_data['workouts'])} workout records for horse {horse_id}")
        else:
            logger.warning(f"No training tables found on {training_url} for horse {horse_id}.")
        
        # --- Extract Stable Comments (B5.12) ---
        logger.debug("Looking for stable comments section...")
        comment_section = soup.find("div", class_=re.compile("comment", re.IGNORECASE)) # Guessing class name
        if comment_section and isinstance(comment_section, Tag):
            # Comments might be in <p> tags or list items <li>
            comments = comment_section.find_all(['p', 'li'])
            if comments:
                for comment in comments:
                    comment_text = clean_text(comment.text)
                    if comment_text:
                        training_data["comments"].append(comment_text)
                logger.info(f"Found {len(training_data['comments'])} potential stable comments for {horse_id}.")
            else:
                # Fallback: get all text if specific tags not found
                comment_text = clean_text(comment_section.text)
                if comment_text:
                    training_data["comments"].append(comment_text)
                    logger.info(f"Found comment section text (fallback) for {horse_id}.")
        else:
            logger.debug(f"Comment section (guessed class 'comment') not found for horse {horse_id}.")


    except Exception as e:
        logger.error(f"Error scraping training info for horse {horse_id}: {e}", exc_info=True)

    logger.info(f"Finished scraping training info for horse {horse_id}.") # Log moved outside try block
    return training_data
