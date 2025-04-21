"""
Utility functions for the Netkeiba scraper.
"""
import re
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Import logger and config
from logger_config import get_logger
from config import HEADERS, REQUEST_DELAY, SELENIUM_WAIT_TIME

# Get logger instance for this module
logger = get_logger(__name__)


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
