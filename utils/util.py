import os
import re
import random
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer

RESET = "\033[0m"  # Reset to default
RED = "\033[91m"  # Bright Red
BLUE = "\033[94m"  # Bright Blue
GREEN = "\033[92m"  # Bright Green
YELLOW = "\033[93m"  # Bright Yellow
PINK = "\033[95m"  # Bright Pink

def set_env():
    load_dotenv()
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")


def extract_content(link: str) -> tuple[str, str]:
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
    docs_transformed = html2text.transform_documents(docs, metadata_type="html")
    desc = docs_transformed[0].metadata.get("description", "")
    detailed_content = docs_transformed[0].page_content
    return desc, detailed_content


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


from multiprocessing import Process, Queue

def _run_playwright_in_process(search_term: str, SEARCH_RESULT_COUNT: int, queue: Queue):
    """
    Des:
        별도 프로세스에서 실행될 Playwright 함수
            - 랭그래프가 동기식으로 실행되는데, 웹스크래핑시 비동기로 계속 실행돼서
            - 멀티프로세싱을 사용하여 Playwright를 별도의 프로세스에서 실행하여 최종적으로 동기식 실행
    Args:
        search_term (str): 검색할 키워드
        SEARCH_RESULT_COUNT (int): 검색 결과 수
        queue (Queue): 결과를 전달할 큐
    """
    try:
        with sync_playwright() as p:
            # 기존 google_search_scrape 로직
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                java_script_enabled=True,
            )
            page = context.new_page()
            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
            """
            )
            
            try:
                page.wait_for_timeout(2000 + random.randint(500, 1500))
                page.goto("https://www.google.com")
                page.wait_for_timeout(1000 + random.randint(500, 1000))
                page.type("#APjFqb", search_term, delay=100)
                page.wait_for_timeout(500)
                page.press("#APjFqb", "Enter")
                page.wait_for_selector("div.yuRUbf", timeout=10000)
                page.wait_for_timeout(2000)

                results = []
                search_results = page.query_selector_all("div.yuRUbf")
                for result in search_results[:SEARCH_RESULT_COUNT]:
                    title_elem = result.query_selector("h3.LC20lb")
                    title = title_elem.inner_text() if title_elem else ""
                    link_elem = result.query_selector("a")
                    link = link_elem.get_attribute("href") if link_elem else ""
                    results.append({"title": title, "link": link})
                queue.put(results)
            except Exception as e:
                print(f"에러 발생: {str(e)}")
                page.screenshot(path=f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_error.png')
                queue.put(None)
            finally:
                browser.close()
    except Exception as e:
        print(f"Playwright 초기화 에러: {str(e)}")
        queue.put(None)

def google_search_scrape(search_term: str, SEARCH_RESULT_COUNT: int):
    """멀티프로세싱을 사용하는 메인 함수"""
    queue = Queue()
    process = Process(target=_run_playwright_in_process, 
                    args=(search_term, SEARCH_RESULT_COUNT, queue))
    process.start()
    results = queue.get()  # 결과를 기다림
    process.join()
    
    if results is None:
        raise Exception("검색 실패")
    return results

'''
def google_search_scrape(search_term: str, SEARCH_RESULT_COUNT: int):
    with sync_playwright() as p:
        # 브라우저 초기화
        print("브라우저 초기화")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        # 브라우저 컨텍스트에 추가 설정
        print("브라우저 컨텍스트 초기화")
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            java_script_enabled=True,
        )

        page = context.new_page()

        # webdriver 제거
        print("webdriver 제거")
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
        """
        )

        try:
            print("구글 페이지 이동")
            page.wait_for_timeout(2000 + random.randint(500, 1500))
            page.goto("https://www.google.com")
            print("검색어 입력")
            page.wait_for_timeout(1000 + random.randint(500, 1000))
            page.type("#APjFqb", search_term, delay=100)
            print("엔터 입력")
            page.wait_for_timeout(500)
            page.press("#APjFqb", "Enter")
            print("검색 결과 로드 대기")
            page.wait_for_selector("div.yuRUbf", timeout=10000)
            print("검색 결과 로드 완료")
            page.wait_for_timeout(2000)

            results = []
            search_results = page.query_selector_all("div.yuRUbf")
            for result in search_results[:SEARCH_RESULT_COUNT]:
                title_elem = result.query_selector("h3.LC20lb")
                title = title_elem.inner_text() if title_elem else ""
                link_elem = result.query_selector("a")
                link = link_elem.get_attribute("href") if link_elem else ""
                results.append({"title": title, "link": link})
            return results

        except Exception as e:
            print(f"에러 발생: {str(e)}")
            page.screenshot(
                path=f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_error.png'
            )
            raise e
        finally:
            browser.close()
'''

'''비동기부분
async def google_search_scrape(search_term: str, SEARCH_RESULT_COUNT: int):
    async with async_playwright() as p:

        # 브라우저 초기화
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        # 브라우저 컨텍스트에 추가 설정
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            java_script_enabled=True,
        )

        page = await context.new_page()

        # webdriver 제거
        await page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
        """
        )

        try:
            await page.wait_for_timeout(2000 + random.randint(500, 1500))
            await page.goto("https://www.google.com")
            await page.wait_for_timeout(1000 + random.randint(500, 1000))
            await page.type("#APjFqb", search_term, delay=100)
            await page.wait_for_timeout(500)
            await page.press("#APjFqb", "Enter")
            await page.wait_for_selector("div.yuRUbf", timeout=10000)
            await page.wait_for_timeout(2000)
            results = []
            search_results = await page.query_selector_all("div.yuRUbf")
            for result in search_results[:SEARCH_RESULT_COUNT]:
                title_elem = await result.query_selector("h3.LC20lb")
                title = await title_elem.inner_text() if title_elem else ""
                link_elem = await result.query_selector("a")
                link = await link_elem.get_attribute("href") if link_elem else ""
                results.append({"title": title, "link": link})
            return results

        except Exception as e:
            await page.screenshot(
                path=f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_error.png'
            )
            raise e
        finally:
            await browser.close()
'''

'''현재 미사용
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
'''
