"""
Scraping functions related to race information.
"""
import re
from datetime import datetime
from bs4 import Tag

# Import shared utilities and config
from utils import get_soup, clean_text
from logger_config import get_logger

# Get logger instance
logger = get_logger(__name__)


def scrape_race_info(soup, race_id):
    """Scrapes basic race information from the race page soup."""
    race_info = {"race_id": race_id}
    try:
        # --- Extract Race Number ---
        race_num_tag = soup.find("div", class_="RaceNum") or soup.find("div", class_=re.compile(r"Race_Num|RaceNum"))
        if race_num_tag:
            race_info["race_number"] = clean_text(race_num_tag.text)
            logger.debug(f"Found race_number: {race_info['race_number']}")
        else:
            # Fallback: Try to find race number in the title or other elements
            title_tag = soup.find("title")
            if title_tag:
                title_text = clean_text(title_tag.text)
                race_num_match = re.search(r"(\d+)R", title_text)
                if race_num_match:
                    race_info["race_number"] = race_num_match.group(1)
                    logger.debug(f"Found race_number from title: {race_info['race_number']}")
                else:
                    logger.warning("Could not extract race number from title.")
            else:
                logger.warning("Could not find 'RaceNum' div or title.")

        # --- Extract Race Name using multiple possible selectors ---
        race_name_h1 = soup.find("h1")
        if race_name_h1:
            race_name_text = clean_text(race_name_h1.text)
            # Extract race name from h1 text (e.g., "フローラＳ(G2)")
            race_name_match = re.search(r"^([^|]+?)(?:\s*\||$)", race_name_text)
            if race_name_match:
                race_name_clean = race_name_match.group(1).strip()
                if race_name_clean and race_name_clean != "競馬データベース":
                    race_info["race_name"] = race_name_clean
                    logger.debug(f"Found race_name from h1: {race_info['race_name']}")
                    
                    # Extract grade if present
                    grade_match = re.search(r"\(([GJ][1-3])\)", race_name_clean)
                    if grade_match:
                        race_info["grade"] = grade_match.group(1)
                        logger.debug(f"Extracted grade from h1: {race_info['grade']}")
        
        # If not found in h1, try RaceTitName div
        if "race_name" not in race_info or not race_info["race_name"] or race_info["race_name"] == "競馬データベース":
            race_tit_name = soup.find("div", class_="RaceTitName")
            if race_tit_name:
                race_name_text = clean_text(race_tit_name.text)
                if race_name_text and race_name_text != "競馬データベース":
                    race_info["race_name"] = race_name_text
                    logger.debug(f"Found race_name from RaceTitName div: {race_info['race_name']}")
                    
                    # Extract grade if present
                    grade_match = re.search(r"\(([GJ][1-3])\)", race_name_text)
                    if grade_match:
                        race_info["grade"] = grade_match.group(1)
                        logger.debug(f"Extracted grade from RaceTitName: {race_info['grade']}")
        
        # If not found in h1, try other div classes
        if "race_name" not in race_info or not race_info["race_name"] or race_info["race_name"] == "競馬データベース":
            for class_pattern in [r"RaceMainTitle|RaceName|Race_Name", r"RaceData01", r"RaceList_Item02"]:
                race_name_div = soup.find("div", class_=re.compile(class_pattern))
                if race_name_div:
                    race_name_text = clean_text(race_name_div.text)
                    if race_name_text and race_name_text != "競馬データベース":
                        race_info["race_name"] = race_name_text
                        logger.debug(f"Found race_name from div with class pattern {class_pattern}: {race_info['race_name']}")
                        
                        # Extract grade if present
                        grade_match = re.search(r"\(([GJ][1-3])\)", race_name_text)
                        if grade_match:
                            race_info["grade"] = grade_match.group(1)
                            logger.debug(f"Extracted grade from div: {race_info['grade']}")
                        break
        
        if "race_name" not in race_info or not race_info["race_name"] or race_info["race_name"] == "競馬データベース":
            race_name_span = soup.find("span", class_=re.compile(r"RaceName|Race_Name|RaceTitName"))
            if race_name_span:
                race_name_text = clean_text(race_name_span.text)
                if race_name_text and race_name_text != "競馬データベース":
                    race_info["race_name"] = race_name_text
                    logger.debug(f"Found race_name from span: {race_info['race_name']}")
        
        # If not found, try from title
        if "race_name" not in race_info or not race_info["race_name"] or race_info["race_name"] == "競馬データベース":
            title_tag = soup.find("title")
            if title_tag:
                title_text = clean_text(title_tag.text)
                # Extract race name from title (e.g., "フローラＳ(G2) 出馬表 | 2025年4月27日 東京11R")
                race_name_match = re.search(r"^([^(|]+)(?:\(.*?\))?(?:\s*出馬表|\s*レース結果)?", title_text)
                if race_name_match:
                    race_info["race_name"] = race_name_match.group(1).strip()
                    logger.debug(f"Found race_name from title: {race_info['race_name']}")
                    
                    # Extract grade from title
                    grade_match = re.search(r"\(([GJ][1-3])\)", title_text)
                    if grade_match:
                        race_info["grade"] = grade_match.group(1)
                        logger.debug(f"Extracted grade from title: {race_info['grade']}")
                    
                    # Extract date, venue, and race number from title
                    venue_date_match = re.search(r"\|\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*([^\d]+)(\d+)R", title_text)
                    if venue_date_match:
                        year, month, day, venue, race_num = venue_date_match.groups()
                        race_info["date"] = f"{year}/{month.zfill(2)}/{day.zfill(2)}"
                        race_info["venue_name"] = venue.strip()
                        race_info["race_number"] = race_num
                        logger.debug(f"Extracted date: {race_info['date']}, venue: {race_info['venue_name']}, race number: {race_info['race_number']} from title")
        
        if "race_name" not in race_info or not race_info["race_name"]:
            race_name_h1 = None
            for h1_tag in soup.find_all("h1"):
                if h1_tag.text and len(h1_tag.text.strip()) > 0:
                    race_name_h1 = h1_tag
                    break
                    
            if race_name_h1:
                race_info["race_name"] = clean_text(race_name_h1.text)
                logger.debug(f"Found race_name from h1: {race_info['race_name']}")
                
                grade_match = re.search(r"\(([GJ][1-3])\)", race_name_h1.text)
                if grade_match:
                    race_info["grade"] = grade_match.group(1)
                    logger.debug(f"Extracted grade from race name: {race_info['grade']}")
        
        if "race_name" not in race_info or not race_info["race_name"] or race_info["race_name"] == "競馬データベース":
            # Look for race name in specific divs
            race_name_divs = soup.find_all("div", class_=re.compile(r"RaceName|Race_Name|RaceMainTitle"))
            for div in race_name_divs:
                if div.text and len(div.text.strip()) > 0:
                    race_info["race_name"] = clean_text(div.text)
                    logger.debug(f"Found race_name from div: {race_info['race_name']}")
                    
                    grade_match = re.search(r"\(([GJ][1-3])\)", div.text)
                    if grade_match:
                        race_info["grade"] = grade_match.group(1)
                        logger.debug(f"Extracted grade from div: {race_info['grade']}")
                    break
                
        if "race_name" not in race_info or not race_info["race_name"]:
            meta_tags = soup.find_all("meta", property="og:title")
            for meta in meta_tags:
                if meta.get("content"):
                    content = clean_text(meta["content"])
                    race_name_match = re.search(r"([^|]+)(?:\(.*?\))?(?:\s*\||$)", content)
                    if race_name_match:
                        race_info["race_name"] = race_name_match.group(1).strip()
                        logger.debug(f"Found race_name from meta tag: {race_info['race_name']}")
                        break
                        
        if "race_name" not in race_info or not race_info["race_name"]:
            race_name_divs = soup.find_all("div", class_=re.compile(r"RaceName|Race_Name"))
            for div in race_name_divs:
                if div.text and len(div.text.strip()) > 0:
                    race_info["race_name"] = clean_text(div.text)
                    logger.debug(f"Found race_name from div: {race_info['race_name']}")
                    break

        # --- Extract Race Details (Distance, Course, Weather, Condition) ---
        race_data_divs = soup.find_all("div", class_=re.compile(r"RaceData|Race_Data"))
        race_details_text = None
        
        for div in race_data_divs:
            text = clean_text(div.text)
            if "発走" in text and ("芝" in text or "ダ" in text):
                race_details_text = text
                break
                
        if not race_details_text:
            # Look for the race details in the 11R div with the race time and course info
            race_header_divs = soup.find_all("div", class_=re.compile(r"RaceList_Item|Race_Header"))
            for div in race_header_divs:
                race_num_div = div.find("div", class_=re.compile(r"RaceNum|Race_Num"))
                if race_num_div and "11R" in race_num_div.text:
                    race_details_div = div.find_next_sibling("div")
                    if race_details_div:
                        text = clean_text(race_details_div.text)
                        if "発走" in text and ("芝" in text or "ダ" in text) and "m" in text:
                            race_details_text = text
                            break
        
        if not race_details_text:
            # Look for the 11R section
            r11_divs = soup.find_all("div", class_=re.compile(r"11R"))
            for div in r11_divs:
                text = clean_text(div.text)
                if "発走" in text and ("芝" in text or "ダ" in text) and "m" in text:
                    race_details_text = text
                    break
                    
                next_div = div.find_next_sibling("div")
                if next_div:
                    text = clean_text(next_div.text)
                    if "発走" in text and ("芝" in text or "ダ" in text) and "m" in text:
                        race_details_text = text
                        break
        
        if not race_details_text:
            for div in soup.find_all("div"):
                text = clean_text(div.text)
                if "発走" in text and ("芝" in text or "ダ" in text) and "m" in text:
                    race_details_text = text
                    break
                    
            if not race_details_text:
                race_main_data = soup.find("div", class_=re.compile(r"RaceMainData|Race_Data_Detail"))
                if race_main_data:
                    for span in race_main_data.find_all("span"):
                        text = clean_text(span.text)
                        if ("芝" in text or "ダ" in text) and "m" in text:
                            race_details_text = text
                            break
        
        if race_details_text:
            logger.debug(f"Found race_details_text: {race_details_text}")
            # Example: "15:45発走 / 芝2000m (左 A)"
            
            # Extract start time
            start_time_match = re.search(r"(\d+:\d+)発走", race_details_text)
            if start_time_match:
                race_info["start_time"] = start_time_match.group(1)
                logger.debug(f"Parsed start_time: {race_info['start_time']}")
                
            # Extract course type, direction, and distance
            course_match = re.search(r"(芝|ダ)(\d+)m\s*(?:\(([左右])\s*([A-Z])\))?", race_details_text)
            if course_match:
                race_info["course_type"] = course_match.group(1)
                race_info["distance_meters"] = course_match.group(2) + "m"
                if course_match.group(3):
                    race_info["direction"] = course_match.group(3)
                if course_match.group(4):
                    race_info["track_section"] = course_match.group(4)
                logger.debug(f"Parsed course details: {race_info['course_type']} {race_info['distance_meters']}")
            else:
                course_match_alt = re.search(r"(障)(?:・障害)?(\d+)m", race_details_text)
                if course_match_alt:
                    race_info["course_type"] = course_match_alt.group(1)
                    race_info["distance_meters"] = course_match_alt.group(2) + "m"
                    logger.debug(f"Parsed obstacle course: {race_info['course_type']} {race_info['distance_meters']}")
                else:
                    logger.warning(f"Could not parse course details from: {race_details_text}")
        else:
            logger.warning("Could not find race details text.")


            # Date, Venue Detail, Class, Conditions (A1.1, A1.2, A1.8-A1.11)
            smalltxt_p = soup.find("p", class_="smalltxt")
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
                if header_row and isinstance(header_row, Tag): # Add Tag check for header_row
                    # Look for a header cell containing '頭数'
                    head_count_th_found = False
                    for th in header_row.find_all("th"):
                        # Ensure th is a Tag before accessing text
                        if isinstance(th, Tag) and re.search(r"頭数", clean_text(th.text) or ""):
                            head_count_th_found = True
                            break
                    # head_count_th = header_row.find("th", string=re.compile(r"頭数")) # Original line causing Pylance warning
                    if head_count_th_found:
                        # The actual count might be in the race info section, let's try to find smalltxt or similar
                        # Re-checking smalltxt or similar for head count
                        smalltxt_p = soup.find("p", class_="smalltxt")
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


from typing import Dict, Any, Optional, List # Add typing imports

def scrape_detailed_race_results(race_id: str) -> Dict[str, Any]:
    """Scrapes detailed results like lap times, weather, track details from the race result page.""" # Updated docstring
    logger.info(f"Scraping detailed results (lap times, weather, track details) for race {race_id}...")
    # Add type hint for the dictionary structure
    detailed_results_data: Dict[str, Any] = {
        "weather_track_details": {}, # Initialize as empty dict
        "lap_times": None,
        "pace_segments": None,
        "time_diffs": {}
    }
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
        weather_track_details = {} # Use a temporary dict
        if race_data01_div and isinstance(race_data01_div, Tag):
            details_text = clean_text(race_data01_div.text)
            logger.debug(f"Found RaceData01 text: {details_text}")
            # Example: "芝:良 / ダート:稍重  天候:晴  芝:良  発走時間:15:40"
            # Example with more details: "天候:晴 / 芝:良 / ダート:稍重 / 馬場水分:芝 G前 10.5% 4角 10.8% / ダ G前 3.2% 4角 3.5% / クッション値:9.5"
            weather_track_details["summary_text"] = details_text

            if isinstance(details_text, str):
                # Basic Weather (A3.6)
                weather_match = re.search(r"天候:(\S+)", details_text)
                if weather_match:
                    weather_track_details["weather"] = weather_match.group(1)

                # Basic Track Condition (A4.1)
                condition_match_shiba = re.search(r"芝:(\S+)", details_text)
                if condition_match_shiba:
                     weather_track_details["track_condition_shiba"] = condition_match_shiba.group(1)
                condition_match_dirt = re.search(r"ダート:(\S+)", details_text)
                if condition_match_dirt:
                     weather_track_details["track_condition_dirt"] = condition_match_dirt.group(1)

                # Temperature (A3.6) - Often not present here, might need JRA source
                temp_match = re.search(r"気温:([\d\.]+)℃", details_text) # Guessing pattern
                if temp_match:
                    weather_track_details["temperature_celsius"] = temp_match.group(1)
                    logger.debug(f"Found temperature: {weather_track_details['temperature_celsius']}")

                # Moisture Content (A4.2, A4.3) - Look for specific patterns
                moisture_shiba_g_match = re.search(r"芝 G前 ([\d\.]+)%", details_text)
                if moisture_shiba_g_match: weather_track_details["moisture_shiba_goal"] = moisture_shiba_g_match.group(1)
                moisture_shiba_4c_match = re.search(r"芝 4角 ([\d\.]+)%", details_text)
                if moisture_shiba_4c_match: weather_track_details["moisture_shiba_4c"] = moisture_shiba_4c_match.group(1)
                moisture_dirt_g_match = re.search(r"ダ G前 ([\d\.]+)%", details_text)
                if moisture_dirt_g_match: weather_track_details["moisture_dirt_goal"] = moisture_dirt_g_match.group(1)
                moisture_dirt_4c_match = re.search(r"ダ 4角 ([\d\.]+)%", details_text)
                if moisture_dirt_4c_match: weather_track_details["moisture_dirt_4c"] = moisture_dirt_4c_match.group(1)
                if any(k.startswith("moisture_") for k in weather_track_details):
                    logger.debug(f"Found moisture data: { {k:v for k,v in weather_track_details.items() if k.startswith('moisture_')} }")


                # Cushion Value (A4.4) - Look for specific pattern
                cushion_match = re.search(r"クッション値:([\d\.]+)", details_text)
                if cushion_match:
                    weather_track_details["cushion_value"] = cushion_match.group(1)
                    logger.debug(f"Found cushion value: {weather_track_details['cushion_value']}")

                # Wind (A3.4, A3.5) - Often not present here, might need JRA source
                # wind_match = re.search(r"風速:(\S+) ([\d\.]+)m", details_text) # Guessing pattern
                # if wind_match:
                #     weather_track_details["wind_direction"] = wind_match.group(1)
                #     weather_track_details["wind_speed_mps"] = wind_match.group(2)

            else:
                logger.warning(f"RaceData01 details_text was not a string, skipping regex search for race {race_id}")

            detailed_results_data["weather_track_details"] = weather_track_details # Assign the populated dict

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


# --- Course Details Scraper (A2) ---
def scrape_course_details(venue_name: str) -> Dict[str, Any]:
    """
    Scrapes detailed course characteristics (A2) for a given venue.
    """
    logger.info(f"Scraping course details for venue '{venue_name}'...")
    course_details = {"venue_name": venue_name}
    
    # Determine venue code from venue_name
    venue_codes = {
        "東京": "tokyo", "中山": "nakayama", "阪神": "hanshin", "京都": "kyoto",
        "福島": "fukushima", "新潟": "niigata", "小倉": "kokura", "札幌": "sapporo",
        "函館": "hakodate", "中京": "chukyo"
    }
    venue_code = venue_codes.get(venue_name)
    
    if not venue_code:
        logger.warning(f"Unknown venue name '{venue_name}', cannot determine venue code.")
        return course_details
        
    course_url = f"https://db.netkeiba.com/course/{venue_code}/"
    soup = get_soup(course_url)
    
    if soup:
        # Extract A2.1 Layout
        layout_img = soup.find("img", class_=re.compile(r"course_map|course_img"))
        if layout_img and "src" in layout_img.attrs:
            course_details["layout_image_url"] = layout_img["src"]
        
        # Extract course info from course description
        course_info_div = soup.find("div", class_=re.compile(r"course_info|course_data"))
        if course_info_div:
            course_text = clean_text(course_info_div.text)
            straight_match = re.search(r"直線.*?(\d+)m", course_text)
            if straight_match:
                course_details["straight_length"] = straight_match.group(1)
            
            corner_match = re.search(r"コーナー.*?(急|緩|標準)", course_text)
            if corner_match:
                course_details["corner_shape"] = corner_match.group(1)
            
            elevation_match = re.search(r"高低差.*?(\d+)m", course_text)
            if elevation_match:
                course_details["elevation"] = elevation_match.group(1)
        
        # Extract A2.6/A2.7 Track Bias data
        bias_table = soup.find("table", class_=re.compile(r"bias_table|race_table"))
        if bias_table:
            course_details["track_bias"] = []
            rows = bias_table.find_all("tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) >= 3:
                    bias_data = {
                        "track_type": clean_text(cells[0].text),
                        "distance": clean_text(cells[1].text),
                        "bias_description": clean_text(cells[2].text)
                    }
                    course_details["track_bias"].append(bias_data)
    else:
        logger.warning(f"Could not fetch course details page: {course_url}")
        
    return course_details
