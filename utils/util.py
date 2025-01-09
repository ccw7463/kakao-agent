import os
from functools import wraps
from dotenv import load_dotenv
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer
import requests
from bs4 import BeautifulSoup

RESET = "\033[0m"        # Reset to default
RED = "\033[91m"         # Bright Red
BLUE = "\033[94m"        # Bright Blue
GREEN = "\033[92m"        # Bright Green
YELLOW = "\033[93m"       # Bright Yellow
PINK = "\033[95m"         # Bright Pink

def set_env():
    load_dotenv()
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "langchain-academy"

def trace_function(enable_print=True, only_func_name=False):
    def wrapper(func):
        @wraps(func)
        def wrapped(*args, **kwargs):  # 이름을 "wrapped"로 변경하여 구분
            if enable_print:
                if only_func_name:
                    print(f"{GREEN}\n🚀 Passing Through [{func.__name__}] ..{RESET}")
                else:
                    print(f"{GREEN}\n🚀 Passing Through [{func.__name__}] ..{RESET}")
                    print(f"\n#### [Input State]")
                    print(f"  args: {args}")
                    print(f"  kwargs: {kwargs}")
            result = func(*args, **kwargs)  # 원본 함수 호출
            if enable_print:
                if only_func_name:
                    pass
                else:
                    print(f"\n#### [Output State]")
                    print(f"  result: {result}")
            return result
        return wrapped
    return wrapper
    
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


def google_search_scrape(query:str, 
                         num_results:int=3) -> list:
    """
        Des:
            Google 검색 결과를 스크래핑하는 함수
        Args:
            query (str): 검색할 키워드
            num_results (int): 검색 결과 수
        Returns:
            list: 검색 결과를 담은 리스트
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    query = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={query}&num={num_results}"
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for g in soup.find_all("div", class_="tF2Cxc"):
        title = g.find("h3").text.upper()
        link = g.find("a")["href"]
        if link.endswith(".pdf"):
            continue
        results.append({"title": title, "link": link})
    return results