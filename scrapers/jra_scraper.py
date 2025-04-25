"""
JRA公式サイトからデータを取得するスクレイピング機能。
カレンダー情報と出馬表PDFを処理します。
"""
import os
import re
import requests
import pandas as pd
import tabula
from datetime import datetime
from bs4 import BeautifulSoup
import tempfile
from typing import Dict, List, Any, Optional, Tuple

from logger_config import get_logger
from scrapers.jra_constants import (
    BASE_URL_JRA, CALENDAR_URL_TEMPLATE, RACE_PDF_URL_TEMPLATE,
    PDF_HEADER_AREA, PDF_DATA_AREA, PDF_COLUMNS, VENUE_CODES
)

logger = get_logger(__name__)

def get_jra_calendar(year: int = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    JRA公式サイトから開催カレンダーを取得します。
    
    Args:
        year: 取得する年。指定しない場合は現在の年を使用。
        
    Returns:
        日付ごとの開催情報を含む辞書
    """
    if year is None:
        year = datetime.now().year
        
    url = CALENDAR_URL_TEMPLATE.format(year=year)
    logger.info(f"JRA開催カレンダーを取得中: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        
        calendar_data = {}
        
        calendar_tables = soup.find_all("table", class_=re.compile(r"calendar|Calendar"))
        for table in calendar_tables:
            month_heading = table.find_previous("h2", class_=re.compile(r"month|Month"))
            if not month_heading:
                continue
                
            month_match = re.search(r'(\d+)月', month_heading.text)
            if not month_match:
                continue
                
            month = int(month_match.group(1))
            
            for day_cell in table.find_all("td", class_=re.compile(r"calendar-day|has-races")):
                day_text = day_cell.find("div", class_="day")
                if not day_text:
                    continue
                    
                day = int(re.search(r'(\d+)', day_text.text).group(1))
                date_str = f"{year:04d}{month:02d}{day:02d}"
                
                venues = []
                venue_links = day_cell.find_all("a")
                for link in venue_links:
                    venue_text = link.text.strip()
                    venue_code = next((code for name, code in VENUE_CODES.items() if name in venue_text), None)
                    if venue_code:
                        venues.append({
                            "venue_name": venue_text,
                            "venue_code": venue_code,
                            "url": link.get("href")
                        })
                
                if venues:
                    calendar_data[date_str] = venues
        
        logger.info(f"JRA開催カレンダー取得完了。{len(calendar_data)}日分の開催情報を取得。")
        return calendar_data
        
    except Exception as e:
        logger.error(f"JRA開催カレンダー取得エラー: {e}", exc_info=True)
        return {}

def get_race_entries_pdf(race_id: str) -> Optional[str]:
    """
    レースIDに基づいて出馬表PDFを取得し、一時ファイルに保存します。
    
    Args:
        race_id: レースID（yyyymmddnnnrr形式）
        
    Returns:
        保存されたPDFファイルのパス。取得失敗時はNone。
    """
    try:
        year = race_id[0:4]
        month = race_id[4:6]
        day = race_id[6:8]
        venue_code = race_id[8:10]
        race_num = race_id[10:12]
        
        jra_venue_code = None
        for name, code in VENUE_CODES.items():
            if venue_code == code[:2]:
                jra_venue_code = name
                break
                
        if not jra_venue_code:
            logger.error(f"不明な会場コード: {venue_code}")
            return None
            
        pdf_url = RACE_PDF_URL_TEMPLATE.format(
            year=year, month=month, day=day,
            venue=jra_venue_code, race=race_num
        )
        
        logger.info(f"出馬表PDFを取得中: {pdf_url}")
        
        response = requests.get(pdf_url)
        response.raise_for_status()
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(response.content)
            pdf_path = temp_file.name
            
        logger.info(f"出馬表PDF保存完了: {pdf_path}")
        return pdf_path
        
    except Exception as e:
        logger.error(f"出馬表PDF取得エラー: {e}", exc_info=True)
        return None

def parse_race_entries_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """
    出馬表PDFを解析して馬の情報を抽出します。
    
    Args:
        pdf_path: PDFファイルのパス
        
    Returns:
        馬のリスト。各馬の情報を含む辞書のリスト。
    """
    logger.info(f"出馬表PDFを解析中: {pdf_path}")
    
    try:
        dfs = tabula.read_pdf(
            pdf_path,
            pages="all",
            area=[PDF_DATA_AREA],
            columns=PDF_COLUMNS,
            lattice=True,
            pandas_options={"header": 0}
        )
        
        if not dfs:
            logger.warning(f"PDFからテーブルを抽出できませんでした: {pdf_path}")
            return []
            
        entries_df = pd.concat(dfs, ignore_index=True)
        
        expected_columns = ["枠番", "馬番", "馬名", "性齢", "斤量", "騎手", "調教師", "馬体重", "備考"]
        
        if len(entries_df.columns) != len(expected_columns):
            logger.warning(f"列数が期待と異なります: 期待={len(expected_columns)}, 実際={len(entries_df.columns)}")
            min_cols = min(len(expected_columns), len(entries_df.columns))
            entries_df = entries_df.iloc[:, :min_cols]
            expected_columns = expected_columns[:min_cols]
            
        entries_df.columns = expected_columns
        
        entries = []
        for _, row in entries_df.iterrows():
            entry = {}
            for col in entries_df.columns:
                value = row[col]
                if pd.notna(value):
                    entry[col] = value
            
            if "性齢" in entry and entry["性齢"]:
                sex_age = str(entry["性齢"])
                entry["sex"] = sex_age[0]  # 最初の文字が性別（牡/牝/セ）
                entry["age"] = int(sex_age[1:]) if sex_age[1:].isdigit() else None
            
            if "馬体重" in entry and entry["馬体重"]:
                weight_str = str(entry["馬体重"])
                weight_match = re.search(r'(\d+)(?:\(([+-]\d+)\))?', weight_str)
                if weight_match:
                    entry["horse_weight"] = int(weight_match.group(1))
                    if weight_match.group(2):
                        entry["horse_weight_diff"] = weight_match.group(2)
            
            entries.append(entry)
        
        logger.info(f"出馬表PDF解析完了。{len(entries)}頭の馬情報を抽出。")
        return entries
        
    except Exception as e:
        logger.error(f"出馬表PDF解析エラー: {e}", exc_info=True)
        return []

def get_race_info_from_jra(race_id: str) -> Dict[str, Any]:
    """
    JRA公式サイトからレース情報を取得します。
    
    Args:
        race_id: レースID
        
    Returns:
        レース情報を含む辞書
    """
    logger.info(f"JRAからレース情報を取得中: {race_id}")
    
    pdf_path = get_race_entries_pdf(race_id)
    if not pdf_path:
        return {}
        
    try:
        entries = parse_race_entries_pdf(pdf_path)
        
        race_info = {
            "race_id": race_id,
            "horses": entries,
            "source": "JRA公式",
            "timestamp": datetime.now().isoformat()
        }
        
        os.remove(pdf_path)
        
        return race_info
        
    except Exception as e:
        logger.error(f"JRAレース情報取得エラー: {e}", exc_info=True)
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
        return {}
