# RUNTRACK Marathon Data Collection Pipeline

`runfor.kr`에서 마라톤 대회 일정을 수집하고 **Extract → Transform → Load** 순서로 처리한 뒤, 로컬 MySQL 또는 Amazon RDS MySQL에 적재하는 데이터 수집 파이프라인입니다.

대회 목록은 Selenium으로 동적 요소를 로드하고, 각 대회의 상세 페이지는 `requests`와 `BeautifulSoup`으로 수집합니다. 원본 데이터는 RAW CSV로 보존하고, 지역·날짜·접수기간·집결시간·연락처·코스 등을 표준화한 Processed CSV를 생성한 뒤 서비스 DB 스키마에 맞춰 저장합니다.

로컬 환경에서는 `main.py`가 전체 ETL을 순차 실행하며, AWS 환경에서는 Lambda별로 책임을 분리하고 Amazon S3를 단계 간 데이터 저장소로 사용합니다. Step Functions는 Lambda 실행 순서와 메타데이터 전달을 담당하고, EventBridge Scheduler는 상태 머신을 정해진 시간에 실행할 수 있도록 구성합니다.

또한 `pytest`, Ruff, GitHub Actions를 이용하여 코드 품질과 테스트를 검증하고, AWS SAM과 CloudFormation을 통해 Lambda, S3, Step Functions, EventBridge Scheduler 및 IAM 구성을 관리합니다.

---

## 1. 프로젝트 목표

이 프로젝트의 주요 목표는 다음과 같습니다.

- `runfor.kr`의 동적 마라톤 대회 목록과 상세 정보를 수집합니다.
- 한 번의 수집 실행을 `batch_id` 기준으로 관리합니다.
- 웹에서 수집한 RAW 데이터와 전처리가 완료된 Processed 데이터를 분리합니다.
- 원본 RAW CSV는 수집값을 유지한 상태로 별도 보관합니다.
- Transform 단계에서 지역, 날짜, 접수기간, 집결시간, 연락처 등의 형식을 표준화합니다.
- 데이터 저장 전 필수 컬럼, 결측값, 중복값, 형식을 검증합니다.
- 로컬 환경에서는 `Extract → Transform → Load` 전체 흐름을 순차 실행합니다.
- AWS 환경에서는 각 ETL 단계를 Lambda로 분리합니다.
- Lambda 사이의 대용량 데이터는 직접 전달하지 않고 S3를 사용합니다.
- Lambda 간에는 `batch_id`, `bucket`, `prefix`, `object key` 같은 메타데이터를 전달합니다.
- Load Lambda는 AWS Secrets Manager에서 RDS 자격 증명을 조회합니다.
- Step Functions를 이용하여 Extract, Transform, Load Lambda를 순차 실행합니다.
- EventBridge Scheduler를 이용해 전체 AWS 파이프라인을 정기 실행할 수 있도록 구성합니다.
- AWS SAM을 이용해 주요 AWS 리소스를 코드로 정의하고 배포합니다.
- `pytest`, Ruff, GitHub Actions를 이용해 코드와 테스트를 지속적으로 검증합니다.

---

## 2. 전체 구성

### 2.1 로컬 파이프라인

로컬에서는 `main.py`가 전체 ETL 파이프라인의 진입점입니다.

```text
runfor.kr
    ↓
Extract
    ↓
data/raw/{batch_id}/
    ↓
RAW CSV
    ↓
Transform
    ↓
data/processed/
    ↓
Processed CSV
    ↓
Load
    ↓
MySQL
```

실행 함수 기준:

```text
run_extract()
    ↓
run_transform()
    ↓
run_load()
```

각 단계에서 반환한 실제 파일 경로를 다음 단계에 전달하므로 같은 디렉터리에 여러 CSV가 존재하더라도 현재 실행에서 생성한 파일을 명확하게 연결할 수 있습니다.

---

### 2.2 AWS 파이프라인

AWS 환경에서는 Extract, Transform, Load를 Lambda로 분리합니다.

```text
EventBridge Scheduler
        ↓
AWS Step Functions
        ↓
Extract Lambda
        ↓
/tmp/data/raw/{batch_id}/
        ↓
Amazon S3
raw/{batch_id}/
        ↓
Transform Lambda
        ↓
/tmp/data/raw/{batch_id}/
        ↓
전처리 / 표준화 / 검증
        ↓
/tmp/data/processed/
        ↓
Amazon S3
processed/{batch_id}/
        ↓
Load Lambda
        ↓
/tmp/data/processed/
        ↓
AWS Secrets Manager
        ↓
Amazon RDS MySQL
```

AWS 단계 간에는 CSV 데이터 자체를 Step Functions Payload로 전달하지 않습니다.

```text
Extract Lambda
    ↓
batch_id
bucket
raw_prefix
raw_key
    ↓
Transform Lambda
    ↓
batch_id
bucket
processed_prefix
processed_key
    ↓
Load Lambda
```

S3는 Lambda별로 독립된 `/tmp` 파일시스템 사이에서 데이터를 전달하는 공용 저장소 역할을 합니다.

---

## 3. 프로젝트 구조

주요 파일과 디렉터리는 다음과 같이 구성됩니다.

```text
runtrack-data-collection-pipeline/
│
├─ .github/
│  └─ workflows/
│     └─ ci.yml
│     └─ deploy.yml
│
├─ events/
│  ├─ transform-event.json
│  └─ load-event.json
│
├─ handlers/
│  ├─ __init__.py
│  ├─ extract_handler.py
│  ├─ transform_handler.py
│  └─ load_handler.py
│
├─ src/
│  └─ data_collection_pipeline/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ database.py
│     ├─ extract.py
│     ├─ transform.py
│     ├─ load.py
│     └─ s3_storage.py
│
├─ tests/
│  ├─ test_extract.py
│  ├─ test_transform.py
│  ├─ test_extract_handler.py
│  ├─ test_transform_handler.py
│  ├─ test_load_handler.py
│  ├─ test_database.py
│  └─ test_s3_storage.py
│
├─ .dockerignore
├─ .env.example
├─ .gitignore
├─ Dockerfile.extract
├─ main.py
├─ pyproject.toml
├─ README.md
├─ requirements.txt
├─ requirements-dev.txt
├─ requirements-extract.txt
└─ template.yaml
```

실행 중 생성되는 다음 파일과 디렉터리는 Git 관리 대상에서 제외합니다.

```text
.env
.venv/
.aws-sam/
data/
logs/
*.log
samconfig.toml
```

---

## 4. 주요 Python 모듈

### 4.1 `config.py`

프로젝트에서 공통으로 사용하는 경로, 수집 설정, Selenium 실행 경로, 시간대를 관리합니다.

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

로컬 환경에서는 기본적으로 프로젝트 루트의 `data/`를 사용합니다.

AWS Lambda에서는 `template.yaml`의 환경변수를 통해 다음 경로를 사용합니다.

```text
DATA_DIR=/tmp/data
```

시간대:

```text
Asia/Seoul
```

---

### 4.2 `extract.py`

`runfor.kr`에서 마라톤 대회 목록과 상세 정보를 수집하고 RAW CSV를 생성합니다.

대회 목록 페이지는 Selenium으로 처리합니다.

```text
https://runfor.kr/
```

주요 처리 흐름:

```text
create_driver()
    ↓
Selenium으로 대회 목록 로드
    ↓
더보기 버튼 반복 클릭
    ↓
대회 상세 URL 수집
    ↓
requests + BeautifulSoup 상세 페이지 요청
    ↓
상세 정보 파싱
    ↓
DataFrame 생성
    ↓
RAW CSV 저장
    ↓
저장 결과 검증
```

주요 수집 항목:

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

로컬 저장 예:

```text
data/raw/260910_090000/
└─ marathon_schedule_raw_260910_090000.csv
```

AWS Lambda에서는 동일한 파일을 `/tmp/data/raw/{batch_id}/`에 생성한 뒤 S3 `raw/{batch_id}/` 영역에 업로드합니다.

---

### 4.3 `transform.py`

RAW CSV를 읽고 서비스에서 사용하기 적합한 형태로 전처리합니다.

주요 처리:

```text
RAW CSV 읽기
    ↓
문자열 / 결측값 정리
    ↓
지역 표준화
    ↓
장소 문자열 정리
    ↓
코스 구분자 통일
    ↓
대회 날짜 변환
    ↓
접수기간 시작일 / 종료일 분리
    ↓
집결시간 표준화
    ↓
전화번호 / 이메일 형식 검증
    ↓
메타데이터 추가
    ↓
최종 컬럼 검증
    ↓
Processed CSV 저장
```

#### 지역 표준화

세부 지역은 RUNTRACK에서 사용하는 8개 권역으로 표준화합니다.

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

```text
여의도 한강공원 (예정)
→ 여의도 한강공원
```

#### 코스 구분자 통일

```text
10km / Half
→ 10km|Half
```

#### 날짜 변환

```text
2026년 10월 11일
→ 2026-10-11
```

#### 접수기간 분리

```text
2026-07-01 ~ 2026-09-30
```

변환:

```text
registration_start_date = 2026-07-01
registration_end_date   = 2026-09-30
```

#### 집결시간 표준화

```text
오전 8시
→ 08:00
```

전처리 완료 후 주요 검증 항목:

```text
최종 컬럼 순서
허용되지 않은 지역값
장소 문자열 정리 여부
코스 구분자 변환 여부
집결시간 형식
전화번호 형식
이메일 형식
```

로컬 저장 예:

```text
data/processed/
└─ marathon_schedule_processed_260910_090000.csv
```

AWS에서는 Transform Lambda가 결과를 다음 S3 Key로 업로드합니다.

```text
processed/{batch_id}/marathon_schedule_processed_{batch_id}.csv
```

---

### 4.4 `database.py`

MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당합니다.

주요 함수:

```text
load_database_config()
load_database_config_from_secret()
create_mysql_engine()
test_mysql_connection()
```

실행 환경에 따라 DB 연결 정보를 다르게 구성합니다.

로컬:

```text
.env
├─ DB_HOST
├─ DB_PORT
├─ DB_NAME
├─ DB_USER
└─ DB_PASSWORD
```

AWS Lambda:

```text
Lambda Environment
├─ DB_HOST
├─ DB_PORT
├─ DB_NAME
└─ DB_SECRET_ARN
        ↓
AWS Secrets Manager
├─ username
└─ password
```

DB 연결 책임을 `load.py`와 분리하여 로컬 MySQL과 Amazon RDS에서 같은 Load 로직을 재사용할 수 있도록 구성합니다.

---

### 4.5 `load.py`

Processed CSV를 검증한 뒤 서비스 DB 스키마에 맞춰 MySQL에 적재합니다.

주요 처리:

```text
Processed CSV 입력
    ↓
필수 컬럼 / 필수값 검증
    ↓
중복 데이터 검증
    ↓
지역 코드 및 DB 컬럼 변환
    ↓
MySQL 연결
    ↓
테이블 생성
    ↓
marathon_schedule INSERT / UPDATE
    ↓
course UPSERT
    ↓
schedule_course 관계 저장
    ↓
DB 적재 결과 검증
```

중복 판별 기준:

```text
title + race_date + location
```

Processed 데이터의 일부 컬럼은 DB 스키마에 맞춰 변환합니다.

| Processed CSV | MySQL |
|---|---|
| `location` | `event_field` |
| `race_date` | `event_date` |
| `registration_start_date` | `register_start_date` |
| `registration_end_date` | `register_end_date` |
| `phone` | `event_inquiry_phone` |
| `email` | `event_inquiry_email` |

`race_status`, `organizer`는 Processed CSV에는 유지되지만 현재 DB 적재 레코드에서는 사용하지 않습니다.

---

### 4.6 `s3_storage.py`

AWS Lambda에서 사용하는 S3 입출력 책임을 담당합니다.

주요 기능:

```text
upload_raw_csv()
    Extract 결과 RAW CSV → S3 raw 영역

download_raw_csv()
    S3 raw CSV → Transform Lambda /tmp

upload_processed_file()
    Transform 결과 CSV → S3 processed 영역

download_processed_file()
    S3 processed CSV → Load Lambda /tmp
```

Lambda Handler는 S3 입출력을 직접 구현하지 않고 `s3_storage.py`를 사용합니다.

---

## 5. Lambda Handler

### 5.1 `extract_handler.py`

Extract Lambda의 실행 진입점입니다.

Extract 단계는 최초 실행에 별도 입력 파라미터가 필요하지 않습니다.

처리 흐름:

```text
Lambda 시작
    ↓
DATA_BUCKET_NAME 확인
    ↓
run_extract(headless=True)
    ↓
/tmp/data/raw/{batch_id}/RAW CSV
    ↓
upload_raw_csv()
    ↓
S3 raw/{batch_id}/
```

반환 데이터는 다음 Transform Lambda가 처리할 배치를 식별하는 메타데이터를 포함합니다.

```json
{
  "stage": "extract",
  "status": "SUCCEEDED",
  "batch_id": "260910_090000",
  "bucket": "<data-bucket-name>",
  "raw_prefix": "raw/260910_090000/",
  "raw_key": "raw/260910_090000/marathon_schedule_raw_260910_090000.csv",
  "request_id": "..."
}
```

Extract Lambda는 Selenium과 Chromium이 필요하므로 ZIP 패키지가 아닌 Lambda Container Image로 배포합니다.

---

### 5.2 `transform_handler.py`

Transform Lambda의 실행 진입점입니다.

입력 Event 예:

```json
{
  "batch_id": "260910_090000",
  "bucket": "<data-bucket-name>",
  "raw_prefix": "raw/260910_090000/"
}
```

처리 흐름:

```text
Lambda Event
    ↓
batch_id / bucket / raw_prefix 검증
    ↓
S3 RAW CSV 다운로드
    ↓
/tmp/data/raw/{batch_id}/
    ↓
run_transform()
    ↓
Processed CSV 생성
    ↓
S3 processed/{batch_id}/ 업로드
```

반환 예:

```json
{
  "stage": "transform",
  "status": "SUCCEEDED",
  "batch_id": "260910_090000",
  "bucket": "<data-bucket-name>",
  "raw_prefix": "raw/260910_090000/",
  "processed_prefix": "processed/260910_090000/",
  "processed_key": "processed/260910_090000/marathon_schedule_processed_260910_090000.csv",
  "request_id": "..."
}
```

`processed_key`는 Load Lambda가 처리할 Processed CSV를 정확하게 지정하는 값입니다.

---

### 5.3 `load_handler.py`

Load Lambda의 실행 진입점입니다.

입력 Event 예:

```json
{
  "batch_id": "260910_090000",
  "bucket": "<data-bucket-name>",
  "processed_key": "processed/260910_090000/marathon_schedule_processed_260910_090000.csv"
}
```

처리 흐름:

```text
Lambda Event
    ↓
batch_id / bucket / processed_key 검증
    ↓
S3 Processed CSV 다운로드
    ↓
/tmp/data/processed/
    ↓
run_load()
    ↓
Secrets Manager 자격 증명 조회
    ↓
Amazon RDS MySQL 연결
    ↓
테이블 생성 / 데이터 적재
    ↓
DB 적재 결과 검증
```

Load Lambda는 RDS와 동일한 네트워크에 연결되며, `DB_SECRET_ARN`을 이용해 Secrets Manager에서 DB 사용자 이름과 비밀번호를 조회합니다.

---

## 6. S3 데이터 구조

AWS 파이프라인의 DataBucket은 다음 Object Key 구조를 사용합니다.

```text
DataBucket
│
├─ raw/
│  └─ {batch_id}/
│     └─ marathon_schedule_raw_{batch_id}.csv
│
└─ processed/
   └─ {batch_id}/
      └─ marathon_schedule_processed_{batch_id}.csv
```

예:

```text
raw/260910_090000/
└─ marathon_schedule_raw_260910_090000.csv

processed/260910_090000/
└─ marathon_schedule_processed_260910_090000.csv
```

S3 콘솔에서 보이는 `raw/`, `processed/`는 실제 파일시스템 디렉터리가 아니라 Object Key Prefix입니다.

---

## 7. 배치 관리

한 번의 수집 실행은 하나의 `batch_id`로 관리합니다.

형식:

```text
YYMMDD_HHMMSS
```

예:

```text
260910_090000
```

동일한 배치 ID를 RAW와 Processed 경로에 사용합니다.

```text
raw/260910_090000/
processed/260910_090000/
```

이 구조를 통해 하나의 수집 작업이 Extract, Transform, Load 단계에서 어떻게 처리되었는지 추적할 수 있습니다.

파일명에도 동일한 배치 ID를 포함합니다.

```text
marathon_schedule_raw_260910_090000.csv
marathon_schedule_processed_260910_090000.csv
```

---

## 8. MySQL 저장 구조

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

동일한 대회가 없으면 INSERT하고 기존 데이터가 존재하면 UPDATE합니다.

### `course`

마라톤 코스 정보를 중복 없이 관리합니다.

```text
course_id
course_name
create_date
update_date
```

`course_name`에는 UNIQUE 제약조건을 적용하여 같은 코스의 중복 저장을 방지합니다.

### `schedule_course`

마라톤 일정과 코스의 다대다 관계를 저장하는 연결 테이블입니다.

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

관계:

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

## 9. AWS SAM 구성

AWS 리소스는 프로젝트 루트의 `template.yaml`에서 정의합니다.

현재 주요 리소스:

```text
Resources
├─ DataBucket
├─ ExtractFunction
├─ TransformFunction
├─ LoadFunction
├─ PipelineStateMachine
├─ PipelineSchedulerRole
└─ PipelineSchedule
```

계정 및 환경마다 달라지는 값은 SAM Parameter로 외부에서 전달합니다.

```text
DbHost
DbPort
DbName
DbSecretArn
LoadSubnetId
LoadSecurityGroupId
ScheduleEnabled
ScheduleExpression
```

---

### `DataBucket`

RAW와 Processed CSV를 저장하는 파이프라인 데이터 Bucket입니다.

CloudFormation이 Bucket을 생성하며 Lambda는 `!Ref DataBucket`을 통해 실제 Bucket 이름을 전달받거나, 앞 단계의 반환 Payload를 통해 Bucket 정보를 전달합니다.

---

### `ExtractFunction`

```text
FunctionName: runtrack-pipeline-extract
PackageType: Image
Architecture: x86_64
Memory: 2048 MB
Timeout: 900 sec
EphemeralStorage: 1024 MB
DATA_DIR: /tmp/data
```

Container Image 내부에 Chromium과 ChromeDriver를 포함합니다.

```text
CHROMIUM_BINARY=/usr/local/bin/chromium
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
```

RAW CSV를 DataBucket에 저장하기 위해 S3 쓰기 권한을 사용합니다.

---

### `TransformFunction`

```text
FunctionName: runtrack-pipeline-transform
Runtime: Python 3.13
Architecture: x86_64
Memory: 512 MB
Timeout: 60 sec
DATA_DIR: /tmp/data
```

RAW CSV 다운로드와 Processed CSV 업로드를 위해 S3 읽기/쓰기 권한을 사용합니다.

---

### `LoadFunction`

```text
FunctionName: runtrack-pipeline-load
Runtime: Python 3.13
Architecture: x86_64
Memory: 512 MB
Timeout: 120 sec
DATA_DIR: /tmp/data

DB_HOST=<RDS Endpoint>
DB_PORT=3306
DB_NAME=<Database Name>
DB_SECRET_ARN=<RDS Managed Secret ARN>
```

주요 권한 및 설정:

```text
S3ReadPolicy
→ Processed CSV 다운로드

secretsmanager:GetSecretValue
→ RDS 관리형 Secret 조회

AWSLambdaVPCAccessExecutionRole
→ VPC 연결에 필요한 ENI 관리

VpcConfig
→ 기존 RDS 네트워크의 Subnet / Security Group 사용
```

RDS, Subnet, Security Group 자체는 이 템플릿에서 새로 생성하지 않고 외부에서 전달한 Parameter를 사용하여 연결합니다.

---

### `PipelineStateMachine`

Extract, Transform, Load Lambda를 순차 실행하는 Step Functions 상태 머신입니다.

```text
Start
  ↓
Extract
  ↓
Transform
  ↓
Load
  ↓
End
```

각 Task는 Lambda를 동기 호출합니다.

```text
Resource
→ arn:aws:states:::lambda:invoke

Payload.$: $
→ 현재 State 전체 입력을 Lambda Event로 전달

OutputPath: $.Payload
→ Lambda Invoke 응답 중 실제 Payload만 다음 State로 전달
```

상태 머신 실행 역할에는 세 Lambda를 호출할 수 있는 `LambdaInvokePolicy`가 부여됩니다.

상태 머신 이름:

```text
runtrack-pipeline-state-machine
```

---

### `PipelineSchedulerRole`

EventBridge Scheduler가 Step Functions 상태 머신을 실행할 때 사용하는 IAM Role입니다.

```text
scheduler.amazonaws.com
        ↓
sts:AssumeRole
        ↓
states:StartExecution
        ↓
runtrack-pipeline-state-machine
```

---

### `PipelineSchedule`

EventBridge Scheduler는 정해진 시간 또는 주기에 상태 머신 실행을 시작합니다.

Scheduler 이름:

```text
runtrack-pipeline-schedule
```

주요 설정:

```text
Target
→ runtrack-pipeline-state-machine

Target API
→ states:StartExecution

Timezone
→ Asia/Seoul

Initial Input
→ {}
```

Extract Lambda에는 최초 입력 파라미터가 필요하지 않으므로 Scheduler가 Step Functions에 전달하는 초기 Input은 빈 JSON 객체입니다.

Scheduler 상태는 다음 Parameter로 제어합니다.

```text
ScheduleEnabled=true
→ ENABLED

ScheduleEnabled=false
→ DISABLED
```

현재 템플릿의 기본 Scheduler 표현식:

```text
cron(30 2 * * ? *)
```

`ScheduleExpressionTimezone`이 `Asia/Seoul`이므로 기본값은 한국 시간 기준 매일 02:30 실행을 의미합니다.

---

## 10. Step Functions 오케스트레이션

상태 머신의 최초 입력:

```json
{}
```

메타데이터 전달 흐름:

```text
Step Functions 최초 입력
{}
        ↓
Extract Lambda
        ↓
{
  batch_id,
  bucket,
  raw_prefix,
  raw_key
}
        ↓
Transform Lambda
        ↓
{
  batch_id,
  bucket,
  processed_prefix,
  processed_key
}
        ↓
Load Lambda
        ↓
{
  stage,
  status,
  batch_id,
  load_summary
}
```

Step Functions는 CSV 자체가 아니라 다음 단계가 필요한 S3 위치 정보와 배치 메타데이터를 전달합니다.

AWS Console에서는 각 상태의 Input과 Output을 확인하여 `batch_id`, `bucket`, `raw_prefix`, `processed_key`가 올바르게 이어지는지 검증할 수 있습니다.

---

## 11. EventBridge Scheduler 자동 실행

전체 자동 실행 흐름:

```text
EventBridge Scheduler
        ↓
states:StartExecution
        ↓
Step Functions
        ↓
Extract Lambda
        ↓
S3 Raw
        ↓
Transform Lambda
        ↓
S3 Processed
        ↓
Load Lambda
        ↓
Amazon RDS MySQL
```

Scheduler 설정 확인 항목:

```text
Name
→ runtrack-pipeline-schedule

Target
→ runtrack-pipeline-state-machine

Timezone
→ Asia/Seoul

Input
→ {}

State
→ ScheduleEnabled Parameter에 따라 ENABLED / DISABLED
```

자동 실행을 활성화하기 전 Step Functions를 수동 실행하여 전체 파이프라인 연결을 먼저 확인하는 것이 안전합니다.

---

## 12. Amazon RDS 및 네트워크 구성

Load Lambda는 Amazon RDS MySQL에 접근하기 위해 RDS가 위치한 기존 VPC의 Subnet과 Security Group 설정을 사용합니다.

```text
                         Existing VPC
        ┌──────────────────────────────────────┐
        │ Load Lambda                          │
        │        │                             │
        │        ├── TCP 3306 ─────────→ RDS   │
        │        │                             │
        │        ├── S3 Gateway Endpoint ──────┼──→ Amazon S3
        │        │                             │
        │        └── HTTPS 443                 │
        │                 ↓                    │
        │          Secrets Manager             │
        │          Interface Endpoint          │
        └──────────────────────────────────────┘
```

권장 구성:

```text
RDS Public Access
→ No

RDS Security Group
→ TCP 3306
→ Source: Load Lambda Security Group

S3 접근
→ Gateway VPC Endpoint

Secrets Manager 접근
→ Interface VPC Endpoint
→ HTTPS 443
```

RDS 마스터 자격 증명은 AWS Secrets Manager에서 관리하고 Lambda 코드에 사용자 이름과 비밀번호를 직접 작성하지 않습니다.

---

## 13. SAM 관리 S3와 DataBucket의 차이

SAM 배포 이후 AWS 계정에는 서로 다른 목적의 S3 Bucket이 존재할 수 있습니다.

SAM CLI 관리 Bucket:

```text
로컬 소스
    ↓
sam build
    ↓
Lambda 배포 아티팩트
    ↓
SAM CLI 관리 S3 Bucket
    ↓
CloudFormation
    ↓
AWS 리소스 배포
```

이 Bucket은 애플리케이션 데이터가 아니라 배포 아티팩트를 저장하기 위한 용도입니다.

반면 `DataBucket`은 RUNTRACK 파이프라인 데이터 저장용입니다.

```text
Extract Lambda
    ↓
DataBucket/raw/
    ↓
Transform Lambda
    ↓
DataBucket/processed/
    ↓
Load Lambda
    ↓
Amazon RDS MySQL
```

두 Bucket은 목적이 다르므로 구분하여 관리합니다.

---

## 14. 환경 구성

### 14.1 가상환경 생성

프로젝트 루트에서:

```bash
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
source .venv/Scripts/activate
```

---

### 14.2 실행 패키지 설치

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

주요 실행 의존성:

```text
requests
pandas
beautifulsoup4
selenium
python-dotenv
SQLAlchemy
PyMySQL
```

---

### 14.3 개발 및 테스트 패키지 설치

```bash
python -m pip install -r requirements-dev.txt
```

개발 의존성:

```text
pytest
ruff
```

---

### 14.4 `.env` 설정

로컬 MySQL 실행 시 `.env.example`을 참고하여 `.env`를 작성합니다.

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=runtrack
DB_USER=root
DB_PASSWORD="MySQL 비밀번호"
```

`.env`에는 민감한 값이 포함될 수 있으므로 Git에 커밋하지 않습니다.

AWS Lambda에서는 `DB_USER`, `DB_PASSWORD`를 직접 환경변수로 전달하지 않고 Secrets Manager를 사용합니다.

---

## 15. 로컬 파이프라인 실행

프로젝트 루트에서:

```bash
python main.py
```

실행 흐름:

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
    run_load,
    run_transform,
)

raw_csv_file = run_extract()

processed_csv_file = run_transform(
    raw_csv_file=raw_csv_file,
)

load_summary = run_load(
    processed_csv_file=processed_csv_file,
)
```

---

## 16. 테스트와 코드 품질 검사

### pytest

전체 테스트:

```bash
python -m pytest -v
```

주요 검증 대상:

```text
Extract 데이터 수집 및 파일 경로
Transform 전처리 / 형식 변환 / 데이터 검증
Extract Lambda Handler
Transform Lambda Handler
Load Lambda Handler
S3 Raw / Processed 입출력
로컬 .env 및 Secrets Manager 기반 DB 설정
```

AWS를 직접 호출하지 않아도 되는 단위 테스트는 Mock을 사용하여 외부 의존성을 분리합니다.

### Ruff

```bash
python -m ruff check .
```

`pyproject.toml`을 기준으로 Python 문법, import 정렬, 미사용 코드, timezone 관련 규칙 등을 검사합니다.

---

## 17. GitHub Actions CI

Workflow 위치:

```text
.github/workflows/ci.yml
```

CI 실행 조건:

```text
main branch push
또는
main branch 대상 pull_request
```

주요 흐름:

```text
GitHub Push / Pull Request
        ↓
Checkout Repository
        ↓
Python 환경 설정
        ↓
requirements-dev.txt 설치
        ↓
Ruff 검사
        ↓
pytest 실행
        ↓
CI 성공 / 실패
```

현재 CI는 코드 품질 검사와 테스트를 담당하며 AWS 배포는 SAM CLI를 이용해 수행합니다.

---

## 18. AWS SAM 빌드 및 배포

프로젝트 또는 `template.yaml`을 수정한 뒤 다음 순서로 검증합니다.

```powershell
python -m ruff check .
python -m pytest -v
sam validate --lint
sam build
sam deploy
```

역할:

```text
sam validate --lint
→ SAM / CloudFormation Template 문법과 구조 검증

sam build
→ Lambda 코드와 의존성 및 Container Image 빌드

sam deploy
→ 배포 아티팩트 업로드
→ CloudFormation Stack 생성 또는 업데이트
→ Lambda / S3 / Step Functions / Scheduler 관련 리소스 반영
```

현재 Stack 이름:

```text
runtrack-pipeline
```

현재 Region:

```text
ap-northeast-2
```

Load Lambda와 Scheduler에 필요한 환경별 값은 SAM Parameter로 전달합니다.

---

## 19. Lambda 원격 호출

`sam remote invoke`는 로컬 소스를 직접 실행하는 명령이 아니라 AWS에 배포된 Lambda를 원격 호출하는 명령입니다.

### 19.1 Extract Lambda

Extract는 별도 Event 파라미터가 필요하지 않습니다.

```powershell
sam remote invoke ExtractFunction `
  --stack-name runtrack-pipeline `
  --profile student9
```

정상 실행 시 S3에서 다음 Prefix를 확인합니다.

```text
raw/{batch_id}/
```

---

### 19.2 Transform Lambda

`events/transform-event.json`은 직전 Extract 결과의 실제 `batch_id`, Bucket, Raw Prefix를 기준으로 작성합니다.

```json
{
  "batch_id": "<actual-batch-id>",
  "bucket": "<actual-data-bucket-name>",
  "raw_prefix": "raw/<actual-batch-id>/"
}
```

호출:

```powershell
sam remote invoke TransformFunction `
  --stack-name runtrack-pipeline `
  --event-file .\events\transform-event.json `
  --profile student9
```

정상 실행 후:

```text
processed/{batch_id}/
```

를 확인합니다.

---

### 19.3 Load Lambda

`events/load-event.json`은 직전 Transform 결과의 실제 `processed_key`를 기준으로 작성합니다.

```json
{
  "batch_id": "<actual-batch-id>",
  "bucket": "<actual-data-bucket-name>",
  "processed_key": "processed/<actual-batch-id>/marathon_schedule_processed_<actual-batch-id>.csv"
}
```

호출:

```powershell
sam remote invoke LoadFunction `
  --stack-name runtrack-pipeline `
  --event-file .\events\load-event.json `
  --profile student9
```

정상 실행 시 Load 결과와 RDS 적재 결과를 확인합니다.

---

## 20. Step Functions 실행

상태 머신 이름:

```text
runtrack-pipeline-state-machine
```

최초 입력:

```json
{}
```

정상 실행 흐름:

```text
Start
  ↓
Extract   ✅
  ↓
Transform ✅
  ↓
Load      ✅
  ↓
End
```

AWS Console에서는 각 상태의 입력과 출력에서 다음 메타데이터가 이어지는지 확인합니다.

```text
batch_id
bucket
raw_prefix
processed_prefix
processed_key
```

CLI로 실행할 경우 예:

```powershell
$stateMachineArn = aws stepfunctions list-state-machines `
  --region ap-northeast-2 `
  --profile student9 `
  --query "stateMachines[?name=='runtrack-pipeline-state-machine'].stateMachineArn | [0]" `
  --output text

aws stepfunctions start-execution `
  --state-machine-arn $stateMachineArn `
  --input "{}" `
  --region ap-northeast-2 `
  --profile student9
```

---

## 21. Lambda `/var/task`와 `/tmp`

Lambda 실행 환경에서 주요 경로의 역할은 다음과 같습니다.

```text
/var/task
→ 배포된 Lambda 코드와 패키지가 위치하는 실행 기준 경로

/tmp
→ Lambda 실행 중 파일을 임시 저장할 수 있는 쓰기 가능한 영역
```

RUNTRACK Lambda는:

```text
DATA_DIR=/tmp/data
```

를 사용합니다.

각 Lambda의 `/tmp`는 서로 공유되지 않습니다.

```text
Extract Lambda /tmp
        ↓
Amazon S3
        ↓
Transform Lambda /tmp
        ↓
Amazon S3
        ↓
Load Lambda /tmp
```

따라서 단계 간 파일 전달은 S3를 이용합니다.

---

## 22. Git 관리 정책

프로젝트 파일은 기본적으로 Git에서 추적하고 로컬 환경, 민감정보, 실행 산출물, 캐시 등을 제외합니다.

주요 제외 대상:

```text
.env
.env.*
data/
logs/
*.log

__pycache__/
.pytest_cache/
.ruff_cache/

.venv/
venv/

.vscode/
.idea/

build/
dist/
.aws-sam/
samconfig.toml
```

`.env.example`, `Dockerfile.extract`, `.dockerignore`, `requirements-extract.txt`, `template.yaml`은 재현 가능한 개발 및 배포 구성을 위해 Git에서 관리합니다.

---

## 23. 현재 구현 범위

```text
[Local Pipeline]
runfor.kr
→ Extract
→ RAW CSV
→ Transform
→ Processed CSV
→ Load
→ MySQL

[Code Quality / CI]
pytest
→ Ruff
→ GitHub Actions CI

[AWS Infrastructure as Code]
AWS SAM
→ CloudFormation
→ S3 DataBucket
→ Extract Lambda Container Image
→ Transform Lambda
→ Load Lambda
→ Step Functions
→ EventBridge Scheduler

[AWS Data Pipeline]
EventBridge Scheduler
→ Step Functions
→ Extract Lambda
→ S3 Raw
→ Transform Lambda
→ S3 Processed
→ Load Lambda
→ Amazon RDS MySQL

[Security / Network]
Secrets Manager 기반 RDS 자격 증명 조회
→ Load Lambda VPC 연결
→ RDS Security Group
→ S3 Gateway VPC Endpoint
→ Secrets Manager Interface VPC Endpoint
```

Scheduler는 `ScheduleEnabled` Parameter를 통해 활성화 또는 비활성화할 수 있습니다.

---

## 24. 설계 원칙

- 웹에서 수집한 원본 데이터는 RAW 영역에 별도로 보관합니다.
- 한 번의 수집 실행을 하나의 `batch_id`로 관리합니다.
- RAW CSV와 Processed CSV를 분리합니다.
- 단계 간 대용량 데이터는 S3에 저장합니다.
- Lambda 간에는 파일 자체가 아니라 `batch_id`, `bucket`, `prefix`, `object key`를 전달합니다.
- Lambda의 `/tmp`는 해당 실행의 임시 작업 공간으로만 사용합니다.
- 각 Lambda Handler는 실행 제어와 외부 입출력 연결에 집중합니다.
- 실제 데이터 처리 로직은 `src/data_collection_pipeline/`의 모듈을 재사용합니다.
- 공통 애플리케이션 설정은 `config.py`에서 관리합니다.
- S3 입출력 책임은 `s3_storage.py`로 분리합니다.
- 데이터베이스 연결 책임은 `database.py`로 분리합니다.
- 로컬에서는 `.env`, AWS Lambda에서는 Secrets Manager를 이용해 DB 자격 증명을 관리합니다.
- Amazon RDS는 Load Lambda가 접근할 수 있는 VPC 및 Security Group 규칙을 사용합니다.
- Step Functions는 ETL 실행 순서와 단계 간 메타데이터 전달을 담당합니다.
- EventBridge Scheduler는 상태 머신 실행 시작 시점을 담당합니다.
- 테스트에서는 외부 네트워크, AWS, DB 의존성을 가능한 한 Mock으로 분리합니다.
- 로컬과 CI에서 동일한 Ruff와 pytest 명령을 사용합니다.
- AWS 리소스는 `template.yaml`을 기준으로 재현 가능하게 관리합니다.

---

## 25. 전체 파이프라인 요약

```text
[Scheduler]
EventBridge Scheduler
        ↓

[Orchestration]
AWS Step Functions
        ↓

[Extract]
runfor.kr
        ↓
Selenium으로 동적 대회 목록 로드
        ↓
requests + BeautifulSoup으로 상세 정보 수집
        ↓
RAW CSV
        ↓
Amazon S3 raw/{batch_id}/
        ↓

[Transform]
RAW CSV 다운로드
        ↓
문자열 / 지역 / 날짜 / 시간 / 연락처 표준화
        ↓
Processed CSV
        ↓
Amazon S3 processed/{batch_id}/
        ↓

[Load]
Processed CSV 다운로드
        ↓
Secrets Manager
        ↓
Amazon RDS MySQL
        ↓
marathon_schedule
course
schedule_course
        ↓
DB 적재 결과 검증
```

전체 ETL 흐름:

```text
Extract → Transform → Load
```

AWS 자동 실행 흐름:

```text
EventBridge Scheduler
→ Step Functions
→ Extract Lambda
→ S3 Raw
→ Transform Lambda
→ S3 Processed
→ Load Lambda
→ Amazon RDS MySQL
```
