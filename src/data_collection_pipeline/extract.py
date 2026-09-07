from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)


TARGET_URL = 'https://runfor.kr/'

WAIT_TIMEOUT = 10

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'

RACE_LINK_SELECTOR = ".race-cards a[href^='/race/']"
LOAD_MORE_SELECTOR = "button.race-load-more"

DETAIL_FIELD_MAP = {
    '일정': 'race_date',
    '집결': 'assembly_time',
    '장소': 'location',
    '종목': 'course',
    '주최': 'organizer',
}

RAW_COLUMNS = [
    'title',
    'race_status',
    'region',
    'location',
    'course',
    'race_date',
    'registration_period',
    'assembly_time',
    'organizer',
    'official_url',
    'phone',
    'email',
]

def create_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()

    if headless:
        options.add_argument('--headless=new')

    options.add_argument('--start-maximized')

    return webdriver.Chrome(options=options)


def load_all_marathon(driver):
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    try:
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, RACE_LINK_SELECTOR))
        )
    except TimeoutException as e:
        raise TimeoutException(f'대회 목록이 {WAIT_TIMEOUT}초 이내에 로딩되지 않았습니다.') from e

    initial_count = len(driver.find_elements(By.CSS_SELECTOR, RACE_LINK_SELECTOR))

    load_more_button = driver.find_element(By.CSS_SELECTOR, LOAD_MORE_SELECTOR)

    driver.execute_script(
        'arguments[0].scrollIntoView({block: "center"})',
        load_more_button
    )

    wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, LOAD_MORE_SELECTOR))
    )

    try:
        driver.execute_script(
            'arguments[0].click()',
            load_more_button
        )

    except StaleElementReferenceException:
        print(
            '대회 더보기 버튼의 DOM 참조가 변경되어 버튼을 다시 조회합니다.'
        )

        load_more_button = driver.find_element(
            By.CSS_SELECTOR,
            LOAD_MORE_SELECTOR
        )

        driver.execute_script(
            'arguments[0].click()',
            load_more_button
        )


    wait.until(
        lambda current_driver:
        len(current_driver.find_elements(By.CSS_SELECTOR, RACE_LINK_SELECTOR))
        > initial_count
    )

    after_count = len(driver.find_elements(By.CSS_SELECTOR, RACE_LINK_SELECTOR))
    print(f'대회 더보기 클릭 완료: {initial_count}개 -> {after_count}개')

    race_elements = driver.find_elements(By.CSS_SELECTOR, RACE_LINK_SELECTOR)

    return len(race_elements)


def parse_race_element(element):
    try:
        title = element.find_element(By.CSS_SELECTOR, 'strong.race-card-title').text.strip()
        detail_url = element.get_attribute('href')

    except NoSuchElementException as e:
        raise NoSuchElementException('대회 카드에서 대회 제목을 찾을 수 없습니다.') from e

    return {
        "title": title,
        "detail_url": detail_url,
    }


def collect_marathon_url(driver):
    race_cards = driver.find_elements(By.CSS_SELECTOR, '.race-card')

    race_list = list()

    for race in race_cards:
        element = parse_race_element(race)
        race_list.append(element)

    return race_list


def collect_race_detail(url):
    response = requests.get(url, timeout=(10, 30))
    response.raise_for_status()

    soup = BeautifulSoup(response.content, features='html.parser')
    detail_facts = soup.select_one('.detail-facts')
    fact_elements = detail_facts.select('dl>div')
    contact = soup.select_one('.contact-card')

    result = {}

    title = soup.select_one('.detail-title h1').text
    race_status = soup.select_one('.status-badge').text
    region = soup.select_one('span.detail-region').text
    registration_period = soup.select_one('.registration-info strong').text
    official_url = soup.select_one('.apply-card a').get('href')
    phone = contact.select_one('a[href*="tel:"]').text
    email = contact.select_one('a[href*="mail"]').text

    for element in fact_elements:
        key = element.select_one('dt').text.strip()
        value = element.select_one('dd').text

        field_name = DETAIL_FIELD_MAP.get(key)
        if field_name:
            result[field_name] = value

    result['title'] = title
    result['race_status'] = race_status
    result['region'] = region
    result['registration_period'] = registration_period
    result['official_url'] = official_url
    result['phone'] = phone
    result['email'] = email

    return result


def crawl_marathon_schedule(headless: bool = True) -> pd.DataFrame:
    """웹페이지에서 전체 마라톤 일정 상세 정보를 수집한다."""
    driver = create_driver(headless=headless)

    try:
        driver.get(TARGET_URL)
        load_count = load_all_marathon(driver)
        races = collect_marathon_url(driver)

    finally:
        driver.quit()

    details = list()

    for race in races:
        url = race['detail_url']
        details.append(collect_race_detail(url))

    raw_df = pd.DataFrame(details, columns=RAW_COLUMNS)

    print(f'전체 행 수 : {len(raw_df)}')
    print(f'전체 컬럼 수 : {len(raw_df.columns)}')
    print(f'수집된 대회 수 : {load_count}')

    return raw_df


def build_raw_file_path(directory: Path = RAW_DIR) -> Path:
    """현재 시각을 포함한 RAW CSV 저장 경로를 만든다."""
    timestamp = datetime.now().strftime('%y%m%d_%H%M%S')
    return directory / f'marathon_schedule_raw_{timestamp}.csv'


def save_raw_csv(
    df: pd.DataFrame,
    directory: Path = RAW_DIR,
) -> Path:
    """수집 결과를 UTF-8-SIG CSV로 저장한다."""
    directory.mkdir(parents=True, exist_ok=True)
    file_path = build_raw_file_path(directory)
    temp_path = file_path.with_suffix('.tmp.csv')

    try:
        df.to_csv(temp_path, encoding='utf-8-sig', index=False)
        temp_path.replace(file_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    return file_path


def verify_saved_raw_csv(
    saved_file: Path,
    original_df: pd.DataFrame,
) -> None:
    """RAW CSV 저장 전후의 행 수와 컬럼 순서를 검증한다."""
    saved_df = pd.read_csv(saved_file)

    if len(saved_df) != len(original_df):
        raise ValueError('RAW csv 저장 전후의 행 수가 다릅니다.')

    if list(saved_df.columns) != list(original_df.columns):
        raise ValueError('RAW csv 저장 전후의 컬럼 순서가 다릅니다.')


def run_extract(
    headless: bool = True,
    output_dir: Path | None = None,
) -> Path:
    """마라톤 일정을 수집하고 RAW CSV 파일 경로를 반환한다."""
    target_dir = output_dir if output_dir is not None else RAW_DIR

    print('=' * 70)
    print('1. Extract - RUNTRACK 마라톤 일정 수집 시작')
    print('=' * 70)
    print(f'수집 대상 URL : {TARGET_URL}')

    raw_df = crawl_marathon_schedule(headless=headless)
    saved_file = save_raw_csv(raw_df, directory=target_dir)
    verify_saved_raw_csv(saved_file, raw_df)

    print(f'RAW csv 저장 완료 : {saved_file}')
    return saved_file

