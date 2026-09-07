from pathlib import Path
from datetime import datetime
import re

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

RAW_CSV_PATTERN = 'marathon_schedule_raw_*.csv'

REQUIRED_INPUT_COLUMNS = {
    'title',
    'race_status',
    'region',
    'location',
    'course',
    'race_date',
    'registration_period',
    'assembly_time',
    'organizer',
    'official_url',
    'phone',
    'email',
}

COLUMN_ORDER = [
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
]

MISSING_VALUES = {
    '',
    '-',
    '미정',
    'na',
    'n/a',
    'null',
    'none',
}

REGION_MAP = {
    '서울': '서울',
    '인천': '인천',
    '경기': '경기',
    '강원': '강원',
    '제주': '제주',
    '충남': '충청',
    '세종': '충청',
    '대전': '충청',
    '충북': '충청',
    '경북': '경상',
    '대구': '경상',
    '경남': '경상',
    '울산': '경상',
    '부산': '경상',
    '전북': '전라',
    '광주': '전라',
    '전남': '전라',
}

ALLOWED_REGIONS = {
    '서울', '인천', '경기', '강원', '충청', '전라', '경상', '제주'
}

PHONE_PATTERN = re.compile(r'\d{0,3}-?\d{3,4}-\d{4}')


def find_latest_raw_csv(
    directory: Path = RAW_DIR,
    pattern: str = RAW_CSV_PATTERN,
):
    if not directory.exists():
        raise FileNotFoundError(f'RAW 데이터 폴더가 없습니다. {directory}')

    raw_files = sorted(directory.glob(pattern))

    if not raw_files:
        raise FileNotFoundError('전처리할 RAW csv 파일이 없습니다.')

    return raw_files[-1]


def load_raw_csv(file_path: Path) -> pd.DataFrame:
    if not file_path.is_file():
        raise FileNotFoundError(f'RAW csv 파일이 없습니다. : {file_path}')

    return pd.read_csv(file_path, dtype='string')


def validate_input_marathon(schedules_df: pd.DataFrame) -> None:
    if schedules_df.empty:
        raise ValueError('전처리할 마라톤 일정 데이터가 비어 있습니다.')

    missing_columns = REQUIRED_INPUT_COLUMNS - set(schedules_df.columns)

    if missing_columns:
        raise ValueError(f'입력 데이터의 필수 컬럼이 누락되었습니다. : {missing_columns}')


def clean_string_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    clean_df = df.copy()

    for column in clean_df.columns:
        clean_df[column] = (
            clean_df[column]
            .astype('string')
            .str
            .strip()
        )

        missing_mask = (
            clean_df[column]
            .str
            .casefold()
            .isin(MISSING_VALUES)
        )

        clean_df.loc[
            missing_mask,
            column,
        ] = pd.NA

    return clean_df


def parse_date(
    value,
):
    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    korean_date = re.search(
        r'(\d{4})년\s*'
        r'(\d{1,2})월\s*'
        r'(\d{1,2})일',
        text,
    )

    if korean_date:
        year, month, day = (
            korean_date.groups()
        )

        text = (
            f'{year}-'
            f'{int(month):02d}-'
            f'{int(day):02d}'
        )

    return pd.to_datetime(
        text,
        errors='coerce',
    )


def split_registration_period(
    value,
):
    if pd.isna(value):
        return pd.NaT, pd.NaT

    periods = re.split(
        r'\s*[~～]\s*',
        str(value).strip(),
        maxsplit=1,
    )

    if len(periods) != 2:
        return pd.NaT, pd.NaT

    return (
        parse_date(periods[0]),
        parse_date(periods[1]),
    )


def parse_assembly_time(
    value,
):
    if pd.isna(value):
        return pd.NA

    text = str(value).strip()

    is_pm = (
        text.startswith('오후')
        or text.upper().startswith('PM')
    )

    is_am = (
        text.startswith('오전')
        or text.upper().startswith('AM')
    )

    time_matches = re.findall(
        r'(\d{1,2})'
        r'(?:\s*:\s*|\s*시\s*)'
        r'(\d{1,2})?',
        text,
    )

    if not time_matches:
        return pd.NA

    times = []

    for hour_text, minute_text in time_matches:
        hour = int(hour_text)

        minute = (
            int(minute_text)
            if minute_text
            else 0
        )

        if is_pm and hour < 12:
            hour += 12

        if is_am and hour == 12:
            hour = 0

        if (
            0 <= hour <= 23
            and
            0 <= minute <= 59
        ):
            times.append(
                (hour, minute)
            )

    if not times:
        return pd.NA

    hour, minute = min(
        times,
        key=lambda time:
        time[0] * 60 + time[1],
    )

    return f'{hour:02d}:{minute:02d}'


def preprocessing_marathon_schedule(
    schedule_df: pd.DataFrame,
) -> pd.DataFrame:
    validate_input_marathon(schedule_df)

    processed_df = clean_string_columns(schedule_df)

    ## region 표준화
    processed_df['region'] = processed_df['region'].replace(REGION_MAP)

    ## location 공백 및 (예정) 제거
    processed_df['location'] = (
        processed_df['location']
        .str
        .replace(
            r'\s*\(예정\)\s*',
            '',
            regex=True,
        )
        .str
        .strip()
    )

    ## course 구분 기호 통일
    processed_df['course'] = (
        processed_df['course']
        .str
        .replace(
            r'\s*[·/]\s*',
            '|',
            regex=True,
        )
    )

    ## race_date 날짜형 변환
    processed_df['race_date'] = (
        processed_df['race_date']
        .map(parse_date)
    )

    ## registration_period 분리
    registration_dates = (
        processed_df['registration_period']
        .map(split_registration_period)
    )

    processed_df['registration_start_date'] = registration_dates.map(
        lambda value: value[0]
    )

    processed_df['registration_end_date'] = registration_dates.map(
        lambda value: value[1]
    )

    processed_df = processed_df.drop(columns=['registration_period'])

    ## assembly_time 정리
    processed_df['assembly_time'] = (
        processed_df['assembly_time']
        .map(parse_assembly_time)
        .astype('string')
    )

    ## organizer 좌우 공백 제거
    processed_df['organizer'] = (
        processed_df['organizer']
        .str
        .strip()
    )

    ## official_url 좌우 공백 제거
    processed_df['official_url'] = (
        processed_df['official_url']
        .str
        .strip()
    )

    ## 전화번호 형식이 올바르지 않으면 결측 처리
    valid_phone = (
        processed_df['phone']
        .str
        .fullmatch(PHONE_PATTERN)
        .fillna(False)
    )

    processed_df.loc[
        ~valid_phone,
        'phone',
    ] = pd.NA

    ## @가 없는 이메일은 결측 처리
    valid_email = (
        processed_df['email']
        .str
        .contains(
            '@',
            regex=False,
            na=False,
        )
    )

    processed_df.loc[
        ~valid_email,
        'email',
    ] = pd.NA

    ## 최종 컬럼 순서 정리
    return processed_df[COLUMN_ORDER]


def validate_processed_marathon(
    df: pd.DataFrame,
) -> dict:

    errors = []

    if list(df.columns) != COLUMN_ORDER:
        errors.append('최종 컬럼 순서가 올바르지 않습니다.')

    invalid_regions = (
        set(
            df['region']
            .dropna()
            .unique()
        )
        - ALLOWED_REGIONS
    )

    if invalid_regions:
        errors.append(f'허용되지 않은 지역값 : {sorted(invalid_regions)}')

    invalid_location_count = (
        df['location']
        .fillna('')
        .str
        .contains(
            r'\(예정\)',
            regex=True,
        )
        .sum()
    )

    if invalid_location_count:
        errors.append(
            f'location의 (예정) 제거 실패 : '
            f'{invalid_location_count}건'
        )

    invalid_course_count = (
        df['course']
        .fillna('')
        .str
        .contains(
            r'[·/]',
            regex=True,
        )
        .sum()
    )

    if invalid_course_count:
        errors.append(f'course 구분자 변환 실패 : {invalid_course_count}건')

    invalid_time_count = (
        df['assembly_time']
        .dropna()
        .str
        .fullmatch(
            r'\d{2}:\d{2}'
        )
        .eq(False)
        .sum()
    )

    if invalid_time_count:
        errors.append(f'집결시간 변환 실패 : {invalid_time_count}건')

    invalid_phone_count = (
        df['phone']
        .dropna()
        .str
        .fullmatch(
            PHONE_PATTERN
        )
        .eq(False)
        .sum()
    )

    if invalid_phone_count:
        errors.append(f'전화번호 형식 오류 : {invalid_phone_count}건')

    invalid_email_count = (
        ~df['email']
        .dropna()
        .str
        .contains(
            '@',
            regex=False,
        )
    ).sum()

    if invalid_email_count:
        errors.append(f'이메일 형식 오류 : {invalid_email_count}건')

    if errors:
        raise ValueError('전처리 데이터 검증 실패\n\n'.join(errors))

    return {
        'row_count': len(df),
        'column_count': len(df.columns),
        'null_count': int(
            df.isna().sum().sum()
        ),
    }


def build_processed_file_path(
    directory: Path = PROCESSED_DIR,
) -> Path:

    timestamp = datetime.now().strftime('%y%m%d_%H%M%S')

    file_name = (f'marathon_schedule_processed_{timestamp}.csv')

    return directory / file_name


def save_processed_csv(
    df: pd.DataFrame,
) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    file_path = build_processed_file_path()
    temp_path = file_path.with_suffix('.tmp.csv')

    try:
        df.to_csv(
            temp_path,
            index=False,
            encoding='utf-8-sig',
            date_format='%Y-%m-%d',
        )

        temp_path.replace(file_path)

    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    return file_path


def verify_saved_csv(
    saved_file: Path,
    original_df: pd.DataFrame,
) -> pd.DataFrame:
    saved_df = pd.read_csv(saved_file)

    if len(saved_df) != len(original_df):
        raise ValueError('csv 저장 전후의 행 수가 다릅니다.')

    if (list(saved_df.columns) != list(original_df.columns)):
        raise ValueError('csv 저장 전후의 컬럼 순서가 다릅니다.')

    return saved_df




def run_transform(
    raw_csv_file: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """RAW CSV를 전처리하고 processed CSV 파일 경로를 반환한다."""
    if raw_csv_file is None:
        raw_csv_file = find_latest_raw_csv()

    print('=' * 70)
    print('2. Transform - RUNTRACK 마라톤 일정 전처리 시작')
    print('=' * 70)
    print(f'전처리 대상 RAW csv : {raw_csv_file}')

    raw_df = load_raw_csv(raw_csv_file)
    processed_df = preprocessing_marathon_schedule(raw_df)
    validation_summary = validate_processed_marathon(processed_df)

    target_dir = output_dir if output_dir is not None else PROCESSED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_file = build_processed_file_path(directory=target_dir)
    temp_path = saved_file.with_suffix('.tmp.csv')

    try:
        processed_df.to_csv(
            temp_path,
            index=False,
            encoding='utf-8-sig',
            date_format='%Y-%m-%d',
        )
        temp_path.replace(saved_file)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    verify_saved_csv(saved_file, processed_df)

    print(f'전처리 검증 결과 : {validation_summary}')
    print(f'Processed csv 저장 완료 : {saved_file}')

    return saved_file
