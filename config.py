"""
Configuration settings for the Netkeiba scraper.
"""

# Base URL for netkeiba database pages
BASE_URL_NETKEIBA = "https://db.netkeiba.com"

# Headers for HTTP requests to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}

# Delay in seconds between requests to avoid overloading the server
REQUEST_DELAY = 1

# URL template for the shutuba_past page
SHUTUBA_PAST_URL = "https://race.netkeiba.com/race/shutuba_past.html?race_id={}&rf=shutuba_submenu"

# URL template for the paddock page
PADDOCK_URL = "https://race.netkeiba.com/race/paddock.html?race_id={}"

# URL template for race announcements/news
RACE_NEWS_URL = "https://race.netkeiba.com/race/news.html?race_id={}"

# Time in seconds to wait for dynamic content to load in Selenium
SELENIUM_WAIT_TIME = 10
