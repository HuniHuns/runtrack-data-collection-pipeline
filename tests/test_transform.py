from datetime import datetime

import pandas as pd
import pytest

from src.data_collection_pipeline.config import APP_TIMEZONE
from src.data_collection_pipeline.transform import (
    build_processed_file_path,
    parse_assembly_time,
    parse_date,
    split_registration_period,
)


def test_parse_date_converts_korean_date_to_timestamp():
    """개최일 날짜형 타입 변환 여부 테스트"""
    result = parse_date('2026년 10월 11일')

    assert result == pd.Timestamp('2026-10-11')


def test_split_registration_period_returns_start_and_end_date():
    """접수 기간 분리 및 타입 변환 여부 테스트"""
    result = split_registration_period('2026년 8월 1일 ~ 2026년 9월 30일')

    assert result == (
        pd.Timestamp('2026-08-01'),
        pd.Timestamp('2026-09-30'),
    )


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('오전 8시 30분', '08:30'),
        ('오후 2시 30분', '14:30'),
        ('오전 12시', '00:00'),
        ('오후 12시', '12:00'),
        ('시간 미정', None),
    ],
)
def test_parse_assembly_time(value, expected):
    """집합 시간 파싱 여부 테스트"""
    result = parse_assembly_time(value)

    if expected is None:
        assert pd.isna(result)

    else:
        assert result == expected


def test_build_processed_file_path_uses_seoul_time(tmp_path):
    """csv 파일 변환 시 패턴 및 날짜 적용 여부 테스트"""
    batch_at = datetime(2026, 9, 9, 10, 30, 45, tzinfo=APP_TIMEZONE)

    result = build_processed_file_path(batch_at, tmp_path)

    assert result == (
        tmp_path
        / 'marathon_schedule_processed_260909_103045.csv'
    )