"""
JRA関連の定数と設定を提供するモジュール。
"""

BASE_URL_JRA = "https://www.jra.go.jp"

CALENDAR_URL_TEMPLATE = f"{BASE_URL_JRA}/keiba/calendar{{year}}/index.html"

RACE_PDF_URL_TEMPLATE = f"{BASE_URL_JRA}/keiba/rpdf/{{year}}{{month}}/{{day}}/{{venue}}{{race}}.pdf"

PDF_HEADER_AREA = [70, 28, 108, 566]  # 1行目（枠番・馬番などの見出し）
PDF_DATA_AREA = [108, 28, 790, 566]   # 2行目以降（最大18頭分）
PDF_COLUMNS = [28, 70, 138, 278, 330, 382, 450, 512]  # カラム分割

TRACK_CONDITION_CODES = {
    "良": "good",
    "稍重": "slightly_heavy",
    "重": "heavy",
    "不良": "bad"
}

WEATHER_CODES = {
    "晴": "sunny",
    "曇": "cloudy",
    "小雨": "light_rain",
    "雨": "rain",
    "小雪": "light_snow",
    "雪": "snow"
}

VENUE_CODES = {
    "東京": "tokyo",
    "中山": "nakayama",
    "阪神": "hanshin",
    "京都": "kyoto",
    "福島": "fukushima",
    "新潟": "niigata",
    "小倉": "kokura",
    "札幌": "sapporo",
    "函館": "hakodate",
    "中京": "chukyo"
}
