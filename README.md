# RUNTRACK Marathon Data Collection Pipeline

`runfor.kr`에서 마라톤 대회 일정을 수집하고  
**Extract → Transform → Load** 순서로 처리하여 MySQL에 저장하는 데이터 수집 파이프라인 프로젝트입니다.

대회 목록은 Selenium으로 동적 요소를 로드하고, 각 대회의 상세 페이지는 `requests`와 `BeautifulSoup`으로 수집합니다.  
수집된 원본 데이터는 CSV로 보관하고, 지역·날짜·접수기간·집결시간·연락처 등을 표준화한 뒤 RUNTRACK 서비스에서 사용할 수 있는 형태로 MySQL에 적재합니다.

또한 `pytest`, `Ruff`, GitHub Actions를 이용하여 코드 품질과 테스트를 자동으로 검증하는 CI 환경을 구성합니다.

---

## 1. 프로젝트 구조

```text
runtrack-data-collection-pipeline/
│
├─ .github/
│  └─ workflows/
│     └─ ci.yml
│
├─ src/
│  └─ data_collection_pipeline/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ database.py
│     ├─ extract.py
│     ├─ load.py
│     └─ transform.py
│
├─ tests/
│  ├─ test_extract.py
│  └─ test_transform.py
│
├─ .env.example
├─ .gitignore
├─ main.py
├─ pyproject.toml
├─ README.md
├─ requirements.txt
└─ requirements-dev.txt
```

현재 파이프라인은 별도의 `interim` 단계 없이 **원본 CSV → 전처리 완료 CSV → MySQL** 흐름으로 구성됩니다.
`.aws-sam/`, `.venv/`, `data/`, `.env` 등은 실행 환경 또는 빌드 산출물이므로 Git에서 제외합니다.

---

## 2. 주요 Python 모듈

### `extract.py`, `transform.py`, `load.py`

ETL 단계별 코드를 재사용 가능한 Python 모듈로 관리합니다.

```text
src/
└─ data_collection_pipeline/
   ├─ __init__.py
   ├─ extract.py
   ├─ transform.py
   └─ load.py
```

각 모듈의 역할은 다음과 같습니다.

| 모듈 | 역할 |
|---|---|
| `extract.py` | `runfor.kr`의 대회 목록 및 상세 정보를 수집하고 RAW CSV 생성 |
| `transform.py` | RAW 데이터를 정제·표준화·검증하고 Processed CSV 생성 |
| `load.py` | Processed CSV를 검증하고 MySQL 테이블에 저장 |

### `.env`

MySQL 접속 정보처럼 코드에 직접 작성하면 안 되는 환경 변수를 저장합니다.

예:

```dotenv
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=
```

> `.env`에는 DB 비밀번호와 같은 민감한 정보가 포함될 수 있으므로 Git 저장소에 커밋하지 않습니다.

### `main.py`

전체 ETL 파이프라인의 진입점입니다.

각 단계가 생성한 실제 파일 경로를 다음 단계에 전달하여 하나의 실행 흐름으로 연결합니다.

```python
raw_csv_file = run_extract()

processed_csv_file = run_transform(
    raw_csv_file=raw_csv_file,
)

load_summary = run_load(
    processed_csv_file=processed_csv_file,
)
```

각 실행 함수의 입력과 반환값은 다음과 같습니다.

| 함수 | 입력 | 반환값 |
|---|---|---|
| `run_extract()` | headless 설정, 선택적 출력 디렉터리 | RAW CSV `Path` |
| `run_transform()` | RAW CSV `Path` | Processed CSV `Path` |
| `run_load()` | Processed CSV `Path` | MySQL 적재 결과 `dict` |

---

### `config.py`

프로젝트에서 공통으로 사용하는 설정을 관리합니다.

주요 설정:

```text
PROJECT_DIR
DEFAULT_DATA_DIR
DATA_DIR
RAW_DIR
PROCESSED_DIR
ENV_FILE

TARGET_URL
SOURCE_SITE

WAIT_TIMEOUT
CONNECT_TIMEOUT
READ_TIMEOUT
RACE_LINK_SELECTOR
LOAD_MORE_SELECTOR

RAW_CSV_PATTERN
PROCESSED_CSV_PATTERN

CHROMIUM_BINARY
CHROMEDRIVER_PATH

APP_TIMEZONE
```

현재 `APP_TIMEZONE`은 다음과 같이 정의되어 있습니다.

```text
Asia/Seoul
```

각 단계 모듈은 필요한 설정만 `config.py`에서 import하여 사용합니다.

---

### `database.py`

MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당합니다.

주요 함수:

```text
load_database_config()
create_mysql_engine()
test_mysql_connection()
```

DB 연결 정보는 로컬 `.env`에서 읽습니다.

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

데이터 적재 로직과 데이터베이스 연결 책임을 분리하여 관리합니다.

---

## 3. 전체 데이터 처리 흐름

```text
runfor.kr
   ↓
run_extract()
   ↓
data/raw/260831_113015
└─ marathon_schedule_raw_260831_113015.csv
   ↓
run_transform(raw_csv_file)
   ↓
data/processed/
└─ marathon_schedule_processed_260831_113120.csv
   ↓
run_load(processed_csv_file)
   ↓
MySQL
├─ marathon_schedule
├─ course
└─ schedule_course
```

ETL 관점에서는 다음과 같이 구분됩니다.

```text
Extract
├─ Selenium WebDriver 실행
├─ 대회 목록 페이지 로딩
├─ 더보기 버튼을 통한 추가 대회 로드
├─ 대회 상세 URL 수집
├─ requests + BeautifulSoup 상세 페이지 파싱
└─ RAW CSV 저장 및 저장 결과 검증

Transform
├─ 문자열 공백 및 결측값 정리
├─ 지역명 표준화
├─ 장소의 '(예정)' 문자열 제거
├─ 코스 구분자 통일
├─ 대회 날짜 변환
├─ 접수기간 시작일/종료일 분리
├─ 집결시간 HH:MM 형식 변환
├─ 전화번호/이메일 형식 검증
├─ 컬럼 순서 정리
└─ Processed CSV 저장 및 검증

Load
├─ Processed CSV 검증
├─ 서비스 DB 지역 코드 변환
├─ DB 컬럼명 변환
├─ .env 기반 MySQL 연결
├─ 테이블 생성
├─ 마라톤 일정 INSERT / UPDATE
├─ Course UPSERT
├─ Schedule-Course 관계 저장
└─ 최종 DB 적재 검증
```

---

## 4. 단계별 실행 함수

### 4.1 `run_extract()`

`runfor.kr`에서 마라톤 대회 정보를 수집하고 RAW CSV를 생성합니다.

주요 처리 흐름:

```text
create_driver()
   ↓
load_all_marathon()
   ↓
collect_marathon_url()
   ↓
collect_race_detail()
   ↓
crawl_marathon_schedule()
   ↓
save_raw_csv()
   ↓
verify_saved_raw_csv()
```

대회 목록 페이지는 Selenium으로 처리합니다.

```text
https://runfor.kr/
```

대회 목록에서 상세 페이지 URL을 수집한 뒤 각 상세 페이지는 `requests`로 요청하고 `BeautifulSoup`으로 다음 정보를 파싱합니다.

```text
대회명
대회 상태
지역
장소
종목
일정
접수기간
집결시간
주최
공식 URL
전화번호
이메일
```

저장 결과:

```text
data/raw/marathon_schedule_raw_YYMMDD_HHMMSS.csv
```

저장 직후 원본 DataFrame과 다시 읽은 CSV의 **행 수와 컬럼 순서가 동일한지 검증**합니다.

반환값:

```text
RAW CSV Path
```

---

### 4.2 `run_transform()`

`run_extract()`가 반환한 RAW CSV를 입력으로 받아 서비스에서 사용하기 적합한 형태로 전처리합니다.

입력:

```text
data/raw/marathon_schedule_raw_YYMMDD_HHMMSS.csv
```

주요 처리 내용은 다음과 같습니다.

#### 문자열 및 결측값 정리

다음 값은 결측값으로 정규화합니다.

```text
빈 문자열
-
미정
na
n/a
null
none
```

#### 지역 표준화

세부 지역을 RUNTRACK의 8개 권역으로 표준화합니다.

```text
서울 → 서울
인천 → 인천
경기 → 경기
강원 → 강원
충남/충북/세종/대전 → 충청
전북/광주/전남 → 전라
경북/대구/경남/울산/부산 → 경상
제주 → 제주
```

최종 허용 지역:

```text
서울, 인천, 경기, 강원, 충청, 전라, 경상, 제주
```

#### 장소 정리

장소명에 포함된 `(예정)` 문자열을 제거합니다.

예:

```text
여의도 한강공원 (예정)
→ 여의도 한강공원
```

#### 코스 구분자 통일

원본의 `·`, `/` 구분자를 `|`로 통일합니다.

예:

```text
10km / Half
→ 10km|Half
```

#### 날짜 변환

한글 날짜를 날짜형으로 변환합니다.

```text
2026년 10월 11일
→ 2026-10-11
```

#### 접수기간 분리

원본 `registration_period`를 시작일과 종료일로 분리합니다.

```text
2026-07-01 ~ 2026-09-30
```

변환 결과:

```text
registration_start_date = 2026-07-01
registration_end_date   = 2026-09-30
```

#### 집결시간 표준화

오전/오후 또는 AM/PM 형식을 24시간제 `HH:MM` 형태로 변환합니다.

```text
오전 8시
→ 08:00
```

#### 연락처 검증

전화번호가 지정된 형식을 만족하지 않거나 이메일에 `@`가 없는 경우 결측값으로 처리합니다.

전처리 완료 후 다음 항목을 검증합니다.

```text
최종 컬럼 순서
허용되지 않은 지역값
장소의 '(예정)' 제거 여부
코스 구분자 변환 여부
집결시간 형식
전화번호 형식
이메일 형식
```

저장 결과:

```text
data/processed/marathon_schedule_processed_YYMMDD_HHMMSS.csv
```

반환값:

```text
Processed CSV Path
```

---

### 4.3 `run_load()`

Processed CSV를 읽고 데이터를 검증한 뒤 MySQL에 적재합니다.

입력:

```text
data/processed/marathon_schedule_processed_YYMMDD_HHMMSS.csv
```

Load 단계에서는 먼저 Processed CSV의 필수 컬럼, 필수값, 중복 데이터를 검증합니다.

중복 판별 기준:

```text
title + race_date + location
```

그 후 지역명을 서비스 DB의 ENUM 값으로 변환합니다.

| Processed CSV | MySQL |
|---|---|
| 서울 | `SEOUL` |
| 인천 | `INCHEON` |
| 경기 | `GYEONGGI` |
| 강원 | `GANGWON` |
| 충청 | `CHUNGCHEONG` |
| 전라 | `JEONRA` |
| 경상 | `GYEONGSANG` |
| 제주 | `JEJU` |

일부 컬럼은 DB 스키마에 맞게 이름을 변경합니다.

| Processed CSV | MySQL |
|---|---|
| `location` | `event_field` |
| `race_date` | `event_date` |
| `registration_start_date` | `register_start_date` |
| `registration_end_date` | `register_end_date` |
| `phone` | `event_inquiry_phone` |
| `email` | `event_inquiry_email` |

`race_status`, `organizer`는 Processed CSV에는 유지되지만 현재 MySQL 적재 레코드에는 사용하지 않습니다.

---

## 5. MySQL 저장 구조

현재 파이프라인은 다음 3개 테이블을 사용합니다.

```text
marathon_schedule
course
schedule_course
```

### `marathon_schedule`

마라톤 대회의 기본 정보를 저장합니다.

주요 컬럼:

```text
schedule_id
title
official_url
region
event_field
event_date
register_start_date
register_end_date
assembly_time
event_inquiry_email
event_inquiry_phone
event_info
event_poster_url
create_date
update_date
```

`create_date`는 데이터가 최초 생성된 시각을 저장하고, `update_date`는 데이터 수정 시각을 관리하기 위한 컬럼입니다.

기존 대회 탐색 기준:

```text
title + event_date + event_field
```

동일한 기준의 데이터가 없으면 INSERT하고, 존재하면 기존 `schedule_id`를 기준으로 UPDATE합니다.

### `course`

마라톤 대회의 코스 정보를 중복 없이 관리합니다.

주요 컬럼:

```text
course_id
course_name
create_date
update_date
```

`course_name`에는 UNIQUE 제약조건이 적용되며, 동일한 코스가 이미 존재하면 기존 `course_id`를 사용합니다.

### `schedule_course`

마라톤 일정과 코스의 다대다 관계를 저장하는 연결 테이블입니다.

주요 컬럼:

```text
schedule_id
course_id
create_date
update_date
```

복합 Primary Key:

```text
(schedule_id, course_id)
```

관계 구조:

```text
marathon_schedule
        1
        │
        N
 schedule_course
        N
        │
        1
      course
```

---

## 6. 단계별 데이터 상태

| 단계 | 저장 위치 | 데이터 상태 |
|---|---|---|
| Extract | `data/raw/` | 웹페이지에서 수집한 원본 마라톤 일정 CSV |
| Transform | `data/processed/` | 표준화·자료형 변환·검증이 완료된 CSV |
| Load | MySQL | 서비스 DB 스키마에 맞게 적재된 데이터 |

---

## 7. 실행 환경 설정

### 실행 패키지 설치

프로젝트 실행에 필요한 패키지를 설치합니다.

```bash
python -m pip install -r requirements.txt
```

현재 주요 실행 의존성:

```text
requests
pandas
beautifulsoup4
python-dotenv
SQLAlchemy
PyMySQL
```

---

### 개발 및 CI 패키지 설치

테스트와 코드 품질 검사를 포함한 개발 환경은 다음 명령으로 구성합니다.

```bash
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt`:

```text
-r requirements.txt

pytest
ruff
```

따라서 실행 패키지와 함께 `pytest`, `Ruff`가 설치됩니다.

---

### MySQL 환경 변수

프로젝트 루트에 `.env` 파일을 생성합니다.

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=runtrack
DB_USER=root
DB_PASSWORD="MySQL 비밀번호"
```

필수 환경 변수:

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

필수 값이 없거나 `DB_PORT`가 정수가 아니면 Load 단계에서 실행을 중단합니다.

---

## 8. 전체 파이프라인 실행

프로젝트 루트에서 실행합니다.

```bash
python main.py
```

전체 실행 흐름:

```text
main.py
  │
  ├─ run_extract()
  │      ↓
  │   raw_csv_file
  │
  ├─ run_transform(raw_csv_file)
  │      ↓
  │   processed_csv_file
  │
  └─ run_load(processed_csv_file)
         ↓
      load_summary
```

핵심 연결 형태:

```python
from src.data_collection_pipeline import (
    run_extract,
    run_transform,
    run_load,
)


raw_csv_file = run_extract()

processed_csv_file = run_transform(
    raw_csv_file=raw_csv_file,
)

load_summary = run_load(
    processed_csv_file=processed_csv_file,
)
```

앞 단계의 실제 반환 경로를 다음 단계가 그대로 사용하기 때문에 같은 디렉터리에 여러 CSV가 존재하더라도 현재 실행에서 생성된 파일을 정확하게 연결할 수 있습니다.

---

## 9. 테스트

테스트 코드는 `tests/`에 위치합니다.

```text
tests/
├─ test_extract.py
└─ test_transform.py
```

현재 테스트 대상은 외부 네트워크나 MySQL에 직접 의존하지 않는 함수 중심으로 구성합니다.

주요 테스트 대상:

```text
build_raw_file_path()
save_raw_csv()
verify_saved_raw_csv()
parse_date()
split_registration_period()
parse_assembly_time()
preprocessing_marathon_schedule()
validate_processed_marathon()
build_processed_file_path()
```

전체 테스트 실행:

```bash
python -m pytest -v
```

`pyproject.toml`에서 pytest 테스트 경로를 지정합니다.

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

---

## 10. Ruff 코드 품질 검사

Ruff를 이용하여 Python 코드의 기본 오류와 코드 스타일을 검사합니다.

실행:

```bash
python -m ruff check .
```

현재 `pyproject.toml`에서 다음 규칙을 적용합니다.

```text
E4
E7
E9
F
I
DTZ
RUF
```

주요 검사 항목:

```text
Python 기본 문법 및 스타일
미사용 또는 잘못된 코드
import 정렬
datetime timezone 사용
Ruff 권장 코드 품질 규칙
```

Python 기준 버전:

```text
Python 3.13
```

한 줄 길이 기준:

```text
100
```

---

## 11. GitHub Actions CI

CI workflow는 다음 위치에 있습니다.

```text
.github/workflows/ci.yml
```

CI 실행 조건:

```text
main branch push
또는
main branch 대상 pull_request
```

실행 흐름:

```text
GitHub Push / Pull Request
        ↓
Checkout Repository
        ↓
Python 3.13 설정
        ↓
requirements-dev.txt 설치
        ↓
Ruff 검사
        ↓
pytest 실행
        ↓
CI 성공 / 실패
```

CI에서는 다음 두 명령을 자동으로 수행합니다.

```bash
python -m ruff check .
python -m pytest -v
```

따라서 로컬과 GitHub Actions에서 동일한 검사 명령을 사용할 수 있습니다.

---

## 12. Git 관리 정책

이 프로젝트는 블랙리스트 방식의 `.gitignore`를 사용합니다.

프로젝트 파일은 기본적으로 Git에서 추적하고,  
로컬 환경·비밀정보·실행 산출물·캐시 등을 제외합니다.

주요 제외 대상:

```text
.env
data/
logs/
*.log
docs/
notebooks/

__pycache__/
.pytest_cache/
.ruff_cache/

.venv/
venv/

.ipynb_checkpoints/
.vscode/
.idea/

build/
dist/
.aws-sam/
```

`.env.example`은 실제 비밀번호가 포함되지 않은 환경설정 예제이므로 Git에서 추적합니다.

---

## 13. 프로젝트 설계 원칙

이 프로젝트는 다음 원칙을 기준으로 구성합니다.

- 웹에서 수집한 원본 데이터는 `data/raw/`에 별도로 보관합니다.
- RAW 데이터와 전처리 완료 데이터를 분리합니다.
- 각 실행 결과는 timestamp가 포함된 파일명으로 관리합니다.
- 앞 단계가 생성한 실제 파일 경로를 다음 단계에 전달합니다.
- 데이터 전처리 과정에서 지역, 날짜, 시간, 연락처 형식을 표준화합니다.
- Processed CSV 저장 전 데이터 형식과 컬럼 구조를 검증합니다.
- MySQL 적재 전 필수 컬럼, 결측값, 중복 데이터를 다시 검증합니다.
- DB 연결 정보와 비밀번호는 `.env`로 분리합니다.
- `course`는 별도 테이블로 분리하여 동일 코스의 중복 저장을 방지합니다.
- `schedule_course` 연결 테이블을 이용하여 대회와 코스의 관계를 관리합니다.
- `create_date`, `update_date` 컬럼을 통해 DB 데이터의 생성·수정 시각을 관리합니다.
- `main.py`는 각 ETL 실행 함수를 연결하는 진입점 역할에 집중합니다.

---

## 14. 전체 파이프라인 요약

```text
[Extract]
runfor.kr
   ↓
Selenium으로 대회 목록 로드
   ↓
requests + BeautifulSoup으로 상세 페이지 수집
   ↓
RAW CSV

        ↓

[Transform]
문자열 정리
   ↓
지역 표준화
   ↓
날짜 / 접수기간 / 집결시간 변환
   ↓
전화번호 / 이메일 검증
   ↓
Processed CSV

        ↓

[Load]
Processed CSV 검증
   ↓
MySQL 연결
   ↓
marathon_schedule
course
schedule_course
   ↓
DB 적재 결과 검증
```

전체적으로 다음 ETL 흐름을 구성합니다.

```text
Extract → Transform → Load
```
