import os
from dotenv import load_dotenv

def set_env():
    load_dotenv()
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "langchain-academy"

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import platform
from glob import glob

def initialize_browser(use_headless: bool = True, 
                       window_size: str = '1920,1080', 
                       remote_debugging_port: int = 9222, 
                       disable_images: bool = True, 
                       no_sandbox: bool = True, 
                       disable_dev_shm_usage: bool = True, 
                       disable_gpu: bool = True, 
                       disable_extensions: bool = True, 
                       disable_software_rasterizer: bool = True,
                       user_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36'
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
    if use_headless:
        options.add_argument('--headless')
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
        # options.add_argument(f'user-agent={user_agent}')

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
            # print("구동중인 OS는 Windows입니다.")
            # print("ChromeDriver가 존재합니다. 초기화 진행합니다.")
            chrome_driver_path_pattern = 'C:/Users/chang/Desktop/WORKSPACE/**/chromedriver.exe'
            matching_files = glob(chrome_driver_path_pattern, recursive=True)
            if not matching_files:
                raise FileNotFoundError("ChromeDriver 파일을 찾을 수 없습니다.")
            chrome_driver_path = sorted(matching_files)[-1]
            
        # Mac OS의 경우 ChromeDriver 로드
        elif system_os == "darwin":
            # print("구동중인 OS는 Mac입니다.")
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

from urllib.parse import urlparse, urlunparse, urljoin
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer

def extract_info_from_url(full_url:str) -> dict:
    """
        Des:
            URL에서 Base URL을 추출하는 함수
        Args:
            full_url (str): 완전한 URL
        Returns:
            dict: 추출된 정보를 담은 딕셔너리
    """
    parsed_url = urlparse(full_url)  # URL을 파싱
    schema = parsed_url.scheme
    domain = parsed_url.netloc
    base_url = urlunparse((schema, domain, '', '', '', ''))  # Base URL만 재조합
    return {
        "schema":schema,
        "domain":domain,
        "base_url":base_url
    }
    
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
