from unittest.mock import MagicMock, Mock

import pytest

from src.data_collection_pipeline.s3_storage import (
    download_raw_csv,
    upload_processed_file,
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


def test_download_raw_csv(
    tmp_path,
):
    """
    event로 전달받은 RAW Prefix에서
    정확히 하나의 CSV를 다운로드하는지 검증합니다.
    """

    batch_id = '260909_153226'
    raw_prefix = f'raw/{batch_id}/'

    object_key = (
        f'{raw_prefix}'
        f'marathon_schedule_raw_'
        f'{batch_id}.csv'
    )

    mock_s3_client = Mock()

    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [
            {
                'Key': object_key,
            },
        ],
    }

    result = download_raw_csv(
        bucket_name='test-runtrack-bucket',
        batch_id=batch_id,
        raw_prefix=raw_prefix,
        destination_dir=tmp_path,
        s3_client=mock_s3_client,
    )

    expected_file = (
        tmp_path
        / batch_id
        / (
            'marathon_schedule_raw_'
            f'{batch_id}.csv'
        )
    )

    assert result == expected_file

    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket='test-runtrack-bucket',
        Prefix=raw_prefix,
    )

    mock_s3_client.download_file.assert_called_once_with(
        'test-runtrack-bucket',
        object_key,
        str(expected_file),
    )


def test_download_raw_csv_rejects_multiple_csv(
    tmp_path,
):
    """
    하나의 RAW Batch에 CSV가 2개 이상이면
    오류를 발생시키는지 검증합니다.
    """

    mock_s3_client = Mock()

    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [
            {
                'Key': (
                    'raw/260909_153226/'
                    'first.csv'
                ),
            },
            {
                'Key': (
                    'raw/260909_153226/'
                    'second.csv'
                ),
            },
        ],
    }

    with pytest.raises(
        ValueError,
    ):
        download_raw_csv(
            bucket_name='test-runtrack-bucket',
            batch_id='260909_153226',
            raw_prefix='raw/260909_153226/',
            destination_dir=tmp_path,
            s3_client=mock_s3_client,
        )


def test_upload_processed_file(
    tmp_path,
):
    """
    Processed CSV가 processed/ 바로 아래에
    업로드되는지 검증합니다.
    """

    processed_file = (
        tmp_path
        / (
            'marathon_schedule_processed_'
            '260909_153226.csv'
        )
    )

    processed_file.write_text(
        'title,region\n'
        '서울 테스트 마라톤,서울\n',
        encoding='utf-8-sig',
    )

    mock_s3_client = Mock()

    result = upload_processed_file(
        processed_file=processed_file,
        bucket_name='test-runtrack-bucket',
        batch_id='260909_153226',
        s3_client=mock_s3_client,
    )

    expected_key = (
        'processed/260909_153226/'
        'marathon_schedule_processed_'
        '260909_153226.csv'
    )

    assert result == expected_key

    mock_s3_client.upload_file.assert_called_once_with(
        str(processed_file),
        'test-runtrack-bucket',
        expected_key,
    )