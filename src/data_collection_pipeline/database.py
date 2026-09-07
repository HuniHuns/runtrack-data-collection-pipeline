"""
MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당하는 모듈입니다.

로컬 환경에서는 .env 파일에서 데이터베이스 접속 정보를 읽습니다.
DB 연결 책임을 load.py에서 분리하여 적재 로직과 연결 설정을
독립적으로 관리할 수 있도록 구성합니다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from .config import ENV_FILE


REQUIRED_ENV_NAMES = {
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
}


def load_database_config(
    env_file: Path = ENV_FILE,
) -> dict[str, str | int]:
    """
    .env 파일에서 MySQL 연결 정보를 읽고 검증한다.

    Args:
        env_file:
            MySQL 연결 정보가 저장된 .env 파일 경로

    Returns:
        host, port, database, username, password를 담은 연결 설정

    Raises:
        FileNotFoundError:
            .env 파일이 존재하지 않는 경우

        ValueError:
            필수 환경 변수가 없거나 DB_PORT가 정수가 아닌 경우
    """

    if not env_file.is_file():
        raise FileNotFoundError(f'.env 파일이 없습니다. : {env_file}')

    load_dotenv(dotenv_path=env_file)

    missing_names = [
        name
        for name in REQUIRED_ENV_NAMES
        if not os.environ.get(name)
    ]

    if missing_names:
        raise ValueError(
            f'필수 환경 변수가 없습니다. : {sorted(missing_names)}'
        )

    try:
        port = int(os.environ['DB_PORT'])
    except ValueError as error:
        raise ValueError('DB_PORT는 정수여야 합니다.') from error

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
