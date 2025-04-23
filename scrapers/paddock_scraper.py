"""
Scraping functions related to horse condition and paddock information.
"""
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils import clean_text
from logger_config import get_logger
from config import SELENIUM_WAIT_TIME

logger = get_logger(__name__)


def scrape_paddock_info(driver: WebDriver, race_id: str):
    """Scrapes horse condition and paddock information (B6) for a race."""
    logger.info(f"Scraping paddock information for race {race_id}...")
    paddock_data = {"race_id": race_id, "paddock_observations": {}}
    paddock_url = f"https://race.netkeiba.com/race/paddock.html?race_id={race_id}"
    
    if not driver:
        logger.error("WebDriver not initialized. Cannot scrape paddock information.")
        return paddock_data
    
    try:
        logger.info(f"Fetching paddock page with Selenium: {paddock_url}")
        driver.get(paddock_url)
        
        try:
            WebDriverWait(driver, SELENIUM_WAIT_TIME).until(
                EC.presence_of_element_located((By.CLASS_NAME, "Paddock_Horse_List"))
            )
            logger.debug("Paddock page loaded.")
        except Exception as e:
            logger.error(f"Timeout or error waiting for paddock page elements: {e}")
            return paddock_data
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        paddock_comments_div = soup.find("div", class_="Paddock_Comment")
        if paddock_comments_div:
            paddock_data["general_comments"] = clean_text(paddock_comments_div.text)
        
        horse_list = soup.find("div", class_="Paddock_Horse_List")
        if horse_list and isinstance(horse_list, Tag):
            horse_items = horse_list.find_all("div", class_="Horse_Box")
            
            for horse_item in horse_items:
                umaban_div = horse_item.find("div", class_="Num")
                horse_name_div = horse_item.find("div", class_="Horse_Name")
                condition_div = horse_item.find("div", class_="Horse_Condition")
                
                if umaban_div and horse_name_div:
                    umaban = clean_text(umaban_div.text)
                    horse_name = clean_text(horse_name_div.text)
                    
                    horse_data = {
                        "horse_name": horse_name,
                        "condition_text": clean_text(condition_div.text) if condition_div else None
                    }
                    
                    if condition_div:
                        sweat_match = re.search(r"汗:(.*?)(?:\s|$)", condition_div.text)
                        if sweat_match:
                            horse_data["sweating"] = clean_text(sweat_match.group(1))
                        
                        muscle_match = re.search(r"体つき:(.*?)(?:\s|$)", condition_div.text)
                        if muscle_match:
                            horse_data["muscle_condition"] = clean_text(muscle_match.group(1))
                        
                        mental_match = re.search(r"気配:(.*?)(?:\s|$)", condition_div.text)
                        if mental_match:
                            horse_data["mental_state"] = clean_text(mental_match.group(1))
                        
                        walking_match = re.search(r"歩様:(.*?)(?:\s|$)", condition_div.text)
                        if walking_match:
                            horse_data["walking_style"] = clean_text(walking_match.group(1))
                    
                    image_div = horse_item.find("div", class_="Horse_Photo")
                    if image_div:
                        img_tag = image_div.find("img")
                        if img_tag and "src" in img_tag.attrs:
                            horse_data["paddock_image_url"] = img_tag["src"]
                    
                    paddock_data["paddock_observations"][umaban] = horse_data
            
            logger.info(f"Extracted paddock observations for {len(paddock_data['paddock_observations'])} horses")
        else:
            logger.warning("Could not find paddock horse list on page.")
    
    except Exception as e:
        logger.error(f"Error scraping paddock information for race {race_id}: {e}", exc_info=True)
    
    return paddock_data
