"""
RUNTRACK 마라톤 일정 RAW 데이터를 정제하고 표준화하는 Transform 모듈입니다.

Extract 단계에서 생성된 RAW CSV를 읽어 문자열과 결측 표현을 정리하고,
지역, 장소, 종목, 날짜, 접수기간, 집결시간, 연락처 형식을 변환합니다.
전처리 후에는 허용 지역, 시간 형식, 전화번호, 이메일 등을 검증하고
수집 시각이 포함된 processed CSV 파일로 저장합니다.

저장 구조:
    data/processed/
        marathon_schedule_processed_YYMMDD_HHMMSS.csv

반환값:
    run_transform()
        생성된 processed CSV 파일 경로
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import (
    APP_TIMEZONE,
    PROCESSED_DIR,
    RAW_CSV_PATTERN,
    RAW_DIR,
)

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
    """
    data/raw 폴더에서 가장 최근 RAW CSV 파일을 반환한다.

    Args:
        directory:
            RAW CSV 파일이 저장된 폴더

        pattern:
            검색할 RAW CSV 파일명 패턴

    Returns:
        파일명 정렬 기준으로 가장 최근 RAW CSV 파일 경로

    Raises:
        FileNotFoundError:
            RAW 폴더가 없거나 전처리할 RAW CSV 파일이 없는 경우
    """
        
    if not directory.exists():
        raise FileNotFoundError(f'RAW 데이터 폴더가 없습니다. {directory}')

    raw_files = sorted(directory.glob(pattern))

    if not raw_files:
        raise FileNotFoundError('전처리할 RAW csv 파일이 없습니다.')

    return raw_files[-1]


def load_raw_csv(file_path: Path) -> pd.DataFrame:
    """
    RAW CSV 파일을 문자열 자료형의 DataFrame으로 읽어 반환한다.

    Args:
        file_path:
            읽을 RAW CSV 파일 경로

    Returns:
        모든 컬럼을 Pandas string dtype으로 읽은 DataFrame

    Raises:
        FileNotFoundError:
            지정한 RAW CSV 파일이 존재하지 않는 경우
    """

    if not file_path.is_file():
        raise FileNotFoundError(f'RAW csv 파일이 없습니다. : {file_path}')

    return pd.read_csv(file_path, dtype='string')


def validate_input_marathon(schedules_df: pd.DataFrame) -> None:
    """
    전처리 입력 DataFrame의 데이터 존재 여부와 필수 컬럼을 검증한다.

    Args:
        schedules_df:
            Extract 단계에서 생성된 마라톤 일정 DataFrame

    Raises:
        ValueError:
            입력 데이터가 비어 있거나 필수 컬럼이 누락된 경우
    """

    if schedules_df.empty:
        raise ValueError('전처리할 마라톤 일정 데이터가 비어 있습니다.')

    missing_columns = REQUIRED_INPUT_COLUMNS - set(schedules_df.columns)

    if missing_columns:
        raise ValueError(f'입력 데이터의 필수 컬럼이 누락되었습니다. : {missing_columns}')


def clean_string_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    전체 컬럼을 문자열로 정리하고 공통 결측 표현을 Pandas NA로 변환한다.

    Args:
        df:
            문자열 정리가 필요한 원본 DataFrame

    Returns:
        좌우 공백 제거와 결측값 표준화가 완료된 DataFrame
    """

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
    """
    다양한 날짜 문자열을 Pandas Timestamp로 변환한다.

    YYYY년 M월 D일 형식은 YYYY-MM-DD 형태로 정규화한 뒤 변환하며,
    변환할 수 없는 값은 NaT로 처리한다.

    Args:
        value:
            변환할 날짜 값

    Returns:
        변환된 Timestamp 또는 변환할 수 없는 경우 NaT
    """

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
    """
    접수기간 문자열을 접수 시작일과 종료일로 분리한다.

    물결표(~)를 기준으로 최대 한 번 분리한 뒤 각 값을 parse_date()로 변환한다.

    Args:
        value:
            접수 시작일과 종료일이 함께 저장된 문자열

    Returns:
        접수 시작일과 종료일 Timestamp 튜플.
        값이 없거나 형식이 올바르지 않으면 (NaT, NaT) 반환
    """

    if pd.isna(value):
        return pd.NaT, pd.NaT

    periods = re.split(
        r'\s*[~]\s*',
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
    """
    집결시간 문자열에서 유효한 시간을 추출하여 HH:MM 형식으로 변환한다.

    오전/오후 또는 AM/PM 표현을 반영하고 여러 시간이 포함된 경우
    유효한 시간 중 가장 이른 시간을 선택한다.

    Args:
        value:
            변환할 집결시간 문자열

    Returns:
        HH:MM 형식의 시간 문자열 또는 변환할 수 없는 경우 Pandas NA
    """

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
    """
    마라톤 일정 RAW DataFrame을 분석 및 DB 저장이 가능한 구조로 전처리한다.

    주요 처리:
        - 문자열 및 결측 표현 정리
        - 지역값 표준화
        - 장소의 (예정) 표현 제거
        - 종목 구분자를 |로 통일
        - 대회일 날짜형 변환
        - 접수기간 시작일/종료일 분리
        - 집결시간 HH:MM 변환
        - 전화번호와 이메일 형식 검증
        - 최종 컬럼 순서 정리

    Args:
        schedule_df:
            Extract 단계의 RAW 마라톤 일정 DataFrame

    Returns:
        COLUMN_ORDER 순서로 정리된 전처리 DataFrame

    Raises:
        ValueError:
            입력 데이터가 비어 있거나 필수 컬럼이 누락된 경우
    """
    
    validate_input_marathon(schedule_df)

    processed_df = clean_string_columns(schedule_df)

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
    """
    전처리 결과의 컬럼 구조와 주요 값의 품질을 검증한다.

    Args:
        df:
            preprocessing_marathon_schedule()가 반환한 DataFrame

    Returns:
        행 수, 컬럼 수, 전체 결측값 수를 담은 검증 요약 딕셔너리

    Raises:
        ValueError:
            컬럼 순서, 지역값, 장소, 종목 구분자, 시간, 전화번호,
            이메일 형식 중 하나 이상이 검증 조건을 만족하지 않는 경우
    """

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
    """
    현재 시각을 포함한 processed CSV 파일 경로를 생성한다.

    Args:
        directory:
            processed CSV를 저장할 기본 폴더

    Returns:
        marathon_schedule_processed_YYMMDD_HHMMSS.csv 형식의 파일 경로
    """

    timestamp = datetime.now(APP_TIMEZONE).strftime('%y%m%d_%H%M%S')

    file_name = (f'marathon_schedule_processed_{timestamp}.csv')

    return directory / file_name


def save_processed_csv(
    df: pd.DataFrame,
) -> Path:
    """
    전처리 DataFrame을 하나의 processed CSV 파일로 저장한다.

    임시 파일에 먼저 저장한 뒤 최종 파일로 교체하여
    저장 도중 실패한 불완전한 파일이 남는 것을 방지한다.

    Args:
        df:
            저장할 전처리 DataFrame

    Returns:
        저장이 완료된 processed CSV 파일 경로

    Raises:
        OSError:
            폴더 생성 또는 CSV 저장에 실패한 경우
    """

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
    """
    저장한 processed CSV를 다시 읽고 저장 전후의 행 수와 컬럼 순서를 검증한다.

    Args:
        saved_file:
            저장이 완료된 processed CSV 파일 경로

        original_df:
            CSV 저장 전 전처리 DataFrame

    Returns:
        저장된 CSV를 다시 읽은 DataFrame

    Raises:
        ValueError:
            저장 전후의 행 수 또는 컬럼 순서가 다른 경우
    """

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
    """
    RAW CSV 로딩부터 전처리, 검증, processed CSV 저장까지 순서대로 실행한다.

    Args:
        raw_csv_file:
            전처리할 RAW CSV 파일 경로. 지정하지 않으면 최신 RAW CSV 사용

        output_dir:
            processed CSV를 저장할 폴더. 지정하지 않으면 기본 data/processed 폴더 사용

    Returns:
        이번 Transform 단계에서 생성된 processed CSV 파일 경로

    Raises:
        FileNotFoundError:
            전처리할 RAW CSV 파일을 찾을 수 없는 경우

        ValueError:
            입력 데이터 또는 전처리 결과 검증에 실패한 경우

        OSError:
            processed CSV 저장에 실패한 경우
    """

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

if __name__ == '__main__':
    try:
        run_transform()

    except (FileNotFoundError, OSError, ValueError) as error:
        print('정적 웹페이지 전처리 작업에 실패했습니다.')
        print(f'오류 내용 : {error}')

        raise SystemExit(1) from error