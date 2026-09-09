"""
RUNTRACK 마라톤 일정 데이터 수집 파이프라인의 공통 설정 모듈입니다.

웹 수집 설정과 프로젝트 데이터 저장 경로를 한곳에서 관리합니다.
각 단계 모듈은 필요한 설정값만 import하여 사용합니다.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

## ===========================================================
## 1. 프로젝트 경로
## ===========================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = PROJECT_DIR / 'data'
DATA_DIR = Path(os.getenv('DATA_DIR', str(DEFAULT_DATA_DIR)))
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

ENV_FILE = PROJECT_DIR / '.env'

## ===========================================================
## 2. 웹 수집 설정
## ===========================================================

TARGET_URL = 'https://runfor.kr/'
SOURCE_SITE = 'RUNFOR - RUNNING INFORMATION'

WAIT_TIMEOUT = 10
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30

RACE_LINK_SELECTOR = ".race-cards a[href^='/race/']"
LOAD_MORE_SELECTOR = 'button.race-load-more'

RAW_CSV_PATTERN = 'marathon_schedule_raw_*.csv'
PROCESSED_CSV_PATTERN = 'marathon_schedule_processed_*.csv'

## ===========================================================
## 3. Selenium 실행 환경
## ===========================================================

# 로컬에서는 설정하지 않아도 기존 Chrome/Selenium Manager 사용 가능
# Lambda에서는 Chromium Layer의 경로를 환경변수로 전달

CHROMIUM_BINARY = os.getenv('CHROMIUM_BINARY')
CHROMEDRIVER_PATH = os.getenv('CHROMEDRIVER_PATH')


## ===========================================================
## 4. 시간대 설정
## ===========================================================

APP_TIMEZONE = ZoneInfo('Asia/Seoul')