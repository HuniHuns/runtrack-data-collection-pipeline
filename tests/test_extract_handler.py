from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from handlers import extract_handler


def test_lambda_handler_runs_extract_and_uploads_to_s3(
    monkeypatch,
    tmp_path,
):
    """
    Extract Lambda Handler가 RAW CSV를 생성하고
    Amazon S3에 업로드하는가
    """

    ## =======================================================
    ## 1. 테스트 RAW CSV
    ## =======================================================

    batch_id = '260909_140000'
    raw_batch_dir = tmp_path / 'raw' / batch_id

    raw_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_csv_file = raw_batch_dir  / (
            'marathon_schedule_raw_'
            f'{batch_id}.csv'
        )

    raw_csv_file.write_text(
        'title,region\n'
        '서울 테스트 마라톤,서울\n',
        encoding='utf-8-sig',
    )

    ## =======================================================
    ## 2. run_extract Mock
    ## =======================================================

    mock_run_extract = Mock(
        return_value=raw_csv_file
    )

    monkeypatch.setattr(
        extract_handler,
        'run_extract',
        mock_run_extract,
    )

    ## =======================================================
    ## 3. S3 Upload Mock
    ## =======================================================

    raw_key = (
        'raw/260909_140000/'
        'marathon_schedule_raw_260909_140000.csv'
    )

    mock_upload = Mock(
        return_value=raw_key
    )

    monkeypatch.setattr(
        extract_handler,
        'upload_raw_csv',
        mock_upload,
    )

    ## =======================================================
    ## 4. S3 Bucket 환경변수
    ## =======================================================

    monkeypatch.setenv(
        'DATA_BUCKET_NAME',
        'runtrack-test-bucket',
    )

    ## =======================================================
    ## 5. Lambda Context
    ## =======================================================

    context = SimpleNamespace(
        aws_request_id='test-request-id'
    )

    ## =======================================================
    ## 6. Handler 실행
    ## =======================================================

    result = (
        extract_handler.lambda_handler(
            event=None,
            context=context,
        )
    )

    ## =======================================================
    ## 7. 기존 Extract 호출 검증
    ## =======================================================

    mock_run_extract.assert_called_once_with(headless=True)

    ## =======================================================
    ## 8. S3 Upload 호출 검증
    ## =======================================================

    mock_upload.assert_called_once_with(
        raw_csv_file=raw_csv_file,
        bucket_name='runtrack-test-bucket',
    )

    ## =======================================================
    ## 9. Handler 응답 검증
    ## =======================================================

    assert result == {
        'stage': 'extract',
        'status': 'SUCCEEDED',
        'batch_id': '260909_140000',
        'bucket': 'runtrack-test-bucket',
        'raw_prefix': 'raw/260909_140000/',
        'raw_key': (
            'raw/260909_140000/'
            'marathon_schedule_raw_260909_140000.csv'
        ),
        'request_id': 'test-request-id',
    }


def test_lambda_handler_raises_runtime_error_without_bucket(
    monkeypatch,
    tmp_path,
):
    """
    DATA_BUCKET_NAME 환경변수가 없으면
    RuntimeError가 발생하는가
    """

    batch_id = '260909_140000'
    raw_batch_dir = tmp_path / 'raw' / batch_id

    raw_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_csv_file = raw_batch_dir / (
            'marathon_schedule_raw_'
            f'{batch_id}.csv'
        )

    raw_csv_file.touch()

    monkeypatch.setattr(
        extract_handler,
        'run_extract',
        Mock(
            return_value=raw_csv_file
        ),
    )

    monkeypatch.delenv(
        'DATA_BUCKET_NAME',
        raising=False,
    )

    with pytest.raises(RuntimeError):
        extract_handler.lambda_handler(
            event=None,
            context=None,
        )