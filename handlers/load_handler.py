"""
S3 Processed CSV를 다운로드하고
Amazon RDS MySQL에 적재하는
RUNTRACK AWS Lambda Load Handler입니다.
"""

from src.data_collection_pipeline.config import PROCESSED_DIR
from src.data_collection_pipeline.load import run_load
from src.data_collection_pipeline.s3_storage import download_processed_file


def lambda_handler(
    event: dict,
    context: object,
) -> dict[str, object]:
    """
    RUNTRACK Load Lambda 실행 진입점입니다.

    Args:
        event:
            Transform Lambda 또는 Step Functions에서
            전달되는 배치 메타데이터

        context:
            AWS Lambda 실행 Context

    Returns:
        Load 실행 결과
    """

    ## =======================================================
    ## 1. Event 입력값 확인
    ## =======================================================

    batch_id = event.get('batch_id')
    bucket_name = event.get('bucket')
    processed_key = event.get('processed_key')

    if not batch_id:
        raise ValueError('batch_id가 없습니다.')

    if not bucket_name:
        raise ValueError('bucket 정보가 없습니다.')

    if not processed_key:
        raise ValueError('processed_key 정보가 없습니다.')

    ## =======================================================
    ## 2. S3 Processed CSV 다운로드
    ## =======================================================

    processed_file = download_processed_file(
        bucket_name=bucket_name,
        processed_key=processed_key,
        destination_dir=PROCESSED_DIR,
    )

    ## =======================================================
    ## 3. Processed CSV → RDS MySQL 적재
    ## =======================================================

    load_summary = run_load(
        processed_csv_file=processed_file,
    )

    # ========================================================
    # 4. Lambda Request ID
    # ========================================================

    request_id = getattr(context, 'aws_request_id', None)

    # ========================================================
    # 5. 결과
    # ========================================================

    return {
        'stage': 'load',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': bucket_name,
        'processed_key': processed_key,
        'load_summary': load_summary,
        'request_id': request_id,
    }