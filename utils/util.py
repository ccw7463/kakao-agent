import os
from functools import wraps
from dotenv import load_dotenv
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta

RESET = "\033[0m"        # Reset to default
RED = "\033[91m"         # Bright Red
BLUE = "\033[94m"        # Bright Blue
GREEN = "\033[92m"        # Bright Green
YELLOW = "\033[93m"       # Bright Yellow
PINK = "\033[95m"         # Bright Pink

def set_env():
    load_dotenv()
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    
def extract_content(link:str) -> tuple[str, str]:
    """
        Des:
            주어진 링크에 대한 내용 추출하는 함수
        Args:
            link (str): 추출할 링크
        Returns:
            tuple[str, str]: 추출된 내용을 담은 튜플
    """
    loader = AsyncHtmlLoader(link)
    docs = loader.load()
    html2text = Html2TextTransformer()
    docs_transformed = html2text.transform_documents(docs,metadata_type="html")
    desc = docs_transformed[0].metadata.get('description',"")
    detailed_content = docs_transformed[0].page_content
    return desc,detailed_content


def parse_relative_date(relative_date: str) -> str:
    """
        Des:
            날짜 표현 변환 함수
        Args:
            relative_date (str): 상대적인 날짜 표현 (~시간 전, ~일 전 표현)
        Returns:
            str: 절대 날짜 (YYYY. MM. DD.)
    """
    now = datetime.now()

    if "시간 전" in relative_date:
        hours = int(re.search(r"(\d+)", relative_date).group(1))
        result_date = now - timedelta(hours=hours)
    elif "일 전" in relative_date:
        days = int(re.search(r"(\d+)", relative_date).group(1))
        result_date = now - timedelta(days=days)
    elif "분 전" in relative_date:
        minutes = int(re.search(r"(\d+)", relative_date).group(1))
        result_date = now - timedelta(minutes=minutes)
    else:
        return relative_date

    return result_date.strftime("%Y. %m. %d.")

def google_search_scrape(query: str, 
                         SEARCH_RESULT_COUNT: int = 3,
                         SEARCH_RETRY_COUNT : int = 3,
                         SEARCH_MINIMUM_RESULT: int = 1) -> list:
    """
        Des:
            Google 검색 결과를 스크래핑하는 함수 (날짜 포함)
        Args:
            query (str): 검색할 키워드
            SEARCH_RESULT_COUNT (int): 검색 결과 수
            SEARCH_RETRY_COUNT (int): 검색 시도 횟수
            SEARCH_MINIMUM_RESULT (int): 최소 검색 결과 수
        Returns:
            list: 검색 결과를 담은 리스트
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    query = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={query}&num={SEARCH_RESULT_COUNT}"
    results = []
    for _ in range(SEARCH_RETRY_COUNT):
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        for g in soup.find_all("div", class_="tF2Cxc"):
            title = g.find("h3").text.upper()
            link = g.find("a")["href"]
            date_span = g.find("span", class_="LEwnzc Sqrs4e")
            date_text = date_span.text if date_span else "No date available"
            if "전" in date_text:
                date = parse_relative_date(date_text)
            else:
                date = date_text

            if link.endswith(".pdf"):
                continue
            results.append({
                "title": title,
                "link": link,
                "date": date.replace(" — ","").strip()
            })
        if len(results) >= SEARCH_MINIMUM_RESULT:
            break
    return results