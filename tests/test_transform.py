from datetime import datetime

import pandas as pd
import pytest

from src.data_collection_pipeline.config import APP_TIMEZONE
from src.data_collection_pipeline.transform import (
    build_processed_file_path,
    parse_assembly_time,
    parse_date,
    preprocessing_marathon_schedule,
    split_registration_period,
    validate_processed_marathon,
)


def create_raw_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            'title': ['2026 서울 테스트 마라톤'],
            'race_status': ['접수중'],
            'region': ['부산'],
            'location': ['서울광장 (예정)'],
            'course': ['10km / 하프'],
            'race_date': ['2026년 10월 11일'],
            'registration_period': ['2026년 8월 1일 ~ 2026년 9월 30일'],
            'assembly_time': ['오전 8시 30분'],
            'organizer': ['RUNTRACK'],
            'official_url': ['https://example.com'],
            'phone': ['02-1234-5678'],
            'email': ['runtrack@example.com'],
        }
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


def test_preprocessing_marathon_schedule():
    """대회 일정 전처리 전체 결과 테스트"""
    raw_df = create_raw_dataframe()

    result = preprocessing_marathon_schedule(raw_df)

    assert result.loc[0, 'region'] == '경상'
    assert result.loc[0, 'location'] == '서울광장'
    assert result.loc[0, 'course'] == '10km|하프'
    assert result.loc[0, 'race_date'] == pd.Timestamp('2026-10-11')
    assert result.loc[0, 'registration_start_date'] == pd.Timestamp('2026-08-01')
    assert result.loc[0, 'registration_end_date'] == pd.Timestamp('2026-09-30')
    assert result.loc[0, 'assembly_time'] == '08:30'


def test_validate_processed_marathon_returns_summary():
    """전처리 결과 검증 테스트"""
    raw_df = create_raw_dataframe()

    processed_df = preprocessing_marathon_schedule(raw_df)

    result = validate_processed_marathon(processed_df)

    assert result['row_count'] == 1
    assert result['column_count'] == 13
    assert isinstance(
        result['null_count'],
        int,
    )


def test_build_processed_file_path_uses_seoul_time(tmp_path):
    """csv 파일 변환 시 패턴 및 날짜 적용 여부 테스트"""
    before = datetime.now(APP_TIMEZONE).strftime('%y%m%d_%H%M')

    result = build_processed_file_path(tmp_path)

    assert result.parent == tmp_path
    assert result.name.startswith(f'marathon_schedule_processed_{before}')
    assert result.suffix == '.csv'