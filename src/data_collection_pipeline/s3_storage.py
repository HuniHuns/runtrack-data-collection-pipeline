"""
RUNTRACK 데이터 수집 파이프라인에서 사용하는
Amazon S3 저장 기능을 제공하는 모듈입니다.
"""

from pathlib import Path
from typing import Any


def upload_raw_csv(
    raw_csv_file: Path,
    bucket_name: str,
    s3_client: Any | None = None,
) -> str:
    """
    Extract 단계에서 생성한 RAW CSV 파일을
    Amazon S3 Raw 영역에 업로드합니다.

    Args:
        raw_csv_file:
            Extract 단계에서 생성된 로컬 RAW CSV 파일

        bucket_name:
            RAW CSV 파일을 저장할 S3 Bucket 이름

        s3_client:
            테스트 등을 위해 외부에서 전달할 수 있는
            Amazon S3 Client

    Returns:
        S3에 업로드된 Object Key
    """

    ## =======================================================
    ## 1. S3 Bucket 이름 검증
    ## =======================================================

    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    ## =======================================================
    ## 2. RAW CSV 파일 존재 여부 검증
    ## =======================================================

    if not raw_csv_file.is_file():
        raise FileNotFoundError(f'업로드할 RAW CSV 파일이 존재하지 않습니다. {raw_csv_file}')

    ## =======================================================
    ## 3. CSV 파일 형식 검증
    ## =======================================================

    if raw_csv_file.suffix.lower() != '.csv':
        raise ValueError(f'RAW 데이터 파일이 CSV 형식이 아닙니다. {raw_csv_file}')

    ## =======================================================
    ## 4. S3 Client 생성
    ## =======================================================

    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## =======================================================
    ## 5. RAW 배치 폴더에서 batch_id 추출
    ## =======================================================

    batch_id = raw_csv_file.parent.name

    ## =======================================================
    ## 6. S3 Raw Prefix 생성
    ## =======================================================

    raw_prefix = f'raw/{batch_id}'

    ## =======================================================
    ## 7. S3 Object Key 생성
    ## =======================================================

    object_key = f'{raw_prefix}/{raw_csv_file.name}'

    ## =======================================================
    ## 8. RAW CSV S3 업로드
    ## =======================================================

    s3_client.upload_file(
        str(raw_csv_file),
        bucket_name,
        object_key,
    )

    ## =======================================================
    ## 9. 업로드 완료 로그
    ## =======================================================

    print(
        f'S3 업로드 완료 : '
        f's3://{bucket_name}/{object_key}'
    )

    ## =======================================================
    ## 10. 업로드된 S3 Object Key 반환
    ## =======================================================

    return object_key