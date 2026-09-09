from pathlib import Path
from unittest.mock import Mock

import pytest

from handlers import transform_handler


def test_transform_lambda_handler(
    monkeypatch,
):
    """
    Transform Lambda의
    S3 RAW 다운로드 → Transform → S3 업로드
    흐름을 검증합니다.
    """

    batch_id = '260909_153226'
    bucket_name = 'test-runtrack-bucket'
    raw_prefix = f'raw/{batch_id}/'

    raw_csv_file = Path(
        '/tmp/data/raw/'
        f'{batch_id}/'
        f'marathon_schedule_raw_'
        f'{batch_id}.csv'
    )

    processed_file = Path(
        '/tmp/data/processed/'
        f'marathon_schedule_processed_'
        f'{batch_id}.csv'
    )

    processed_key = (
        'processed/'
        f'marathon_schedule_processed_'
        f'{batch_id}.csv'
    )

    processed_prefix = f'processed/{batch_id}/'

    ## -------------------------------------------------------
    ## S3 Download Mock
    ## -------------------------------------------------------

    mock_download = Mock(return_value=raw_csv_file)

    monkeypatch.setattr(
        transform_handler,
        'download_raw_csv',
        mock_download,
    )

    ## -------------------------------------------------------
    ## Transform Mock
    ## -------------------------------------------------------

    mock_transform = Mock(return_value=processed_file)

    monkeypatch.setattr(
        transform_handler,
        'run_transform',
        mock_transform,
    )

    ## -------------------------------------------------------
    ## S3 Upload Mock
    ## -------------------------------------------------------

    mock_upload = Mock(return_value=processed_key)

    monkeypatch.setattr(
        transform_handler,
        'upload_processed_file',
        mock_upload,
    )

    ## -------------------------------------------------------
    ## Lambda Event
    ## -------------------------------------------------------

    event = {
        'batch_id': batch_id,
        'bucket': bucket_name,
        'raw_prefix': raw_prefix,
    }

    context = Mock()

    context.aws_request_id = 'test-request-id'

    ## -------------------------------------------------------
    ## Handler 실행
    ## -------------------------------------------------------

    result = transform_handler.lambda_handler(event, context)

    ## -------------------------------------------------------
    ## 호출 검증
    ## -------------------------------------------------------

    mock_download.assert_called_once_with(
        bucket_name=bucket_name,
        batch_id=batch_id,
        raw_prefix=raw_prefix,
        destination_dir=(
            transform_handler.RAW_DIR
        ),
    )

    mock_transform.assert_called_once_with(
        raw_csv_file=raw_csv_file,
        output_dir=(
            transform_handler.PROCESSED_DIR
        ),
    )

    mock_upload.assert_called_once_with(
        processed_file=processed_file,
        bucket_name=bucket_name,
        batch_id=batch_id,
    )

    ## -------------------------------------------------------
    ## 결과 검증
    ## -------------------------------------------------------

    assert result == {
        'stage': 'transform',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': bucket_name,
        'raw_prefix': raw_prefix,
        'processed_prefix': processed_prefix,
        'processed_key': processed_key,
        'request_id': 'test-request-id',
    }


@pytest.mark.parametrize(
    (
        'event',
        'message',
    ),
    [
        (
            {
                'bucket': 'test-bucket',
                'raw_prefix': 'raw/test/',
            },
            'batch_id가 없습니다.',
        ),
        (
            {
                'batch_id': '260909_153226',
                'raw_prefix': (
                    'raw/260909_153226/'
                ),
            },
            'bucket 정보가 없습니다.',
        ),
        (
            {
                'batch_id': '260909_153226',
                'bucket': 'test-bucket',
            },
            'raw_prefix 정보가 없습니다.',
        ),
    ],
)
def test_transform_lambda_handler_validates_event(
    event,
    message,
):
    """
    Transform Lambda 필수 Event 값 누락을 검증합니다.
    """

    with pytest.raises(
        ValueError,
        match=message,
    ):
        transform_handler.lambda_handler(
            event,
            None,
        )