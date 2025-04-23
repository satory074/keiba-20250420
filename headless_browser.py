"""
Headless browser module with robust WebDriver initialization and fallback mechanisms.
"""
import os
import time
import logging
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver

from logger_config import get_logger

logger = get_logger(__name__)

# Maximum number of retries for WebDriver initialization
MAX_INIT_RETRIES = 3

# Maximum number of retries for page loading
MAX_LOAD_RETRIES = 3

# Delay between retries (seconds)
RETRY_DELAY = 2


def initialize_driver_with_fallback() -> Optional[WebDriver]:
    """
    Initialize a WebDriver with multiple fallback mechanisms.
    
    Returns:
        WebDriver instance or None if all initialization attempts fail
    """
    logger.info("Initializing WebDriver with fallback mechanisms...")
    
    # Try different initialization strategies
    strategies = [
        _init_headless_chrome,
        _init_regular_chrome,
        _init_with_explicit_driver_path,
    ]
    
    for attempt, strategy in enumerate(strategies, 1):
        logger.info(f"WebDriver initialization attempt {attempt}/{len(strategies)} using {strategy.__name__}")
        
        driver = strategy()
        if driver:
            logger.info(f"Successfully initialized WebDriver using {strategy.__name__}")
            return driver
        
        logger.warning(f"WebDriver initialization failed using {strategy.__name__}")
        time.sleep(RETRY_DELAY)
    
    logger.error("All WebDriver initialization attempts failed")
    return None


def _init_headless_chrome() -> Optional[WebDriver]:
    """
    Initialize a headless Chrome WebDriver.
    
    Returns:
        WebDriver instance or None if initialization fails
    """
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Add user agent to avoid detection
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        # Disable images for faster loading
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # Test the driver with a simple page load
        driver.get("https://www.google.com")
        
        return driver
    except Exception as e:
        logger.error(f"Error initializing headless Chrome: {e}")
        return None


def _init_regular_chrome() -> Optional[WebDriver]:
    """
    Initialize a regular (non-headless) Chrome WebDriver.
    
    Returns:
        WebDriver instance or None if initialization fails
    """
    try:
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        
        # Add user agent to avoid detection
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        
        # Test the driver with a simple page load
        driver.get("https://www.google.com")
        
        return driver
    except Exception as e:
        logger.error(f"Error initializing regular Chrome: {e}")
        return None


def _init_with_explicit_driver_path() -> Optional[WebDriver]:
    """
    Initialize a Chrome WebDriver with explicit driver path.
    
    Returns:
        WebDriver instance or None if initialization fails
    """
    try:
        # Try to find chromedriver in common locations
        driver_paths = [
            "/usr/bin/chromedriver",
            "/usr/local/bin/chromedriver",
            "/snap/bin/chromedriver",
            os.path.expanduser("~/chromedriver"),
        ]
        
        for driver_path in driver_paths:
            if os.path.exists(driver_path):
                logger.info(f"Found chromedriver at {driver_path}")
                
                options = Options()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                
                service = Service(executable_path=driver_path)
                driver = webdriver.Chrome(service=service, options=options)
                driver.set_page_load_timeout(30)
                
                # Test the driver with a simple page load
                driver.get("https://www.google.com")
                
                return driver
        
        logger.warning("Could not find chromedriver in common locations")
        return None
    except Exception as e:
        logger.error(f"Error initializing Chrome with explicit driver path: {e}")
        return None


def safe_get_with_retry(driver: WebDriver, url: str) -> bool:
    """
    Safely navigate to a URL with retry mechanism.
    
    Args:
        driver: WebDriver instance
        url: URL to navigate to
        
    Returns:
        True if navigation was successful, False otherwise
    """
    if not driver:
        logger.error("Cannot navigate: WebDriver is None")
        return False
    
    for attempt in range(1, MAX_LOAD_RETRIES + 1):
        try:
            logger.info(f"Navigating to {url} (attempt {attempt}/{MAX_LOAD_RETRIES})")
            driver.get(url)
            return True
        except TimeoutException:
            logger.warning(f"Timeout loading {url} (attempt {attempt}/{MAX_LOAD_RETRIES})")
            if attempt < MAX_LOAD_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            if attempt < MAX_LOAD_RETRIES:
                time.sleep(RETRY_DELAY)
    
    logger.error(f"Failed to load {url} after {MAX_LOAD_RETRIES} attempts")
    return False
