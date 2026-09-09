"""
RUNTRACK 마라톤 일정 수집 작업을 실행하는
AWS Lambda Extract Handler입니다.
"""
import os

from src.data_collection_pipeline.extract import run_extract
from src.data_collection_pipeline.s3_storage import upload_raw_csv


def lambda_handler(
    event: dict | None,
    context: object,
) -> dict[str, object]:
    """
    RUNTRACK Extract Lambda의 실행 진입점입니다.
    """

    if event is None:
        event = {}

    bucket_name = os.getenv('DATA_BUCKET_NAME')

    if not bucket_name:
        raise RuntimeError('DATA_BUCKET_NAME 환경변수가 설정되지 않았습니다.')

    raw_csv_file = run_extract(headless=True)
    batch_id = raw_csv_file.parent.name

    raw_key = upload_raw_csv(
        raw_csv_file=raw_csv_file,
        bucket_name=bucket_name,
    )

    raw_prefix = f'raw/{batch_id}/'

    request_id = getattr(context, 'aws_request_id', None)

    return {
        'stage': 'extract',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': bucket_name,
        'raw_prefix': raw_prefix,
        'raw_key': raw_key,
        'request_id': request_id,
    }