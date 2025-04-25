"""
Configuration settings for the Netkeiba scraper.
"""

# Base URL for netkeiba database pages
BASE_URL_NETKEIBA = "https://db.netkeiba.com"

# Base URL for JRA official site
BASE_URL_JRA = "https://www.jra.go.jp"

# Base URL for JMA weather API
BASE_URL_JMA = "https://www.jma.go.jp/bosai/forecast/data/forecast"

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

# URL template for netkeiba odds API
NETKEIBA_ODDS_API_URL = "https://race.netkeiba.com/api/api_get_jra_odds.html"

# URL template for commercial odds API
KEIBA_ODDS_API_URL = "https://api.team-nave.com/kb_odds/v1/odds"

# Time in seconds to wait for dynamic content to load in Selenium
SELENIUM_WAIT_TIME = 10

UPDATE_FREQUENCY = {
    "weather": 30,         # 気象データ更新頻度
    "track_condition": 30, # 馬場状態更新頻度
    "odds": 2,             # オッズ更新頻度
    "bias": 60             # バイアス指標更新頻度
}

UPDATE_THRESHOLDS = {
    "odds_change_percent": 15,  # オッズ変動閾値（%）
    "precipitation_change": 20,  # 降水確率変動閾値（%ポイント）
    "moisture_change": 2,        # 含水率変動閾値（%ポイント）
    "cushion_change": 0.5,       # クッション値変動閾値
    "wind_speed_change": 3       # 風速変動閾値（m/s）
}

JRA_CALENDAR_URL_TEMPLATE = f"{BASE_URL_JRA}/keiba/calendar{{year}}/index.html"

JRA_RACE_PDF_URL_TEMPLATE = f"{BASE_URL_JRA}/keiba/rpdf/{{year}}{{month}}/{{day}}/{{venue}}{{race}}.pdf"

PDF_HEADER_AREA = [70, 28, 108, 566]  # 1行目（枠番・馬番などの見出し）
PDF_DATA_AREA = [108, 28, 790, 566]   # 2行目以降（最大18頭分）
PDF_COLUMNS = [28, 70, 138, 278, 330, 382, 450, 512]  # カラム分割
