"""
RUNTRACK database.py의
로컬 .env 및 AWS Secrets Manager 기반
MySQL 설정 로직을 검증합니다.
"""

import json
from unittest.mock import Mock

import pytest

from src.data_collection_pipeline.database import (
    load_database_config,
    load_database_config_from_secret,
)


def _clear_database_env(
    monkeypatch,
) -> None:
    """
    DB 환경변수가 테스트끼리 영향을 주지 않도록 제거합니다.
    """

    env_names = [
        'DB_SECRET_ARN',
        'DB_HOST',
        'DB_PORT',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD',
    ]

    for name in env_names:
        monkeypatch.delenv(
            name,
            raising=False,
        )


def test_load_database_config_from_secret(
    monkeypatch,
):
    """
    Lambda에서는 Secret의 username/password와
    환경변수의 RDS 정보를 결합하는지 검증합니다.
    """

    _clear_database_env(
        monkeypatch
    )

    monkeypatch.setenv(
        'DB_SECRET_ARN',
        'arn:aws:secretsmanager:test',
    )

    monkeypatch.setenv(
        'DB_HOST',
        'runtrack-db.example.amazonaws.com',
    )

    monkeypatch.setenv(
        'DB_PORT',
        '3306',
    )

    monkeypatch.setenv(
        'DB_NAME',
        'runtrackdb',
    )

    mock_secrets_client = Mock()

    mock_secrets_client.get_secret_value.return_value = {
        'SecretString':
            json.dumps(
                {
                    'username':
                        'runtrack_admin',

                    'password':
                        'test-password',
                }
            )
    }

    result = load_database_config(
        secrets_client=(
            mock_secrets_client
        )
    )

    assert result == {
        'host':
            'runtrack-db.example.amazonaws.com',

        'port':
            3306,

        'database':
            'runtrackdb',

        'username':
            'runtrack_admin',

        'password':
            'test-password',
    }

    (
        mock_secrets_client
        .get_secret_value
        .assert_called_once_with(
            SecretId=(
                'arn:aws:secretsmanager:test'
            )
        )
    )


def test_secret_values_have_priority(
    monkeypatch,
):
    """
    Secret에 host/port/dbname까지 존재하면
    환경변수보다 Secret 값을 우선 사용하는지 검증합니다.
    """

    _clear_database_env(
        monkeypatch
    )

    monkeypatch.setenv(
        'DB_HOST',
        'environment-host',
    )

    monkeypatch.setenv(
        'DB_PORT',
        '3307',
    )

    monkeypatch.setenv(
        'DB_NAME',
        'environment-db',
    )

    mock_secrets_client = Mock()

    (
        mock_secrets_client
        .get_secret_value
        .return_value
    ) = {
        'SecretString':
            json.dumps(
                {
                    'host':
                        'secret-host',

                    'port':
                        3306,

                    'dbname':
                        'runtrackdb',

                    'username':
                        'runtrack_admin',

                    'password':
                        'secret-password',
                }
            )
    }

    result = (
        load_database_config_from_secret(
            secret_arn='test-secret',
            secrets_client=(
                mock_secrets_client
            ),
        )
    )

    assert result == {
        'host': 'secret-host',
        'port': 3306,
        'database': 'runtrackdb',
        'username': 'runtrack_admin',
        'password': 'secret-password',
    }


def test_secret_requires_username(
    monkeypatch,
):
    """
    Secret에 username이 없으면 실패해야 합니다.
    """

    _clear_database_env(
        monkeypatch
    )

    monkeypatch.setenv(
        'DB_HOST',
        'test-host',
    )

    monkeypatch.setenv(
        'DB_NAME',
        'runtrackdb',
    )

    client = Mock()

    client.get_secret_value.return_value = {
        'SecretString':
            json.dumps(
                {
                    'password':
                        'password',
                }
            )
    }

    with pytest.raises(
        ValueError,
        match=r'username이 없습니다\.',
    ):
        load_database_config_from_secret(
            secret_arn='test-secret',
            secrets_client=client,
        )


def test_secret_requires_password(
    monkeypatch,
):
    """
    Secret에 password가 없으면 실패해야 합니다.
    """

    _clear_database_env(
        monkeypatch
    )

    monkeypatch.setenv(
        'DB_HOST',
        'test-host',
    )

    monkeypatch.setenv(
        'DB_NAME',
        'runtrackdb',
    )

    client = Mock()

    client.get_secret_value.return_value = {
        'SecretString':
            json.dumps(
                {
                    'username':
                        'runtrack_admin',
                }
            )
    }

    with pytest.raises(
        ValueError,
        match=r'password가 없습니다\.',
    ):
        load_database_config_from_secret(
            secret_arn='test-secret',
            secrets_client=client,
        )


def test_secret_rejects_invalid_json():
    """
    SecretString이 JSON이 아니면 실패해야 합니다.
    """

    client = Mock()

    client.get_secret_value.return_value = {
        'SecretString':
            'invalid-json'
    }

    with pytest.raises(
        ValueError,
        match=r'올바른 JSON 형식이 아닙니다\.',
    ):
        load_database_config_from_secret(
            secret_arn='test-secret',
            secrets_client=client,
        )


def test_load_database_config_from_env(
    monkeypatch,
    tmp_path,
):
    """
    DB_SECRET_ARN이 없는 경우
    기존 로컬 .env 동작을 유지하는지 검증합니다.
    """

    _clear_database_env(
        monkeypatch
    )

    env_file = (
        tmp_path
        / '.env'
    )

    env_file.write_text(
        '\n'.join(
            [
                'DB_HOST=localhost',
                'DB_PORT=3306',
                'DB_NAME=runtrackdb',
                'DB_USER=root',
                'DB_PASSWORD=password',
            ]
        ),
        encoding='utf-8',
    )

    result = load_database_config(
        env_file=env_file
    )

    assert result == {
        'host': 'localhost',
        'port': 3306,
        'database': 'runtrackdb',
        'username': 'root',
        'password': 'password',
    }