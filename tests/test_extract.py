from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data_collection_pipeline import extract
from src.data_collection_pipeline.config import APP_TIMEZONE
from src.data_collection_pipeline.extract import (
    build_raw_batch_dir,
    build_raw_file_path,
    create_driver,
    save_raw_csv,
    verify_saved_raw_csv,
)


def test_create_driver_uses_lambda_chromium(monkeypatch):
    """
    Chromium과 ChromeDriver 경로가 설정된 경우
    Lambda Container용 WebDriver 설정을 사용하는가
    """

    ## 1. Lambda 환경의 Chromium 경로 Mock
    monkeypatch.setattr(
        extract,
        'CHROMIUM_BINARY',
        '/usr/local/bin/chromium',
    )

    monkeypatch.setattr(
        extract,
        'CHROMEDRIVER_PATH',
        '/usr/local/bin/chromedriver',
    )

    ## 2. 실제 Chrome 실행 방지를 위한 Mock
    fake_driver = MagicMock()
    fake_service = MagicMock()

    chrome_mock = MagicMock(return_value=fake_driver)
    service_mock = MagicMock(return_value=fake_service)

    monkeypatch.setattr(
        extract.webdriver,
        'Chrome',
        chrome_mock,
    )

    monkeypatch.setattr(
        extract,
        'Service',
        service_mock,
    )

    ## 3. Driver 생성
    result = create_driver()

    ## 4. 결과 검증
    assert result is fake_driver

    service_mock.assert_called_once_with(
        executable_path=(
            '/usr/local/bin/chromedriver'
        )
    )

    call_kwargs = chrome_mock.call_args.kwargs
    options = call_kwargs['options']

    assert options.binary_location == '/usr/local/bin/chromium'

    assert '--headless=new' in options.arguments
    assert '--no-sandbox' in options.arguments
    assert '--disable-dev-shm-usage' in options.arguments

    assert call_kwargs['service'] is fake_service


def test_build_raw_batch_dir(tmp_path):
    """수집 시각을 기준으로 RAW 배치 폴더가 생성되는가"""

    collected_at = datetime(2026, 9, 9, 10, 30, 15, tzinfo=APP_TIMEZONE)

    result = build_raw_batch_dir(
        directory=tmp_path,
        collected_at=collected_at,
    )

    expected_dir = tmp_path / '260909_103015'

    assert result == expected_dir
    assert result.exists()
    assert result.is_dir()


def test_build_raw_file_path(tmp_path):
    """raw csv파일명이 패턴에 맞게 작성되었는가"""

    collected_at = datetime(2026, 9, 9, 10, 30, 15, tzinfo=APP_TIMEZONE)
    result = build_raw_file_path(tmp_path, collected_at)

    assert result.parent == tmp_path
    assert result.name == ('marathon_schedule_raw_260909_103015.csv')
    assert result.suffix == '.csv'


def test_save_raw_csv_creates_file(tmp_path):
    """save_raw_csv 함수 실행 시 csv 파일이 생성되는가"""
    source_df = pd.DataFrame(
        {
            'title': [
                '서울 테스트 마라톤',
                '부산 테스트 마라톤',
            ],
            'region': [
                '서울',
                '경상',
            ],
        }
    )

    saved_file = save_raw_csv(source_df, tmp_path)

    assert saved_file.exists()
    assert saved_file.is_file()


def test_save_raw_csv_preserves_data(tmp_path):
    """csv 파일 저장 시 DataFrame 정보가 그대로 저장되는가"""
    source_df = pd.DataFrame(
        {
            'title': [
                '서울 테스트 마라톤',
            ],
            'region': [
                '서울',
            ],
        }
    )

    saved_file = save_raw_csv(source_df, tmp_path)

    saved_df = pd.read_csv(saved_file, dtype='string')

    assert len(saved_df) == 1
    assert saved_df.loc[0, 'title'] == '서울 테스트 마라톤'
    assert saved_df.loc[0, 'region'] == '서울'


def test_verify_saved_raw_csv_success(tmp_path):
    """검증 함수가 제대로 작동하는가"""
    source_df = pd.DataFrame(
        {
            'title': [
                '서울 테스트 마라톤',
            ],
            'region': [
                '서울',
            ],
        }
    )

    file_path = tmp_path / 'marathon_schedule_raw_test.csv'

    source_df.to_csv(
        file_path,
        index=False,
        encoding='utf-8-sig',
    )

    verify_saved_raw_csv(file_path, source_df)


def test_verify_saved_raw_csv_raises_value_error(tmp_path):
    """검증 함수가 에러를 제대로 반환하는가 (예외 처리 확인)"""
    source_df = pd.DataFrame(
        {
            'title': [
                '서울 마라톤',
                '부산 마라톤',
            ],
        }
    )

    saved_df = pd.DataFrame(
        {
            'title': [
                '서울 마라톤',
            ],
        }
    )

    file_path = tmp_path / 'marathon_schedule_raw_test.csv'

    saved_df.to_csv(
        file_path,
        index=False,
        encoding='utf-8-sig',
    )

    with pytest.raises(ValueError):
        verify_saved_raw_csv(file_path, source_df)