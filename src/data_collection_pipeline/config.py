"""
RUNTRACK 마라톤 일정 데이터 수집 파이프라인의 공통 설정 모듈입니다.

웹 수집 설정과 프로젝트 데이터 저장 경로를 한곳에서 관리합니다.
각 단계 모듈은 필요한 설정값만 import하여 사용합니다.
"""

from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

ENV_FILE = PROJECT_DIR / '.env'

TARGET_URL = 'https://runfor.kr/'

WAIT_TIMEOUT = 10
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30

RACE_LINK_SELECTOR = ".race-cards a[href^='/race/']"
LOAD_MORE_SELECTOR = 'button.race-load-more'

RAW_CSV_PATTERN = 'marathon_schedule_raw_*.csv'
PROCESSED_CSV_PATTERN = 'marathon_schedule_processed_*.csv'

APP_TIMEZONE = ZoneInfo('Asia/Seoul')