import os
import re
import json
import requests
import platform
from functools import wraps
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from glob import glob
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer

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


def initialize_browser(use_headless: bool = False, 
                    window_size: str = '1920,1080', 
                    remote_debugging_port: int = 9222, 
                    disable_images: bool = True, 
                    no_sandbox: bool = True, 
                    disable_dev_shm_usage: bool = True, 
                    disable_gpu: bool = True, 
                    disable_extensions: bool = True, 
                    disable_software_rasterizer: bool = True,
                    user_agent: str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
) -> webdriver.Chrome:
    """
        Des:
            Chrome 브라우저를 초기화하는 함수
        Args:
            use_headless (bool): 헤드리스 모드로 실행할지 여부 (기본값: False)
            no_sandbox (bool): 샌드박스를 비활성화할지 여부 (기본값: True)
            window_size (str): 브라우저 창 크기 설정 (기본값: '1920,1080')
            remote_debugging_port (int): 원격 디버깅에 사용할 포트 번호 (기본값: 9222)
            disable_images (bool): 이미지 로드를 비활성화할지 여부 (기본값: True)
            disable_dev_shm_usage (bool): /dev/shm 사용을 비활성화할지 여부 (기본값: True)
            disable_gpu (bool): GPU 가속을 비활성화할지 여부 (기본값: True)
            disable_extensions (bool): 확장 프로그램을 비활성화할지 여부 (기본값: True)
            disable_software_rasterizer (bool): 소프트웨어 래스터라이저를 비활성화할지 여부 (기본값: True)
        Returns:
            webdriver.Chrome: 초기화된 Chrome 브라우저 객체
    """
    options = webdriver.ChromeOptions()
    
    # 도커환경 필수옵션
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    
    if use_headless:
        options.add_argument('--headless=new')
    if no_sandbox:
        options.add_argument('--no-sandbox')
    if disable_dev_shm_usage:
        options.add_argument('--disable-dev-shm-usage')
    if disable_gpu:
        options.add_argument('--disable-gpu')
    if remote_debugging_port:
        options.add_argument(f'--remote-debugging-port={remote_debugging_port}')
    if disable_extensions:
        options.add_argument('--disable-extensions')
    if disable_software_rasterizer:
        options.add_argument('--disable-software-rasterizer')
    if disable_images:
        options.add_argument('--blink-settings=imagesEnabled=false')
    if window_size:
        options.add_argument(f'--window-size={window_size}')
    if user_agent:
        options.add_argument(f'--user-agent={user_agent}')
    
    try:
        # 현재 OS 확인
        system_os = platform.system().lower()
        
        # 리눅스 OS의 경우 ChromeDriver 로드
        if system_os == 'linux':
            # print("구동중인 OS는 Linux입니다.")
            # print("ChromeDriver가 존재합니다. 초기화 진행합니다.")
            home_path = os.path.expanduser('~')
            chrome_driver_path = os.path.join(home_path, '.wdm', 'drivers', 'chromedriver', 'linux64')
            latest_version = sorted(os.listdir(chrome_driver_path))[-1]  # 가장 최신 버전 선택
            chrome_driver_path = os.path.join(chrome_driver_path, latest_version, 'chromedriver')
            
        # 윈도우 OS의 경우 ChromeDriver 로드
        elif system_os == 'windows':
            chrome_driver_path_pattern = 'C:/Users/chang/Desktop/WORKSPACE/**/chromedriver.exe'
            matching_files = glob(chrome_driver_path_pattern, recursive=True)
            if not matching_files:
                raise FileNotFoundError("ChromeDriver 파일을 찾을 수 없습니다.")
            chrome_driver_path = sorted(matching_files)[-1]
            
        # Mac OS의 경우 ChromeDriver 로드
        elif system_os == "darwin":
            chrome_driver_path = None
            
        # 지원되지 않는 OS의 경우 예외 발생
        else:
            raise EnvironmentError(f"지원되지 않는 OS: {system_os}")

        # print("ChromeDriver가 존재합니다. 초기화 진행합니다.")
        browser = webdriver.Chrome(service=Service(chrome_driver_path), options=options)

    except Exception as e:
        # ChromeDriver가 없을 경우 설치 과정 실행
        print(f"ChromeDriver가 존재하지 않습니다. 설치 과정을 진행합니다. 오류: {e}")
        browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return browser