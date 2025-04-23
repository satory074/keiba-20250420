"""
Scraping functions related to speed figures and performance metrics.
"""
import re
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from typing import Dict, Any, Optional, List

from utils import get_soup, clean_text
from logger_config import get_logger
from config import BASE_URL_NETKEIBA

logger = get_logger(__name__)


def scrape_speed_figures(race_id, horse_id=None):
    """Scrapes speed figures and performance metrics (B7) for a race or specific horse."""
    logger.info(f"Scraping speed figures for race {race_id}" + (f", horse {horse_id}" if horse_id else ""))
    speed_data = {"race_id": race_id, "figures": {}}
    
    if horse_id:
        figure_url = f"{BASE_URL_NETKEIBA}/horse/rpci/{horse_id}/"
    else:
        figure_url = f"{BASE_URL_NETKEIBA}/race/rpci/{race_id}/"
        
    soup = get_soup(figure_url)
    if not soup:
        logger.warning(f"Could not fetch speed figure page: {figure_url}")
        return speed_data
    
    try:
        figure_table = soup.find("table", class_=re.compile(r"race_table_01|RaceTable01|SpeedFigureTable"))
        if figure_table and isinstance(figure_table, Tag):
            rows = figure_table.find_all("tr")
            headers = []
            
            header_row = rows[0] if rows else None
            if header_row:
                headers = [clean_text(th.text) for th in header_row.find_all("th")]
            
            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) < len(headers):
                    continue
                    
                horse_link = row.find("a", href=re.compile(r"/horse/\d+"))
                row_horse_id = None
                if horse_link:
                    horse_id_match = re.search(r"/horse/(\d+)", horse_link["href"])
                    if horse_id_match:
                        row_horse_id = horse_id_match.group(1)
                
                umaban = clean_text(cells[0].text) if len(cells) > 0 else "unknown"
                row_key = row_horse_id or umaban
                
                horse_figures = {}
                for i, header in enumerate(headers):
                    if i < len(cells):
                        value = clean_text(cells[i].text)
                        if value:
                            if "指数" in header:  # B7.1 Speed Index
                                horse_figures["speed_index"] = value
                            elif "上り" in header:  # B7.2 Last 3F
                                horse_figures["last_3f"] = value
                            elif "位置取り" in header:  # B7.4 Position
                                horse_figures["position_metric"] = value
                            elif "ペース" in header:  # B7.3 Pace Rating
                                horse_figures["pace_rating"] = value
                            elif "テン" in header:  # B7.5 Start Dash
                                horse_figures["start_dash"] = value
                            elif "上昇度" in header:  # B7.7 Improvement Rating
                                horse_figures["improvement_rating"] = value
                            else:
                                clean_header = re.sub(r'[^a-zA-Z0-9_]', '_', header).lower()
                                horse_figures[clean_header] = value
                
                speed_data["figures"][row_key] = horse_figures
                logger.debug(f"Added speed figures for {row_key}: {horse_figures}")
            
            logger.info(f"Found speed figures for {len(speed_data['figures'])} horses")
        else:
            logger.warning(f"Could not find speed figure table on page: {figure_url}")
    
    except Exception as e:
        logger.error(f"Error scraping speed figures: {e}", exc_info=True)
    
    return speed_data
