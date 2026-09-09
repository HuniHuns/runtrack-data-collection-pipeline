"""
S3 Raw 데이터를 전처리하여
S3 Processed 영역에 저장하는
RUNTRACK AWS Lambda Transform Handler입니다.
"""

from src.data_collection_pipeline.config import (
    PROCESSED_DIR,
    RAW_DIR,
)
from src.data_collection_pipeline.s3_storage import (
    download_raw_csv,
    upload_processed_file,
)
from src.data_collection_pipeline.transform import run_transform


def lambda_handler(
    event: dict,
    context: object,
) -> dict[str, object]:
    """
    RUNTRACK Transform Lambda 실행 진입점입니다.
    """

    ## -------------------------------------------------------
    ## 1. Event 입력값 확인
    ## -------------------------------------------------------

    batch_id = event.get('batch_id')
    bucket_name = event.get('bucket')
    raw_prefix = event.get('raw_prefix')

    if not batch_id:
        raise ValueError('batch_id가 없습니다.')

    if not bucket_name:
        raise ValueError('bucket 정보가 없습니다.')

    if not raw_prefix:
        raise ValueError('raw_prefix 정보가 없습니다.')

    ## -------------------------------------------------------
    ## 2. S3 RAW CSV 다운로드
    ## -------------------------------------------------------

    raw_csv_file = download_raw_csv(
        bucket_name=bucket_name,
        batch_id=batch_id,
        raw_prefix=raw_prefix,
        destination_dir=RAW_DIR,
    )

    ## -------------------------------------------------------
    ## 3. Transform 실행
    ## -------------------------------------------------------

    processed_file = run_transform(
        raw_csv_file=raw_csv_file,
        output_dir=PROCESSED_DIR,
    )

    ## -------------------------------------------------------
    ## 4. Processed CSV S3 업로드
    ## -------------------------------------------------------

    processed_key = upload_processed_file(
        processed_file=processed_file,
        bucket_name=bucket_name,
        batch_id=batch_id
    )

    processed_prefix = f'processed/{batch_id}/'

    ## -------------------------------------------------------
    ## 5. Lambda Request ID
    ## -------------------------------------------------------

    request_id = getattr(context, 'aws_request_id', None)

    ## -------------------------------------------------------
    ## 6. 결과 반환
    ## -------------------------------------------------------

    return {
        'stage': 'transform',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': bucket_name,
        'raw_prefix': raw_prefix,
        'processed_prefix': processed_prefix,
        'processed_key': processed_key,
        'request_id': request_id,
    }