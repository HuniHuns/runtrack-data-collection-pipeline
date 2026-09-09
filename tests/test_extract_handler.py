from pathlib import Path
from types import SimpleNamespace

from handlers import extract_handler


def test_lambda_handler_runs_extract(
    monkeypatch,
    tmp_path,
):
    """
    Extract Lambda Handler가 run_extract()를 실행하고
    RAW 배치 정보를 정상적으로 반환하는가
    """

    batch_id = '260909_120000'

    raw_batch_dir = tmp_path / 'raw' / batch_id
    raw_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_csv_file = raw_batch_dir / (
            'marathon_schedule_raw_'
            f'{batch_id}.csv'
        )
    raw_csv_file.write_text(
        'title,region\n'
        '서울 테스트 마라톤,서울\n',
        encoding='utf-8-sig',
    )


    def fake_run_extract(headless: bool) -> Path:

        assert headless is True

        return raw_csv_file


    monkeypatch.setattr(
        extract_handler,
        'run_extract',
        fake_run_extract,
    )

    context = SimpleNamespace(
        aws_request_id='test-request-id'
    )

    result = extract_handler.lambda_handler(
            event=None,
            context=context,
        )

    assert result == {
        'stage': 'extract',
        'status': 'SUCCEEDED',
        'batch_id': '260909_120000',
        'temporary_raw_file': str(raw_csv_file),
        'request_id': 'test-request-id',
    }