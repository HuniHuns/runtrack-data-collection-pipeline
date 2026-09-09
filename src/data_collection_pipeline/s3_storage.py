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


def download_raw_csv(
    bucket_name: str,
    batch_id: str,
    raw_prefix: str,
    destination_dir: Path,
    s3_client: Any | None = None,
) -> Path:
    """
    Transform 단계에서 처리할 RAW CSV를
    S3 Raw 영역에서 Lambda 임시 디렉터리로 다운로드합니다.
    """

    ## -------------------------------------------------------
    ## 1. 필수 입력값 검증
    ## -------------------------------------------------------

    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    if not batch_id:
        raise ValueError('batch_id가 지정되지 않았습니다.')

    if not raw_prefix:
        raise ValueError('raw_prefix가 지정되지 않았습니다.')

    ## -------------------------------------------------------
    ## 2. S3 Client
    ## -------------------------------------------------------

    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## -------------------------------------------------------
    ## 3. Lambda RAW Batch Directory 생성
    ## -------------------------------------------------------

    raw_batch_dir = destination_dir / batch_id
    raw_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ## -------------------------------------------------------
    ## 4. event로 전달받은 Prefix 아래 Object 조회
    ## -------------------------------------------------------

    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=raw_prefix,
    )

    objects = response.get('Contents', [])

    ## -------------------------------------------------------
    ## 5. CSV만 필터링
    ## -------------------------------------------------------

    csv_objects = [
        obj
        for obj in objects
        if obj['Key'].endswith('.csv')
    ]

    if not csv_objects:
        raise FileNotFoundError(
            'S3 Raw 영역에 CSV 파일이 없습니다. '
            f's3://{bucket_name}/{raw_prefix}'
        )

    ## -------------------------------------------------------
    ## 6. RUNTRACK은 Batch당 RAW CSV 1개만 허용
    ## -------------------------------------------------------

    if len(csv_objects) > 1:
        raise ValueError(
            '하나의 RAW 배치에 CSV 파일이 '
            '2개 이상 존재합니다. '
            f's3://{bucket_name}/{raw_prefix}'
        )

    ## -------------------------------------------------------
    ## 7. RAW CSV 다운로드
    ## -------------------------------------------------------

    object_key = csv_objects[0]['Key']

    file_name = Path(object_key).name

    local_file = raw_batch_dir / file_name

    s3_client.download_file(
        bucket_name,
        object_key,
        str(local_file),
    )

    print(
        f'S3 다운로드 완료 : '
        f's3://{bucket_name}/{object_key}'
    )

    return local_file


def upload_processed_file(
    processed_file: Path,
    bucket_name: str,
    batch_id: str,
    s3_client: Any | None = None,
) -> str:
    """
    Transform 결과 Processed CSV를
    S3 Processed 영역에 업로드합니다.
    """

    ## -------------------------------------------------------
    ## 1. 입력값 검증
    ## -------------------------------------------------------

    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    if not processed_file.is_file():
        raise FileNotFoundError(f'Processed CSV 파일이 존재하지 않습니다. {processed_file}')

    ## -------------------------------------------------------
    ## 2. S3 Client
    ## -------------------------------------------------------

    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## -------------------------------------------------------
    ## 3. S3 Object Key
    ## -------------------------------------------------------

    object_key = f'processed/{batch_id}/{processed_file.name}'

    ## -------------------------------------------------------
    ## 4. S3 업로드
    ## -------------------------------------------------------

    s3_client.upload_file(
        str(processed_file),
        bucket_name,
        object_key,
    )

    print(
        f'S3 업로드 완료 : '
        f's3://{bucket_name}/{object_key}'
    )

    return object_key