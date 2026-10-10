# 나만의 용돈 기입장 (budget_app)

파일(JSONL)에 데이터를 영구 저장하는 **콘솔 가계부**입니다.
수입·지출 기록, 검색, 월별 요약, 예산 경고, 카테고리 관리, CSV 가져오기/내보내기를 지원합니다.

- Python 3.10 이상 (3.10 / 3.11 / 3.14에서 테스트 통과)
- **표준 라이브러리만 사용** — `pip install` 필요 없음

---

## 1. 실행 방법

프로젝트 폴더(`B2-1/`)에서 실행합니다.

```bash
python -m budget_app <command> [options]

python -m budget_app --help          # 전체 명령 목록
python -m budget_app add --help      # 명령별 사용법 (모든 명령·하위 명령 지원)
```

- 옵션은 모두 `--` 표기로 통일했습니다. (`-h` 없이 `--help`만 사용)
- 옵션은 **명령 뒤에** 씁니다. 예: `python -m budget_app list --limit 5`
- macOS에서 `python`이 없으면 `python3`로 실행하세요.

## 2. 폴더 구조와 계층

```
B2-1/
├── budget_app/          프로그램 코드
│   ├── __main__.py      실행 입구 (python -m budget_app)
│   ├── cli.py           ① CLI: 명령어 해석 → 입력 검사 → 서비스 호출 → 출력
│   ├── prompts.py          대화형 입력 (틀리면 다시 묻기)
│   ├── formatter.py        출력 모양 (표 정렬)
│   ├── services.py      ② 서비스: 기능 규칙
│   ├── storage.py       ③ 저장소: 파일 읽기/쓰기 (JSONL, CSV)
│   ├── models.py        ④ 모델: 데이터 모양 (dataclass)
│   ├── validators.py       입력 검증
│   ├── decorators.py       공통 기능 (오류 처리, 실행 로그·시간)
│   └── errors.py           "원인 + 힌트" 오류 클래스
├── tests/               자동 테스트 (97개)
├── samples/             import 연습용 CSV
├── scripts/             10만 건 실측 스크립트
├── docs/                설계 문서
└── data/                실행하면 자동 생성 (저장 파일)
```

| 계층 | 파일 | 하는 일 | 안 하는 일 |
| --- | --- | --- | --- |
| ① CLI | `cli.py`, `prompts.py`, `formatter.py` | 사람과 대화: 명령 해석, 입력, 출력 | 계산, 파일 접근 |
| ② 서비스 | `services.py` (`BudgetService`) | 규칙: 카테고리 확인, id 발급, 검색·요약, 삭제 막기 | 입력 받기, 파일 형식 다루기 |
| ③ 저장소 | `storage.py` (`TransactionRepository`, `CategoryStore`, `BudgetStore`, `RecurringStore`) | 파일 읽기/쓰기 | 규칙 판단 |
| ④ 모델 | `models.py` (`Transaction` 등) | 데이터 모양 정의 | 저장, 계산, 출력 |

호출 방향은 **위 → 아래 한 방향**입니다. 예를 들어 `add` 명령 하나는 이렇게 지나갑니다.

```
__main__.py → cli.py(명령 해석) → prompts.py(질문) → validators.py(검사)
           → services.py(카테고리 확인, id 발급) → storage.py(파일 끝에 한 줄 추가)
           → cli.py([저장 완료] id 출력)
```

코드 안에는 `# [요구 4.6]`처럼 **미션 요구사항 번호**를 주석으로 표시해 두었습니다.

## 3. 저장 파일 위치와 형식

- 기본 위치: `./data/` (실행한 폴더 기준)
- 다른 폴더를 쓰려면: `--data-dir <폴더>` (예: `python -m budget_app list --data-dir mydata`)
- 형식: **JSONL** (한 줄 = JSON 하나 = 데이터 1건, UTF-8)

| 파일 | 내용 | 한 줄 예시 |
| --- | --- | --- |
| `transactions.jsonl` | 거래 | `{"id": "TX-000001", "type": "expense", "date": "2024-01-15", "amount": 15000, "category": "food", "memo": "점심", "tags": ["meal"]}` |
| `categories.jsonl` | 카테고리 | `{"name": "food"}` |
| `budgets.jsonl` | 월 예산 | `{"month": "2024-01", "amount": 500000}` |
| `recurring.jsonl` | 반복 규칙 (보너스) | `{"id": "RC-001", "type": "income", "day": 25, "amount": 3000000, "category": "salary", "memo": "월급", "tags": [], "applied_months": ["2024-01"]}` |
| `app.log` | 실행 로그 | `2024-01-15 12:00:00,123 command=cmd_add exit_code=0 elapsed=0.001s` |
| `backups/<날짜-시간>/` | 백업 (보너스) | 위 4개 `.jsonl` 파일의 복사본 |

**초기 실행 동작 (안 A)**
- 폴더나 파일이 없으면 **자동으로 만듭니다.**
- 카테고리가 비어 있으면 **기본 카테고리를 자동 생성**하고 안내 메시지를 출력합니다.
  ```
  [안내] 카테고리가 비어 있어 기본 카테고리를 만들었습니다: food, transport, rent, salary, etc
  ```

## 4. 명령 요약

| 명령 | 입력 방식 | 예시 |
| --- | --- | --- |
| `add` | 대화형 | `add` |
| `list` | 옵션 | `list --limit 5` (기본 10건) |
| `search` | 옵션 | `search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal` |
| `summary` | 옵션 | `summary --month 2024-01 --top 3` (기본 TOP 3) |
| `update` | **옵션 (고정)** | `update --id TX-000001 --amount 20000 --memo 저녁` |
| `delete` | 옵션 | `delete --id TX-000001` |
| `budget set` / `budget list` | 옵션 | `budget set --month 2024-01 --amount 500000` |
| `category add` / `list` / `remove` | 대화형 또는 `--name` | `category add`, `category remove --name hobby` |
| `import` | 옵션 | `import --from samples/import_ok.csv` (`--strict` 선택) |
| `export` | 옵션 | `export --out export.csv --month 2024-01` |
| `backup` (보너스) | - | `backup` |
| `recurring add` / `list` / `remove` / `apply` (보너스) | 대화형 / 옵션 | `recurring apply --month 2024-02` |

## 5. 주요 명령 실행 예시

**거래 추가 (대화형)** — 틀리면 그 항목만 다시 묻습니다.
```
$ python -m budget_app add
날짜(YYYY-MM-DD): 2024-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심 김밥
태그(쉼표로 구분, 없으면 엔터): meal,friend
[저장 완료] id=TX-000001
```

**목록 (최신순)**
```
$ python -m budget_app list --limit 3
ID        | 날짜       | 타입    | 카테고리  |    금액 | 메모      | 태그
----------+------------+---------+-----------+---------+-----------+------------
TX-000001 | 2024-01-15 | expense | food      |   15000 | 점심 김밥 | meal,friend
TX-000002 | 2024-01-14 | income  | salary    | 3000000 | 1월 월급  |
TX-000003 | 2024-01-12 | expense | transport |   20000 |           |
... 최신 3건만 표시했습니다. 더 보려면 --limit 값을 늘리세요.
```
- **최신순 기준**: 날짜가 늦은 순, 같은 날짜면 나중에 추가한(id 번호가 큰) 거래가 먼저입니다.

**예산 + 월별 요약**
```
$ python -m budget_app budget set --month 2024-01 --amount 150000
[저장 완료] 2024-01 예산 150000원

$ python -m budget_app summary --month 2024-01 --top 3
[2024-01 월별 요약]
총 수입: 3000000원
총 지출: 185000원
잔액: 2815000원
예산: 150000원 (사용률 123.3%)
[경고] 예산을 35000원 초과했습니다!

지출 TOP 3
1) rent 150000원
2) transport 20000원
3) food 15000원
```
- 거래가 없는 달은 `데이터 없음`을 출력합니다.

**카테고리**
```
$ python -m budget_app category add
카테고리명: hobby
[저장 완료] category=hobby

$ python -m budget_app category remove --name food
[오류] 'food' 카테고리를 사용하는 거래가 1건 있어 삭제할 수 없습니다.
[힌트] search --category food 로 거래를 찾고, update --id <id> --category <다른 카테고리> 로 바꾼 뒤 다시 삭제하세요.
```
- **사용 중인 카테고리는 삭제를 막습니다.** 거래나 반복 규칙이 없는 카테고리를 가리키는 일(고아 데이터)을 막기 위해서입니다.

## 6. update 방식: 옵션 방식으로 고정

`update`는 **옵션 방식(안 A)**으로 고정했습니다. 준 옵션의 항목만 바뀌고 나머지는 그대로입니다.

```bash
python -m budget_app update --id <id> [--date YYYY-MM-DD] [--type income|expense] \
       [--category 이름] [--amount 금액] [--memo 메모] [--tags 태그1,태그2]
```

- 없는 id → `[오류] 없는 데이터입니다` (종료 코드 1)
- 바꿀 옵션을 하나도 안 주면 → `[오류] 수정할 항목이 없습니다`
- `--memo ""`, `--tags ""` 처럼 빈 값을 주면 메모·태그를 지웁니다.

**update/delete 안전성 (원자적 저장)**: 원본을 한 줄씩 읽어 **임시 파일**(`transactions.jsonl.tmp`)에 쓰고, 끝까지 다 썼을 때만 `os.replace()`로 **한 번에 교체**합니다. 쓰는 도중 오류가 나거나 프로그램이 꺼져도 원본 파일은 그대로 남습니다.

## 7. import / export CSV 스키마

| column | required | 설명 |
| --- | --- | --- |
| `date` | Y | `YYYY-MM-DD` |
| `type` | Y | `income` / `expense` |
| `category` | Y | 등록된 카테고리 |
| `amount` | Y | 양수 정수 |
| `memo` | N | 문자열 |
| `tags` | N | 쉼표(`,`) 구분 문자열 (예: `"meal,friend"`) |

- 공통: **UTF-8, 헤더 포함**. (엑셀의 "CSV UTF-8" 형식도 읽을 수 있습니다)
- export한 파일은 같은 스키마라서 **그대로 다시 import**할 수 있습니다.

**import — 깨진 행이 섞여 있을 때**
```
$ python -m budget_app import --from samples/import_broken.csv
[완료] imported=2, skipped=4
  - 건너뜀: 3번째 줄: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
  - 건너뜀: 4번째 줄: 금액은 0보다 커야 합니다 (양수).
  - 건너뜀: 5번째 줄: 허용되지 않은 타입입니다: spend
  - 건너뜀: 6번째 줄: 등록되지 않은 카테고리입니다: shopping
```
- 기본: 정상 행만 등록하고, 건너뛴 행은 **줄 번호와 이유**를 보고합니다. (부분 성공)
- `--strict`: 하나라도 깨진 행이 있으면 **아무것도 등록하지 않습니다.** (전체 취소)
- 어느 경우든 저장은 마지막에 원자적으로 한 번만 합니다.

**export**
```
$ python -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (5 records)
```
- `--month YYYY-MM` 또는 `--from YYYY-MM-DD` / `--to YYYY-MM-DD` 중 **하나 이상 필수**입니다.
- `--category`, `--type`, `--q`, `--tag` 조건도 함께 쓸 수 있습니다.

## 8. 오류 처리와 종료 코드

오류는 스택트레이스 대신 **원인 + 해결 힌트**로 출력합니다.

```
$ python -m budget_app delete --id TX-999999
[오류] 없는 데이터입니다: id=TX-999999
[힌트] list 또는 search 로 id를 확인하세요. (예: TX-000001)
$ echo $?
1
```

| 종료 코드 | 의미 |
| --- | --- |
| `0` | 정상 종료 |
| `1` | 실행 중 오류 (잘못된 값, 없는 id, 파일 문제 등) |
| `2` | 명령 형식 오류 (필수 옵션 누락, 모르는 옵션 등) |

## 9. 데코레이터 (공통 기능 분리)

`decorators.py`에 두 개를 만들어 **모든 명령 함수**에 붙였습니다.

```python
@log_execution    # 명령 이름·종료 코드·걸린 시간을 data/app.log 에 기록
@handle_errors    # 오류 → [오류]/[힌트] 출력 + 종료 코드 1
def cmd_add(args, service) -> int:
    ...
```

같은 코드를 명령마다 복사하지 않고 `@` 한 줄로 재사용합니다. 명령 함수에는 그 명령의 핵심 일만 남습니다.

## 10. 보너스 기능

| 기능 | 명령 / 위치 | 설명 |
| --- | --- | --- |
| 백업 | `backup` | `data/backups/<날짜-시간>/`에 저장 파일 복사 |
| 반복 내역 | `recurring add / list / remove / apply --month` | 월급·월세 규칙 저장 후 해당 월에 자동 생성. 같은 달에 다시 실행해도 중복이 생기지 않고, 31일 규칙은 짧은 달에 마지막 날로 맞춥니다 |
| 표 정렬 | `formatter.py` | 외부 라이브러리 없이 열 너비를 맞춥니다. 한글은 화면에서 2칸을 차지하는 점까지 계산합니다 |
| 저장 원자성 | `storage.py`의 `write_jsonl_atomic()` | 임시 파일에 쓰고 `os.replace()`로 교체 |

## 11. 테스트

```bash
python -m unittest          # 97개 테스트 (검증 / 저장소 / 서비스 / 출력 / CLI)
```

## 12. 10만 건 실측

```bash
python scripts/make_big_data.py     # bigdata/ 폴더에 거래 10만 건을 만들고 측정
```

측정 결과 (거래 10만 건, 파일 13.5MB, Apple Silicon Mac):

| 작업 | 시간 | 최대 메모리 |
| --- | --- | --- |
| list: 스트리밍 + 최신 10건 | 0.21초 | **0.05 MB** |
| 비교: 전체를 리스트로 올린 뒤 정렬 | 0.30초 | **61.31 MB** |
| summary: 스트리밍 합계 | 0.19초 | 0.05 MB |
| 새 id 발급 (전체 훑기) | 0.20초 | 0.05 MB |
| update 1건 (전체 다시 쓰기) | 0.77초 | 0.06 MB |

- **스트리밍 덕분에 메모리는 거의 늘지 않습니다.** (전체 로드 대비 약 1,000분의 1)
- **병목은 시간**입니다. 명령마다 파일을 처음부터 끝까지 훑고, update/delete는 파일 전체를 다시 씁니다.
- 개선 방향: 마지막 id를 별도 파일에 저장, 월별로 파일 분리, 또는 표준 라이브러리 `sqlite3`로 바꾸고 인덱스 사용.

## 13. 문서

- [docs/01_설계전략.md](docs/01_설계전략.md) — 구조, 결정 사항과 그 이유
- [docs/02_실행가이드.md](docs/02_실행가이드.md) — 필수 기능을 한 번씩 체험하는 단계별 가이드 (약 10분)
