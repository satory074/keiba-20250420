"""
Scraping functions related to race day announcements and news.
"""
import re
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict, Any, List

from utils import clean_text
from logger_config import get_logger
from config import SELENIUM_WAIT_TIME

logger = get_logger(__name__)


def scrape_race_announcements(driver: WebDriver, race_id: str) -> Dict[str, Any]:
    """Scrapes race day announcements and news (A1.12, A5) for a race."""
    logger.info(f"Scraping race announcements for race {race_id}...")
    announcement_data = {"race_id": race_id, "announcements": []}
    announcement_url = f"https://race.netkeiba.com/race/news.html?race_id={race_id}"
    
    if not driver:
        logger.error("WebDriver not initialized. Cannot scrape race announcements.")
        return announcement_data
    
    try:
        logger.info(f"Fetching race announcements page with Selenium: {announcement_url}")
        driver.get(announcement_url)
        
        try:
            WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                EC.presence_of_element_located((By.CLASS_NAME, "Race_News_List"))
            )
            logger.debug("Race announcements page loaded.")
        except Exception as e:
            logger.error(f"Timeout or error waiting for race announcements page elements: {e}")
            return announcement_data
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        announcement_list = soup.find("div", class_="Race_News_List")
        if announcement_list and isinstance(announcement_list, Tag):
            announcement_items = announcement_list.find_all(["dl", "div"], class_=re.compile(r"News_Item|NewsItem"))
            
            for item in announcement_items:
                date_element = item.find(["dt", "div"], class_=re.compile(r"News_Date|NewsDate"))
                title_element = item.find(["dd", "div"], class_=re.compile(r"News_Title|NewsTitle"))
                content_element = item.find(["dd", "div"], class_=re.compile(r"News_Text|NewsText"))
                
                if title_element or content_element:
                    announcement = {
                        "datetime": clean_text(date_element.text) if date_element else None,
                        "title": clean_text(title_element.text) if title_element else None,
                        "content": clean_text(content_element.text) if content_element else None,
                        "announcement_type": None
                    }
                    
                    if announcement["title"]:
                        if re.search(r"出走取消|取消", announcement["title"]):
                            announcement["announcement_type"] = "scratch"  # A5.1
                        elif re.search(r"騎手変更", announcement["title"]):
                            announcement["announcement_type"] = "jockey_change"  # A5.2
                        elif re.search(r"馬場|コース変更", announcement["title"]):
                            announcement["announcement_type"] = "track_change"  # A5.3
                        elif re.search(r"発走時刻|時刻変更", announcement["title"]):
                            announcement["announcement_type"] = "start_time_change"  # A5.4
                        elif re.search(r"不利|妨害|制裁", announcement["title"]):
                            announcement["announcement_type"] = "stewards_inquiry"  # A5.5
                    
                    announcement_data["announcements"].append(announcement)
            
            logger.info(f"Extracted {len(announcement_data['announcements'])} race announcements")
        else:
            logger.warning("Could not find race announcements list on page.")
    
    except Exception as e:
        logger.error(f"Error scraping race announcements for race {race_id}: {e}", exc_info=True)
    
    return announcement_data
