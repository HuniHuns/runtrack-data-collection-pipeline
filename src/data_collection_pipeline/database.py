"""
MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당하는 모듈입니다.

로컬 환경에서는 .env 파일에서 데이터베이스 접속 정보를 읽습니다.
DB 연결 책임을 load.py에서 분리하여 적재 로직과 연결 설정을
독립적으로 관리할 수 있도록 구성합니다.
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

from .config import ENV_FILE

REQUIRED_LOCAL_ENV_NAMES = {
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
}

def _parse_port(port_value: str | int, source_name: str) -> int:
    """
    데이터베이스 포트 값을 정수로 변환하고 유효성을 검증합니다.

    Args:
        port_value:
            문자열 또는 정수 형태의 포트 값

        source_name:
            오류 메시지에 표시할 포트 값 출처

    Returns:
        정수형 포트 번호
    """

    try:
        port = int(port_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{source_name}는 정수여야 합니다.') from error

    if not 1 <= port <= 65535:
        raise ValueError(f'{source_name}는 1~65535 범위여야 합니다.')

    return port

# ============================================================
# 3. AWS Secrets Manager
# ============================================================

def _load_secret_value(
    secret_arn: str,
    secrets_client: Any | None = None,
) -> dict[str, Any]:
    """
    AWS Secrets Manager에서 Secret 값을 조회하고 JSON으로 변환합니다.

    Args:
        secret_arn:
            조회할 Secrets Manager Secret ARN

        secrets_client:
            테스트에서 사용할 Secrets Manager Mock Client

    Returns:
        SecretString을 파싱한 딕셔너리
    """

    if not secret_arn:
        raise ValueError('DB_SECRET_ARN이 지정되지 않았습니다.')

    if secrets_client is None:
        import boto3

        secrets_client = boto3.client('secretsmanager')

    response = secrets_client.get_secret_value(SecretId=secret_arn)

    secret_string = response.get('SecretString')

    if not secret_string:
        raise ValueError('Secrets Manager의 SecretString이 없습니다.')

    try:
        secret = json.loads(secret_string)
    except json.JSONDecodeError as error:
        raise ValueError(
            'Secrets Manager의 SecretString이 올바른 JSON 형식이 아닙니다.'
        ) from error

    if not isinstance(secret, dict):
        raise ValueError('Secrets Manager의 Secret 값은 JSON 객체여야 합니다.')

    return secret


def load_database_config_from_secret(
    secret_arn: str,
    secrets_client: Any | None = None,
) -> dict[str, str | int]:
    """
    AWS Secrets Manager와 Lambda 환경변수를 이용하여
    Amazon RDS MySQL 연결 정보를 구성합니다.

    Secret에 값이 존재하면 Secret 값을 우선 사용하고,
    없는 값은 Lambda 환경변수에서 조회합니다.

    Args:
        secret_arn:
            RDS가 관리하는 Secrets Manager Secret ARN

        secrets_client:
            테스트에서 사용할 Secrets Manager Mock Client

    Returns:
        MySQL 연결 설정 딕셔너리
    """

    secret = _load_secret_value(secret_arn=secret_arn, secrets_client=secrets_client)

    # --------------------------------------------------------
    # Username / Password
    # --------------------------------------------------------

    username = secret.get('username')
    password = secret.get('password')

    if not username:
        raise ValueError('Secrets Manager에 username이 없습니다.')

    if not password:
        raise ValueError('Secrets Manager에 password가 없습니다.')

    # --------------------------------------------------------
    # Host
    # --------------------------------------------------------

    host = secret.get('host') or os.environ.get('DB_HOST')

    if not host:
        raise ValueError('DB_HOST가 지정되지 않았습니다.')

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    database_name = secret.get('dbname') or os.environ.get('DB_NAME')

    if not database_name:
        raise ValueError('DB_NAME이 지정되지 않았습니다.')

    # --------------------------------------------------------
    # Port
    # --------------------------------------------------------

    port_value = secret.get('port') or os.environ.get('DB_PORT') or '3306'
    port = _parse_port(port_value=port_value, source_name='DB_PORT')

    return {
        'host': str(host),
        'port': port,
        'database': str(database_name),
        'username': str(username),
        'password': str(password),
    }




def load_database_config(
    env_file: Path = ENV_FILE,
    secrets_client: Any | None = None,
) -> dict[str, str | int]:
    """
    실행 환경에 따라 MySQL 연결 정보를 읽고 검증합니다.

    AWS Lambda:
        DB_SECRET_ARN 환경변수가 존재하면
        AWS Secrets Manager를 사용합니다.

    Local:
        DB_SECRET_ARN이 없으면
        .env 파일을 사용합니다.

    Args:
        env_file:
            로컬 실행 시 사용할 .env 파일 경로

        secrets_client:
            테스트에서 사용할 Secrets Manager Mock Client

    Returns:
        MySQL 연결 설정 딕셔너리
    """

    secret_arn = os.environ.get('DB_SECRET_ARN')

    if secret_arn:
        return load_database_config_from_secret(
            secret_arn=secret_arn,
            secrets_client=secrets_client,
        )
    
    if not env_file.is_file():
        raise FileNotFoundError(f'.env 파일이 없습니다. : {env_file}')

    load_dotenv(dotenv_path=env_file)

    missing_names = [
        name
        for name in REQUIRED_LOCAL_ENV_NAMES
        if not os.environ.get(name)
    ]

    if missing_names:
        raise ValueError(f'필수 환경 변수가 없습니다. {sorted(missing_names)}')

    port = _parse_port(
        port_value=os.environ['DB_PORT'],
        source_name='DB_PORT',
    )
    
    return {
        'host': os.environ['DB_HOST'],
        'port': port,
        'database': os.environ['DB_NAME'],
        'username': os.environ['DB_USER'],
        'password': os.environ['DB_PASSWORD'],
    }


def create_mysql_engine(
    config: dict[str, str | int],
) -> Engine:
    """
    MySQL 연결 설정으로 SQLAlchemy Engine을 생성한다.

    Args:
        config:
            load_database_config()가 반환한 연결 설정

    Returns:
        연결 유효성 확인과 재사용 설정이 적용된 SQLAlchemy Engine
    """

    database_url = URL.create(
        drivername='mysql+pymysql',
        username=str(config['username']),
        password=str(config['password']),
        host=str(config['host']),
        port=int(config['port']),
        database=str(config['database']),
        query={
            'charset': 'utf8mb4'
        },
    )

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def test_mysql_connection(
    engine: Engine,
) -> dict[str, str]:
    """
    MySQL 연결 상태와 서버 정보를 확인한다.

    Args:
        engine:
            연결을 확인할 SQLAlchemy Engine

    Returns:
        MySQL 버전, 데이터베이스명, 현재 사용자 정보
    """

    query = text(
        '''
        SELECT
            VERSION() AS version,
            DATABASE() AS database_name,
            CURRENT_USER() AS db_user
        '''
    )

    with engine.connect() as connection:
        info = (
            connection
            .execute(query)
            .mappings()
            .one()
        )

    return {
        'mysql_version': str(info['version']),
        'database_name': str(info['database_name']),
        'current_user': str(info['db_user']),
    }
