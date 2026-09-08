"""
RUNTRACK 마라톤 일정 데이터 수집 ETL 파이프라인 실행 파일입니다.

이 파일은 프로젝트의 실행 진입점(entry point)으로,
마라톤 일정 수집, 데이터 전처리, MySQL 저장 작업을 순서대로 실행합니다.

[사용 모듈]
1. extract.py
    - runfor.kr의 동적 대회 목록을 Selenium으로 로딩합니다.
    - 각 대회 상세 페이지에서 일정 정보를 수집합니다.
    - 수집 결과를 원본 RAW CSV 파일로 저장합니다.

2. transform.py
    - RAW CSV 파일을 읽습니다.
    - 지역, 장소, 종목, 날짜, 접수기간, 집결시간 등을 표준화합니다.
    - 전화번호와 이메일 형식을 검증합니다.
    - 전처리 결과를 processed CSV 파일로 저장합니다.

3. load.py
    - processed CSV 파일을 읽고 MySQL 저장 전 데이터를 검증합니다.
    - marathon_schedule, course, schedule_course 테이블을 생성합니다.
    - 마라톤 일정과 코스 관계를 INSERT 또는 UPDATE 방식으로 저장합니다.

[실행 흐름]
run_extract()
-> RAW CSV 파일 경로 반환

run_transform(raw_csv_file)
-> processed CSV 파일 경로 반환

run_load(processed_csv_file)
-> MySQL 저장 결과 요약 반환

[실행 결과]
각 단계에서 생성한 파일 경로와 MySQL 저장 결과를 출력하고,
RAW CSV 경로, processed CSV 경로, MySQL 저장 결과를 튜플로 반환합니다.
"""

from pathlib import Path

import requests
from selenium.common.exceptions import WebDriverException
from sqlalchemy.exc import SQLAlchemyError

from src.data_collection_pipeline import (
    run_extract,
    run_load,
    run_transform,
)

## --------------------------------------
## 프로젝트 경로 설정
## --------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent


def main() -> tuple[Path, Path, dict[str, object]]:
    """
    RUNTRACK 마라톤 일정 Extract, Transform, Load 작업을 순서대로 실행한다.

    Returns:
        다음 실행 결과를 저장한 튜플

        1. Extract 단계에서 생성한 RAW CSV 파일 경로
        2. Transform 단계에서 생성한 processed CSV 파일 경로
        3. Load 단계의 MySQL 저장 결과 요약
    """

    print('=' * 70)
    print('RUNTRACK 마라톤 일정 ETL 파이프라인 시작')
    print('=' * 70)

    # 1. Extract
    raw_csv_file = run_extract()

    # 2. Transform
    processed_csv_file = run_transform(raw_csv_file=raw_csv_file)

    # 3. Load
    load_summary = run_load(processed_csv_file=processed_csv_file)

    print()
    print('>' * 70)
    print('RUNTRACK 마라톤 일정 ETL 파이프라인 완료')
    print('>' * 70)
    print(f'✔ RAW CSV       : {raw_csv_file}')
    print(f'✔ Processed CSV : {processed_csv_file}')
    print(f'✔ MySQL 적재    : {load_summary}')

    return raw_csv_file, processed_csv_file, load_summary


if __name__ == '__main__':
    try:
        main()

    except requests.exceptions.RequestException as error:
        print()
        print('마라톤 일정 HTTP 요청 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

    except WebDriverException as error:
        print()
        print('Selenium 브라우저 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

    except SQLAlchemyError as error:
        print()
        print('MySQL 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

    except (FileNotFoundError, OSError, ValueError) as error:
        print()
        print('파일 처리 또는 데이터 검증 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')
