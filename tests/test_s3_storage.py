from unittest.mock import MagicMock

import pytest

from src.data_collection_pipeline.s3_storage import (
    upload_raw_csv,
)


def test_upload_raw_csv(
    tmp_path,
):
    """
    RAW CSV 파일이
    batch_id 기반 S3 Object Key로 업로드되는가
    """

    ## =======================================================
    ## 1. RAW Batch Directory 생성
    ## =======================================================

    batch_id = (
        '260909_140000'
    )

    raw_batch_dir = (
        tmp_path
        / batch_id
    )

    raw_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ## =======================================================
    ## 2. RAW CSV 생성
    ## =======================================================

    raw_csv_file = (
        raw_batch_dir
        / (
            'marathon_schedule_raw_'
            f'{batch_id}.csv'
        )
    )

    raw_csv_file.write_text(
        'title,region\n'
        '서울 테스트 마라톤,서울\n',
        encoding='utf-8-sig',
    )

    ## =======================================================
    ## 3. S3 Client Mock
    ## =======================================================

    s3_client = MagicMock()

    ## =======================================================
    ## 4. RAW CSV 업로드
    ## =======================================================

    result = upload_raw_csv(
        raw_csv_file=raw_csv_file,
        bucket_name='runtrack-test-bucket',
        s3_client=s3_client,
    )

    ## =======================================================
    ## 5. S3 Object Key 검증
    ## =======================================================

    expected_key = (
        'raw/260909_140000/'
        'marathon_schedule_raw_260909_140000.csv'
    )

    assert result == expected_key

    ## =======================================================
    ## 6. S3 upload_file 호출 검증
    ## =======================================================

    s3_client.upload_file.assert_called_once_with(
        str(raw_csv_file),
        'runtrack-test-bucket',
        expected_key,
    )


def test_upload_raw_csv_raises_value_error_without_bucket(
    tmp_path,
):
    """
    S3 Bucket 이름이 없으면
    ValueError가 발생하는가
    """

    raw_csv_file = (
        tmp_path
        / 'marathon_schedule_raw_test.csv'
    )

    raw_csv_file.touch()

    with pytest.raises(
        ValueError
    ):
        upload_raw_csv(
            raw_csv_file=raw_csv_file,
            bucket_name='',
        )


def test_upload_raw_csv_raises_file_not_found(
    tmp_path,
):
    """
    RAW CSV 파일이 존재하지 않으면
    FileNotFoundError가 발생하는가
    """

    raw_csv_file = (
        tmp_path
        / 'not_exists.csv'
    )

    with pytest.raises(
        FileNotFoundError
    ):
        upload_raw_csv(
            raw_csv_file=raw_csv_file,
            bucket_name='runtrack-test-bucket',
        )


def test_upload_raw_csv_raises_value_error_when_not_csv(
    tmp_path,
):
    """
    RAW 데이터 파일이 CSV가 아니면
    ValueError가 발생하는가
    """

    raw_file = (
        tmp_path
        / 'raw_test.txt'
    )

    raw_file.write_text(
        'test',
        encoding='utf-8',
    )

    with pytest.raises(
        ValueError
    ):
        upload_raw_csv(
            raw_csv_file=raw_file,
            bucket_name='runtrack-test-bucket',
        )