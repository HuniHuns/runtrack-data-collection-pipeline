"""
Load Lambda Handler의 입력 검증과
S3 Processed CSV 다운로드 및 Load 실행을 검증합니다.
"""

## Mock 객체 생성을 위한 표준 테스트 도구
from unittest.mock import Mock

## 예외 발생 검증
import pytest

## 테스트 대상 Lambda Handler
from handlers.load_handler import lambda_handler

## ===========================================================
## 1. 정상 실행 테스트
## ===========================================================

def test_load_handler(monkeypatch, tmp_path):
    """
    정상 Event 입력 시 S3 Processed CSV를 다운로드하고
    run_load()가 호출되는지 확인합니다.
    """

    ## 테스트용 Lambda Event
    event = {
        'batch_id': '20260901_035140',
        'bucket': 'test-runtrack-bucket',
        'processed_key': (
            'processed/20260901_035140/'
            'marathon_schedule_processed_20260901_035140.csv'
        ),
    }

    ## Lambda Context Mock 생성
    context = Mock()
    context.aws_request_id = 'test-request-id'

    ## 테스트용 Processed CSV 경로
    processed_file = tmp_path / 'marathon_schedule_processed_20260901_035140.csv'

    ## S3 다운로드 Mock
    mock_download = Mock(return_value=processed_file)

    ## DB 적재 결과 Mock
    mock_run_load = Mock(
        return_value={
            'input_file': processed_file.name,
            'batch_at': '2026-09-01 03:51:40',
            'database_name': 'runtrack',
            'input_count': 60,
            'affected_row_count': 60,
        }
    )

    ## Handler 내부 S3 다운로드 함수 Mock 처리
    monkeypatch.setattr(
        'handlers.load_handler.download_processed_file',
        mock_download,
    )

    ## Handler 내부 run_load() 함수 Mock 처리
    monkeypatch.setattr(
        'handlers.load_handler.run_load',
        mock_run_load,
    )

    ## Lambda Handler 실행
    result = lambda_handler(event, context)

    ## Lambda 반환값 검증
    assert result['stage'] == 'load'
    assert result['status'] == 'SUCCEEDED'
    assert result['batch_id'] == '20260901_035140'
    assert result['bucket'] == 'test-runtrack-bucket'
    assert result['processed_key'] == event['processed_key']
    assert result['request_id'] == 'test-request-id'

    ## Load 결과 검증
    assert result['load_summary']['database_name'] == 'runtrack'
    assert result['load_summary']['input_count'] == 60
    assert result['load_summary']['affected_row_count'] == 60

    ## S3 Processed CSV 다운로드 호출 검증
    mock_download.assert_called_once()

    ## run_load() 호출 검증
    mock_run_load.assert_called_once_with(
        processed_csv_file=processed_file,
    )


## ===========================================================
## 2. Event 입력값 검증 테스트
## ===========================================================

def test_load_handler_requires_batch_id():
    """
    batch_id가 없으면 ValueError가 발생하는지 확인합니다.
    """

    ## batch_id가 누락된 Event
    event = {
        'bucket': 'test-runtrack-bucket',
        'processed_key': 'processed/test.csv',
    }

    ## batch_id 필수값 검증
    with pytest.raises(ValueError, match=r'batch_id가 없습니다\.'):
        lambda_handler(event, Mock())


def test_load_handler_requires_bucket():
    """
    bucket이 없으면 ValueError가 발생하는지 확인합니다.
    """

    ## bucket이 누락된 Event
    event = {
        'batch_id': '20260901_035140',
        'processed_key': 'processed/test.csv',
    }

    ## bucket 필수값 검증
    with pytest.raises(ValueError, match=r'bucket 정보가 없습니다\.'):
        lambda_handler(event, Mock())


def test_load_handler_requires_processed_key():
    """
    processed_key가 없으면 ValueError가 발생하는지 확인합니다.
    """

    ## processed_key가 누락된 Event
    event = {
        'batch_id': '20260901_035140',
        'bucket': 'test-runtrack-bucket',
    }

    ## processed_key 필수값 검증
    with pytest.raises(ValueError, match=r'processed_key 정보가 없습니다\.'):
        lambda_handler(event, Mock())