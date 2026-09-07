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
    processed 폴더의 최신 마라톤 일정 csv를 반환한다.
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
    전처리 완료된 csv를 DataFrame으로 불러온다.
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
    .env 파일에서 MySQL 연결 정보를 읽는다.
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
    PyMySQL을 사용하는 SQLAlchemy Engine을 생성한다.
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
    연결된 MySQL 서버 정보를 확인한다.
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
    MySQL 적재 전 전처리 데이터를 검증한다.
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
    course 문자열을 개별 Course로 분리한다.
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
    기존 MySQL Database에 필요한 테이블을 생성한다.
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
    Pandas 값을 MySQL에 저장 가능한 값으로 변환한다.
    """

    if pd.isna(value):
        return None

    return value


def to_database_date(
    value,
):
    if pd.isna(value):
        return None

    return pd.Timestamp(
        value
    ).date()


def to_database_time(
    value,
):
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
    Course가 없으면 생성하고,
    이미 존재하면 기존 course_id를 반환한다.
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
    신규 대회는 INSERT,
    기존 대회는 UPDATE한다.

    Returns:
        schedule_id,
        신규 저장 여부
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
    한 대회와 Course의 관계를 저장한다.
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
    전처리 데이터를 MarathonSchedule,
    Course, ScheduleCourse 테이블에 저장한다.
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
    CSV의 모든 대회가 DB에 존재하는지 검증한다.
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
    최신 processed CSV 탐색부터
    MySQL 적재 및 검증까지 실행한다.
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


