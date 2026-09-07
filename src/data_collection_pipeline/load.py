"""
RUNTRACK의 전처리된 마라톤 일정 데이터를 MySQL에 저장하는 Load 모듈입니다.

Transform 단계에서 생성된 processed CSV를 읽어 필수 컬럼, 결측값,
중복 데이터를 검증하고 DB 스키마에 맞게 지역값과 컬럼명을 변환합니다.
MySQL 연결 정보를 .env 파일에서 읽고 SQLAlchemy Engine을 생성한 뒤,
marathon_schedule, course, schedule_course 테이블에 데이터를 저장합니다.

모든 테이블은 최초 생성 시각과 갱신 시각을 관리하기 위해
create_date와 update_date 컬럼을 포함합니다.

저장 대상 테이블:
    marathon_schedule
        마라톤 대회의 기본 일정 및 연락처 정보

    course
        대회 종목 정보를 중복 없이 관리

    schedule_course
        마라톤 일정과 종목의 다대다 관계 관리

반환값:
    run_load()
        입력 파일명, DB명, 입력 건수, 신규/수정/관계 저장 건수 요약
"""

from datetime import datetime
from pathlib import Path
from typing import Any
import os

import pandas as pd
from dotenv import load_dotenv

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_DIR / 'data' / 'processed'

ENV_PATH = PROJECT_DIR / '.env'

PROCESSED_CSV_PATTERN = 'marathon_schedule_processed_*.csv'

REQUIRED_INPUT_COLUMNS = {
    'title',
    'race_status',
    'region',
    'location',
    'course',
    'race_date',
    'registration_start_date',
    'registration_end_date',
    'assembly_time',
    'organizer',
    'official_url',
    'phone',
    'email',
}

REGION_DB_MAP = {
    '서울': 'SEOUL',
    '인천': 'INCHEON',
    '경기': 'GYEONGGI',
    '강원': 'GANGWON',
    '충청': 'CHUNGCHEONG',
    '경상': 'GYEONGSANG',
    '전라': 'JEONRA',
    '제주': 'JEJU',
}

DB_COLUMN_MAP = {
    'location': 'event_field',
    'race_date': 'event_date',
    'registration_start_date': 'register_start_date',
    'registration_end_date': 'register_end_date',
    'phone': 'event_inquiry_phone',
    'email': 'event_inquiry_email',
}

DB_REGIONS = {
    'SEOUL',
    'GYEONGGI',
    'INCHEON',
    'CHUNGCHEONG',
    'JEONRA',
    'GYEONGSANG',
    'GANGWON',
    'JEJU',
}

REQUIRED_ENV_NAMES = {
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
}


CREATE_COURSE_TABLE_SQL = text(
    '''
    CREATE TABLE IF NOT EXISTS course (
        course_id BIGINT NOT NULL AUTO_INCREMENT,
        course_name VARCHAR(50) NOT NULL,
        create_date DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP,
        update_date DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,

        PRIMARY KEY (course_id),

        CONSTRAINT uq_course_name
            UNIQUE (course_name)
    )
    ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    '''
)

CREATE_MARATHON_SCHEDULE_TABLE_SQL = text(
    '''
    CREATE TABLE IF NOT EXISTS marathon_schedule (
        schedule_id BIGINT NOT NULL AUTO_INCREMENT,
        title VARCHAR(100) NOT NULL,
        official_url TEXT NULL,

        region ENUM(
            'SEOUL',
            'GYEONGGI',
            'INCHEON',
            'CHUNGCHEONG',
            'JEONRA',
            'GYEONGSANG',
            'GANGWON',
            'JEJU'
        ) NULL,

        event_field VARCHAR(100) NOT NULL,
        event_date DATE NOT NULL,

        register_start_date DATE NULL,
        register_end_date DATE NOT NULL,

        assembly_time TIME NULL,

        event_inquiry_email VARCHAR(50) NULL,
        event_inquiry_phone VARCHAR(20) NULL,

        event_info TEXT NULL,
        event_poster_url TEXT NULL,

        create_date DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP,
        update_date DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,

        PRIMARY KEY (schedule_id)
    )
    ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    '''
)

CREATE_SCHEDULE_COURSE_TABLE_SQL = text(
    '''
    CREATE TABLE IF NOT EXISTS schedule_course (
        schedule_id BIGINT NOT NULL,
        course_id BIGINT NOT NULL,

        create_date DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP,
        update_date DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,

        PRIMARY KEY (
            schedule_id,
            course_id
        ),

        CONSTRAINT fk_schedule_course_schedule
            FOREIGN KEY (schedule_id)
            REFERENCES marathon_schedule(schedule_id)
            ON DELETE CASCADE,

        CONSTRAINT fk_schedule_course_course
            FOREIGN KEY (course_id)
            REFERENCES course(course_id)
            ON DELETE CASCADE
    )
    ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    '''
)

UPSERT_COURSE_SQL = text(
    '''
    INSERT INTO course (
        course_name
    )
    VALUES (
        :course_name
    )

    ON DUPLICATE KEY UPDATE
        course_id = LAST_INSERT_ID(course_id)
    '''
)

SELECT_SCHEDULE_SQL = text(
    '''
    SELECT schedule_id

    FROM marathon_schedule

    WHERE title = :title
      AND event_date = :event_date
      AND event_field = :event_field
    '''
)

INSERT_SCHEDULE_SQL = text(
    '''
    INSERT INTO marathon_schedule (
        title,
        official_url,
        region,
        event_field,
        event_date,
        register_start_date,
        register_end_date,
        assembly_time,
        event_inquiry_email,
        event_inquiry_phone,
        event_info,
        event_poster_url
    )
    VALUES (
        :title,
        :official_url,
        :region,
        :event_field,
        :event_date,
        :register_start_date,
        :register_end_date,
        :assembly_time,
        :event_inquiry_email,
        :event_inquiry_phone,
        NULL,
        NULL
    )
    '''
)

UPDATE_SCHEDULE_SQL = text(
    '''
    UPDATE marathon_schedule

    SET
        official_url = :official_url,
        region = :region,
        event_field = :event_field,
        event_date = :event_date,
        register_start_date = :register_start_date,
        register_end_date = :register_end_date,
        assembly_time = :assembly_time,
        event_inquiry_email = :event_inquiry_email,
        event_inquiry_phone = :event_inquiry_phone,
        update_date = CURRENT_TIMESTAMP

    WHERE schedule_id = :schedule_id
    '''
)

DELETE_SCHEDULE_COURSE_SQL = text(
    '''
    DELETE FROM schedule_course
    WHERE schedule_id = :schedule_id
    '''
)


INSERT_SCHEDULE_COURSE_SQL = text(
    '''
    INSERT INTO schedule_course (
        schedule_id,
        course_id
    )
    VALUES (
        :schedule_id,
        :course_id
    )
    '''
)


def find_latest_processed_csv(
    directory: Path = PROCESSED_DIR,
    pattern: str = PROCESSED_CSV_PATTERN,
):
    """
    data/processed 폴더에서 가장 최근 processed CSV 파일을 반환한다.

    Args:
        directory:
            processed CSV 파일이 저장된 폴더

        pattern:
            검색할 processed CSV 파일명 패턴

    Returns:
        파일명 정렬 기준으로 가장 최근 processed CSV 파일 경로

    Raises:
        FileNotFoundError:
            processed 폴더가 없거나 MySQL에 적재할 CSV 파일이 없는 경우
    """

    if not directory.exists():
        raise FileNotFoundError(f'전처리 데이터 폴더가 없습니다. : {directory}')

    processed_files = sorted(directory.glob(pattern))

    if not processed_files:
        raise FileNotFoundError('MySQL에 적재할 전처리 csv가 없습니다. 먼저 전처리 단계를 실행하세요.')

    return processed_files[-1]


def load_processed_csv(
    file_path: Path,
) -> pd.DataFrame:
    """
    전처리 완료된 processed CSV를 지정한 자료형의 DataFrame으로 읽는다.

    Args:
        file_path:
            읽을 processed CSV 파일 경로

    Returns:
        문자열과 날짜 자료형이 지정된 마라톤 일정 DataFrame

    Raises:
        FileNotFoundError:
            지정한 processed CSV 파일이 존재하지 않는 경우
    """

    if not file_path.is_file():
        raise FileNotFoundError(f'전처리 csv 파일이 없습니다. : {file_path}')

    return pd.read_csv(
        file_path,
        dtype={
            'title': 'string',
            'race_status': 'string',
            'region': 'string',
            'location': 'string',
            'course': 'string',
            'assembly_time': 'string',
            'organizer': 'string',
            'official_url': 'string',
            'phone': 'string',
            'email': 'string',
        },
        parse_dates=[
            'race_date',
            'registration_start_date',
            'registration_end_date',
        ],
    )


def load_database_config(
    env_path: Path = ENV_PATH,
) -> dict[str, str | int]:
    """
    .env 파일에서 MySQL 연결 정보를 읽고 필수 환경변수를 검증한다.

    Args:
        env_path:
            MySQL 연결 정보가 저장된 .env 파일 경로

    Returns:
        host, port, database, username, password를 담은 연결 설정

    Raises:
        FileNotFoundError:
            .env 파일이 존재하지 않는 경우

        ValueError:
            필수 환경변수가 없거나 DB_PORT가 정수가 아닌 경우
    """

    if not env_path.is_file():
        raise FileNotFoundError(f'.env 파일이 없습니다. : {env_path}')

    load_dotenv(dotenv_path=env_path)

    missing_names = REQUIRED_ENV_NAMES - set(os.environ)

    if missing_names:
        raise ValueError(f'필수 환경 변수가 없습니다. : {sorted(missing_names)}')

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
    MySQL 연결 설정으로 PyMySQL 기반 SQLAlchemy Engine을 생성한다.

    Args:
        config:
            load_database_config()가 반환한 MySQL 연결 설정

    Returns:
        연결 유효성 확인과 재사용 설정이 적용된 SQLAlchemy Engine
    """

    database_url = URL.create(
        drivername='mysql+pymysql',
        username=config['username'],
        password=config['password'],
        host=config['host'],
        port=config['port'],
        database=config['database'],
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
        MySQL 버전, 연결 데이터베이스명, 현재 사용자 정보를 담은 딕셔너리

    Raises:
        SQLAlchemyError:
            MySQL 연결 또는 확인 쿼리 실행에 실패한 경우
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
        'mysql_version':
            str(info['version']),

        'database_name':
            str(info['database_name']),

        'current_user':
            str(info['db_user']),
    }


def validate_processed_data(
    df: pd.DataFrame,
) -> None:
    """
    MySQL 적재 전 processed DataFrame의 필수 조건을 검증한다.

    Args:
        df:
            Transform 단계에서 생성된 마라톤 일정 DataFrame

    Raises:
        ValueError:
            데이터가 비어 있거나 필수 컬럼 누락, NOT NULL 컬럼 결측,
            동일 대회 중복 데이터가 존재하는 경우
    """

    if df.empty:
        raise ValueError('DB에 저장할 데이터가 없습니다.')

    missing_columns = (REQUIRED_INPUT_COLUMNS - set(df.columns))

    if missing_columns:
        raise ValueError(
            'DB 적재에 필요한 컬럼이 누락되었습니다. '
            f': {sorted(missing_columns)}'
        )

    required_not_null = [
        'title',
        'region',
        'location',
        'race_date',
    ]

    null_counts = df[required_not_null].isna().sum()

    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(
            'NOT NULL 대상 컬럼에 결측값이 있습니다.\n'
            f'{invalid_nulls.to_string()}'
        )

    duplicate_count = (
        df.duplicated(
            subset=[
                'title',
                'race_date',
                'location',
            ]
        )
        .sum()
    )

    if duplicate_count:
        raise ValueError(
            f'동일 대회 중복 데이터가 있습니다. '
            f': {duplicate_count}건'
        )


def parse_courses(
    value,
) -> list[str]:
    """
    | 구분자로 저장된 course 문자열을 개별 종목 목록으로 분리한다.

    중복 종목은 최초 등장 순서를 유지하면서 제거한다.

    Args:
        value:
            하나 이상의 대회 종목이 저장된 문자열

    Returns:
        공백과 중복을 제거한 Course 이름 목록
    """

    if pd.isna(value):
        return []

    courses = [
        course.strip()
        for course in str(value).split('|')
        if course.strip()
    ]

    return list(
        dict.fromkeys(courses)
    )


def create_tables(
    engine: Engine,
) -> None:
    """
    RUNTRACK 적재에 필요한 MySQL 테이블이 없으면 생성한다.

    생성 대상:
        - course
        - marathon_schedule
        - schedule_course

    Args:
        engine:
            테이블을 생성할 MySQL SQLAlchemy Engine

    Raises:
        SQLAlchemyError:
            테이블 생성 쿼리 실행에 실패한 경우
    """

    with engine.begin() as connection:

        connection.execute(
            CREATE_COURSE_TABLE_SQL
        )

        connection.execute(
            CREATE_MARATHON_SCHEDULE_TABLE_SQL
        )

        connection.execute(
            CREATE_SCHEDULE_COURSE_TABLE_SQL
        )


def to_database_value(
    value,
):
    """
    Pandas 결측값을 MySQL에 저장 가능한 None으로 변환한다.

    Args:
        value:
            DB 저장용으로 변환할 Pandas 또는 Python 값

    Returns:
        결측값이면 None, 그렇지 않으면 원래 값
    """

    if pd.isna(value):
        return None

    return value


def to_database_date(
    value,
):
    """
    Pandas 날짜 값을 MySQL DATE에 저장할 Python date로 변환한다.

    Args:
        value:
            변환할 날짜 값

    Returns:
        Python date 또는 결측값인 경우 None
    """

    if pd.isna(value):
        return None

    return pd.Timestamp(
        value
    ).date()


def to_database_time(
    value,
):
    """
    HH:MM 문자열을 MySQL TIME에 저장할 Python time으로 변환한다.

    Args:
        value:
            변환할 집결시간 값

    Returns:
        Python time 또는 결측값인 경우 None

    Raises:
        ValueError:
            값이 HH:MM 형식과 일치하지 않는 경우
    """

    if pd.isna(value):
        return None

    return datetime.strptime(
        str(value),
        '%H:%M'
    ).time()


def get_or_create_course(
    connection,
    course_name: str,
) -> int:
    """
    Course가 없으면 생성하고 이미 존재하면 기존 course_id를 반환한다.

    Args:
        connection:
            현재 적재 트랜잭션의 SQLAlchemy Connection

        course_name:
            저장하거나 조회할 대회 종목명

    Returns:
        신규 또는 기존 Course의 course_id
    """

    result = connection.execute(
        UPSERT_COURSE_SQL,
        {
            'course_name':
                course_name
        },
    )

    return int(
        result.lastrowid
    )


def find_schedule_id(
    connection,
    record: dict[str, Any],
) -> int | None:
    """
    대회명, 개최일, 개최장소를 기준으로 기존 일정의 schedule_id를 조회한다.

    Args:
        connection:
            현재 적재 트랜잭션의 SQLAlchemy Connection

        record:
            title, event_date, event_field를 포함한 마라톤 일정 레코드

    Returns:
        기존 일정의 schedule_id 또는 존재하지 않는 경우 None
    """

    schedule_id = (
        connection.execute(
            SELECT_SCHEDULE_SQL,
            {
                'title':
                    record['title'],

                'event_date':
                    record['event_date'],

                'event_field':
                    record['event_field'],
            },
        )
        .scalar_one_or_none()
    )

    if schedule_id is None:
        return None

    return int(
        schedule_id
    )


def upsert_marathon_schedule(
    connection,
    record: dict[str, Any],
) -> tuple[int, bool]:
    """
    마라톤 일정이 없으면 INSERT하고 기존 일정이면 UPDATE한다.

    기존 일정의 식별은 title, event_date, event_field 조합으로 수행하며,
    UPDATE 시 update_date를 현재 시각으로 갱신한다.

    Args:
        connection:
            현재 적재 트랜잭션의 SQLAlchemy Connection

        record:
            marathon_schedule 테이블에 저장할 대회 데이터

    Returns:
        schedule_id와 신규 저장 여부를 담은 튜플
    """

    schedule_id = (
        find_schedule_id(
            connection,
            record,
        )
    )

    if schedule_id is None:

        result = connection.execute(
            INSERT_SCHEDULE_SQL,
            record,
        )

        return (
            int(result.lastrowid),
            True,
        )

    update_record = (
        record.copy()
    )

    update_record[
        'schedule_id'
    ] = schedule_id

    connection.execute(
        UPDATE_SCHEDULE_SQL,
        update_record,
    )

    return (
        schedule_id,
        False,
    )


def save_schedule_courses(
    connection,
    schedule_id: int,
    course_names: list[str],
) -> int:
    """
    한 마라톤 일정과 Course의 관계를 schedule_course 테이블에 저장한다.

    기존 schedule_id의 관계를 삭제한 뒤 현재 course_names 기준으로 다시 생성한다.

    Args:
        connection:
            현재 적재 트랜잭션의 SQLAlchemy Connection

        schedule_id:
            관계를 저장할 marathon_schedule의 기본키

        course_names:
            연결할 Course 이름 목록

    Returns:
        이번 일정에 저장한 schedule_course 관계 건수
    """

    connection.execute(
        DELETE_SCHEDULE_COURSE_SQL,
        {
            'schedule_id':
                schedule_id
        },
    )

    saved_count = 0

    for course_name in course_names:

        course_id = (
            get_or_create_course(
                connection,
                course_name,
            )
        )

        connection.execute(
            INSERT_SCHEDULE_COURSE_SQL,
            {
                'schedule_id':
                    schedule_id,

                'course_id':
                    course_id,
            },
        )

        saved_count += 1

    return saved_count


def load_marathon_schedules(
    engine: Engine,
    df: pd.DataFrame,
) -> dict[str, int]:
    """
    전처리 DataFrame을 marathon_schedule, course, schedule_course 테이블에 저장한다.

    각 행의 종목 문자열을 분리하고 DB 저장용 자료형으로 변환한 뒤
    일정 INSERT/UPDATE와 Course 관계 저장을 하나의 트랜잭션에서 수행한다.

    Args:
        engine:
            데이터를 저장할 MySQL SQLAlchemy Engine

        df:
            DB 컬럼명으로 변환된 마라톤 일정 DataFrame

    Returns:
        신규 일정 수, 수정 일정 수, Course 관계 저장 수를 담은 딕셔너리
    """

    inserted_count = 0
    updated_count = 0
    relation_count = 0

    with engine.begin() as connection:

        for _, row in df.iterrows():

            course_names = (
                parse_courses(
                    row['course']
                )
            )

            record = {
                'title':
                    to_database_value(
                        row['title']
                    ),

                'official_url':
                    to_database_value(
                        row['official_url']
                    ),

                'region':
                    to_database_value(
                        row['region']
                    ),

                'event_field':
                    to_database_value(
                        row['event_field']
                    ),

                'event_date':
                    to_database_date(
                        row['event_date']
                    ),

                'register_start_date':
                    to_database_date(
                        row['register_start_date']
                    ),

                'register_end_date':
                    to_database_date(
                        row['register_end_date']
                    ),

                'assembly_time':
                    to_database_time(
                        row['assembly_time']
                    ),

                'event_inquiry_email':
                    to_database_value(
                        row['event_inquiry_email']
                    ),

                'event_inquiry_phone':
                    to_database_value(
                        row['event_inquiry_phone']
                    ),
            }

            (
                schedule_id,
                is_inserted,
            ) = upsert_marathon_schedule(
                connection,
                record,
            )

            if is_inserted:
                inserted_count += 1
            else:
                updated_count += 1

            relation_count += (
                save_schedule_courses(
                    connection,
                    schedule_id,
                    course_names,
                )
            )

    return {
        'inserted_count':
            inserted_count,

        'updated_count':
            updated_count,

        'relation_count':
            relation_count,
    }


def validate_loaded_schedules(
    engine: Engine,
    source_df: pd.DataFrame,
) -> None:
    """
    processed CSV의 모든 대회 키가 MySQL에 존재하는지 검증한다.

    대회명, 개최일, 개최장소를 기준으로 원본 DataFrame과
    marathon_schedule 테이블 조회 결과를 비교한다.

    Args:
        engine:
            적재 결과를 조회할 MySQL SQLAlchemy Engine

        source_df:
            실제 DB 적재에 사용한 마라톤 일정 DataFrame

    Raises:
        ValueError:
            입력 데이터 중 DB에서 찾을 수 없는 대회가 존재하는 경우
    """

    db_schedule_df = pd.read_sql(
        '''
        SELECT
            title,
            event_date,
            event_field

        FROM marathon_schedule
        ''',
        engine,
    )

    source_keys = source_df[['title','event_date','event_field']].copy()

    source_keys['event_date'] = (
        pd.to_datetime(source_keys['event_date'])
        .dt
        .date
        .astype('string')
    )

    db_schedule_df['event_date'] = (
        pd.to_datetime(db_schedule_df['event_date'])
        .dt
        .date
        .astype('string')
    )

    result = source_keys.merge(
        db_schedule_df,
        how='left',
        on=['title', 'event_date', 'event_field'],
        indicator=True,
    )

    missing_rows = result[result['_merge'] != 'both']

    if not missing_rows.empty:
        raise ValueError(f'DB에 적재되지 않은 대회가 존재합니다.: {len(missing_rows)}건')

    print(f'전체 {len(source_df)}개 대회\nMySQL 적재 검증 완료')


def run_load(
    processed_csv_file: Path | None = None,
) -> dict[str, Any]:
    """
    processed CSV 탐색부터 검증, MySQL 연결, 테이블 생성, 적재 검증까지 실행한다.

    Args:
        processed_csv_file:
            MySQL에 적재할 processed CSV 파일 경로.
            지정하지 않으면 data/processed의 최신 CSV 사용

    Returns:
        입력 파일명, 데이터베이스명, 입력 건수, 신규/수정/관계 저장 건수를 담은 딕셔너리

    Raises:
        FileNotFoundError:
            processed CSV 또는 .env 파일을 찾을 수 없는 경우

        ValueError:
            입력 데이터 검증 또는 DB 적재 결과 검증에 실패한 경우

        SQLAlchemyError:
            MySQL 연결, 테이블 생성 또는 데이터 저장에 실패한 경우
    """

    if processed_csv_file is None:
        processed_csv_file = find_latest_processed_csv()

    processed_df = load_processed_csv(processed_csv_file)
    validate_processed_data(processed_df)

    database_df = processed_df.copy()

    database_df['region'] = (
        database_df['region']
        .map(REGION_DB_MAP)
        .astype('string')
    )

    database_df = database_df.rename(columns=DB_COLUMN_MAP)

    database_config = load_database_config()
    engine = create_mysql_engine(database_config)

    try:
        connection_info = test_mysql_connection(engine)

        create_tables(engine)
        load_result = (
            load_marathon_schedules(
                engine=engine,
                df=database_df,
            )
        )

        validate_loaded_schedules(
            engine=engine,
            source_df=database_df,
        )

        print('=' * 70)
        print('RUNTRACK 마라톤 일정 MySQL 적재 결과')
        print('=' * 70)

        print(f'입력 CSV : {processed_csv_file.name}')
        print(f'연결 Database : {connection_info["database_name"]}')
        print(f'입력 데이터 수 : {len(database_df)}')
        print(f'신규 저장 : {load_result["inserted_count"]}')
        print(f'기존 데이터 수정 : {load_result["updated_count"]}')
        print(f'Course 관계 저장 : {load_result["relation_count"]}')

        return {
            'input_file': processed_csv_file.name,
            'database_name': connection_info['database_name'],
            'input_count': len(database_df),
            **load_result,
        }

    finally:
        engine.dispose()

if __name__ == '__main__':
    try:
        run_load()

    except SQLAlchemyError as error:
        print('MySQL 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')
        raise SystemExit(1) from error

    except (FileNotFoundError, OSError, ValueError) as error:
        print('파일 처리 또는 데이터 검증에 실패했습니다.')
        print(f'오류 내용 : {error}')
        raise SystemExit(1) from error