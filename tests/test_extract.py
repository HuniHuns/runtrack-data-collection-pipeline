from datetime import datetime

import pandas as pd
import pytest

from src.data_collection_pipeline.config import APP_TIMEZONE
from src.data_collection_pipeline.extract import (
    build_raw_file_path,
    save_raw_csv,
    verify_saved_raw_csv,
)


def test_build_raw_file_path(tmp_path):
    """raw csv파일명이 패턴에 맞게 작성되었는가"""

    result = build_raw_file_path(tmp_path)

    assert result.parent == tmp_path
    assert result.name.startswith('marathon_schedule_raw_')
    assert result.suffix == '.csv'

def test_build_raw_file_path_uses_app_timezone(tmp_path):
    """raw csv 파일명에 APP_TIMEZONE 시간이 형식에 맞게 작성되었는가"""

    before = datetime.now(APP_TIMEZONE).replace(microsecond=0)

    result = build_raw_file_path(tmp_path)

    after = datetime.now(APP_TIMEZONE).replace(microsecond=0)

    timestamp_text = result.stem.replace('marathon_schedule_raw_', '')

    result_datetime = datetime.strptime(
        timestamp_text,
        '%y%m%d_%H%M%S',
    ).replace(tzinfo=APP_TIMEZONE)

    assert (
        before
        <= result_datetime
        <= after
    )


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