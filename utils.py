"""
Utility functions for the Netkeiba scraper.
"""
import re
import time

import requests
from bs4 import BeautifulSoup

# Import logger and config
from logger_config import get_logger
from config import HEADERS, REQUEST_DELAY, SELENIUM_WAIT_TIME
from headless_browser import initialize_driver_with_fallback, safe_get_with_retry

# Get logger instance for this module
logger = get_logger(__name__)


def initialize_driver():
    """
    Initializes a headless Chrome WebDriver with fallback mechanisms.
    
    This function uses the robust implementation from headless_browser.py
    which provides multiple fallback strategies for WebDriver initialization.
    """
    logger.info("Initializing WebDriver with fallback mechanisms...")
    return initialize_driver_with_fallback()


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
