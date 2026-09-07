"""
RUNTRACK 마라톤 일정 ETL 파이프라인 실행 파일

실행 흐름
1. Extract
   run_extract()
   -> runfor.kr에서 마라톤 일정을 수집하고 RAW CSV 경로 반환

2. Transform
   run_transform(raw_csv_file)
   -> RAW CSV를 정제/표준화하고 processed CSV 경로 반환

3. Load
   run_load(processed_csv_file)
   -> processed CSV를 MySQL에 적재하고 결과 요약 반환

프로젝트 루트에서 다음과 같이 실행한다.
    python main.py
"""

from pathlib import Path

import requests
from selenium.common.exceptions import WebDriverException
from sqlalchemy.exc import SQLAlchemyError

from src.data_collection_pipeline import (
    run_extract,
    run_transform,
    run_load,
)


PROJECT_DIR = Path(__file__).resolve().parent


def main() -> tuple[Path, Path, dict[str, object]]:
    """마라톤 일정 Extract -> Transform -> Load 전체 파이프라인을 실행한다."""

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
