"""
RUNTRACK의 마라톤 일정 원본 데이터를 수집하는 Extract 모듈입니다.

runfor.kr 메인 페이지는 JavaScript 실행 후 대회 목록이 표시되므로
Selenium을 사용하여 동적 목록을 로딩하고 더보기 버튼을 처리합니다.
대회별 상세 페이지는 requests와 BeautifulSoup으로 요청 및 파싱합니다.

수집한 데이터는 가공하지 않은 RAW DataFrame으로 구성하고,
수집 시각이 포함된 CSV 파일로 data/raw 폴더에 저장합니다.

저장 구조:
    data/raw/
        marathon_schedule_raw_YYMMDD_HHMMSS.csv

반환값:
    run_extract()
        생성된 RAW CSV 파일 경로
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import (
    APP_TIMEZONE,
    CONNECT_TIMEOUT,
    LOAD_MORE_SELECTOR,
    RACE_LINK_SELECTOR,
    RAW_DIR,
    READ_TIMEOUT,
    TARGET_URL,
    WAIT_TIMEOUT,
)

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
    """
    Selenium Chrome WebDriver를 생성한다.

    Args:
        headless:
            True이면 브라우저 UI를 표시하지 않는 headless 모드로 실행

    Returns:
        설정이 적용된 Selenium Chrome WebDriver
    """
    
    options = Options()

    if headless:
        options.add_argument('--headless=new')

    options.add_argument('--start-maximized')

    return webdriver.Chrome(options=options)


def load_all_marathon(driver):
    """
    대회 목록을 기다린 뒤 더보기 버튼을 클릭하여 추가 대회를 로딩한다.

    Args:
        driver:
            runfor.kr 메인 페이지를 제어하는 Selenium WebDriver

    Returns:
        더보기 처리 후 DOM에서 확인한 대회 링크 요소 수

    Raises:
        TimeoutException:
            대회 목록이 제한 시간 안에 로딩되지 않거나 더보기 후 목록이 증가하지 않는 경우

        NoSuchElementException:
            더보기 버튼을 찾을 수 없는 경우
    """

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
    """
    대회 카드 요소에서 대회 제목과 상세 페이지 URL을 추출한다.

    Args:
        element:
            한 건의 대회 카드 Selenium WebElement

    Returns:
        title과 detail_url을 담은 딕셔너리

    Raises:
        NoSuchElementException:
            대회 카드에서 제목 요소를 찾을 수 없는 경우
    """

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
    """
    현재 페이지에 로딩된 대회 카드의 제목과 상세 URL을 수집한다.

    Args:
        driver:
            대회 목록 페이지를 제어하는 Selenium WebDriver

    Returns:
        대회 제목과 상세 URL 딕셔너리의 목록
    """

    race_cards = driver.find_elements(By.CSS_SELECTOR, '.race-card')

    race_list = []

    for race in race_cards:
        element = parse_race_element(race)
        race_list.append(element)

    return race_list


def collect_race_detail(url):
    """
    대회 상세 페이지를 요청하고 필요한 일정 및 연락처 정보를 파싱한다.

    Args:
        url:
            수집할 대회 상세 페이지 URL

    Returns:
        대회명, 상태, 지역, 일정, 집결시간, 장소, 종목, 주최,
        접수기간, 공식 URL, 전화번호, 이메일을 담은 딕셔너리

    Raises:
        requests.exceptions.RequestException:
            상세 페이지 HTTP 요청에 실패한 경우
    """

    response = requests.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
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
    """
    runfor.kr에서 전체 마라톤 일정 상세 정보를 수집하여 DataFrame으로 반환한다.

    Selenium으로 동적 대회 목록을 로딩한 뒤 각 상세 URL을 수집하고,
    상세 페이지는 HTTP 요청으로 파싱하여 RAW_COLUMNS 순서의 DataFrame을 만든다.

    Args:
        headless:
            True이면 Selenium Chrome을 headless 모드로 실행

    Returns:
        전체 마라톤 일정 원본 데이터가 저장된 DataFrame

    Raises:
        TimeoutException:
            대회 목록 로딩 또는 더보기 처리에 실패한 경우

        requests.exceptions.RequestException:
            대회 상세 페이지 요청에 실패한 경우
    """

    driver = create_driver(headless=headless)

    try:
        driver.get(TARGET_URL)
        load_count = load_all_marathon(driver)
        races = collect_marathon_url(driver)

    finally:
        driver.quit()

    details = []

    for race in races:
        url = race['detail_url']
        details.append(collect_race_detail(url))

    raw_df = pd.DataFrame(details, columns=RAW_COLUMNS)

    print(f'전체 행 수 : {len(raw_df)}')
    print(f'전체 컬럼 수 : {len(raw_df.columns)}')
    print(f'수집된 대회 수 : {load_count}')

    return raw_df


def build_raw_file_path(directory: Path = RAW_DIR) -> Path:
    """
    현재 시각을 포함한 RAW CSV 파일 경로를 생성한다.

    Args:
        directory:
            RAW CSV를 저장할 기본 폴더

    Returns:
        marathon_schedule_raw_YYMMDD_HHMMSS.csv 형식의 파일 경로
    """

    timestamp = datetime.now(APP_TIMEZONE).strftime('%y%m%d_%H%M%S')
    return directory / f'marathon_schedule_raw_{timestamp}.csv'


def save_raw_csv(
    df: pd.DataFrame,
    directory: Path = RAW_DIR,
) -> Path:
    """
    동적 크롤링 수집 결과를 raw 배치 폴더 안에 CSV 파일로 저장한다.

    임시 파일에 먼저 저장한 뒤 최종 파일명으로 교체하여
    저장 도중 실패한 불완전한 파일이 남는 것을 방지한다.

    Args:
        df:
            저장할 마라톤 일정 원본 DataFrame

        directory:
            RAW CSV를 저장할 폴더

    Returns:
        저장이 완료된 RAW CSV 파일 경로

    Raises:
        OSError:
            폴더 생성 또는 CSV 파일 저장에 실패한 경우
    """

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
    """
    저장한 RAW CSV를 다시 읽고 저장 전후의 행 수와 컬럼 순서를 검증한다.

    Args:
        saved_file:
            저장이 완료된 RAW CSV 파일 경로

        original_df:
            CSV 저장 전 원본 DataFrame

    Raises:
        ValueError:
            저장 전후의 행 수 또는 컬럼 순서가 다른 경우
    """
    
    saved_df = pd.read_csv(saved_file)

    if len(saved_df) != len(original_df):
        raise ValueError('RAW csv 저장 전후의 행 수가 다릅니다.')

    if list(saved_df.columns) != list(original_df.columns):
        raise ValueError('RAW csv 저장 전후의 컬럼 순서가 다릅니다.')


def run_extract(
    headless: bool = True,
    output_dir: Path | None = None,
) -> Path:
    """
    마라톤 일정 수집부터 RAW CSV 저장 및 검증까지 순서대로 실행한다.

    Args:
        headless:
            True이면 Selenium Chrome을 headless 모드로 실행

        output_dir:
            RAW CSV를 저장할 폴더. 지정하지 않으면 기본 data/raw 폴더 사용

    Returns:
        이번 Extract 단계에서 생성된 RAW CSV 파일 경로

    Raises:
        TimeoutException:
            Selenium 대회 목록 로딩에 실패한 경우

        requests.exceptions.RequestException:
            상세 페이지 HTTP 요청에 실패한 경우

        OSError:
            RAW CSV 저장에 실패한 경우

        ValueError:
            저장 후 검증에 실패한 경우
    """

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

if __name__ == '__main__':
    try:
        run_extract()

    except (TimeoutException, OSError, ValueError) as error:
        print('웹페이지 동적 크롤링 작업에 실패했습니다.')
        print(f'오류 내용 : {error}')

        raise SystemExit(1) from error