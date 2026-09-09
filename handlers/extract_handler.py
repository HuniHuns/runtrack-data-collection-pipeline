"""
RUNTRACK 마라톤 일정 수집 작업을 실행하는
AWS Lambda Extract Handler입니다.
"""

from src.data_collection_pipeline.extract import run_extract


def lambda_handler(
    event: dict | None,
    context: object,
) -> dict[str, object]:
    """
    RUNTRACK Extract Lambda의 실행 진입점입니다.
    """

    if event is None:
        event = {}

    raw_csv_file = run_extract(headless=True)
    batch_id = raw_csv_file.parent.name

    request_id = getattr(context, 'aws_request_id', None)

    return {
        'stage': 'extract',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'temporary_raw_file':str(raw_csv_file),
        'request_id': request_id,
    }