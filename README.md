# 나만의 용돈 기입장 (budget_app)

파일(JSONL)에 데이터를 영구 저장하는 **콘솔 가계부**입니다.
수입·지출 기록, 검색, 월별 요약, 예산 경고, 카테고리 관리, CSV 가져오기/내보내기를 지원합니다.

- Python 3.10 이상 (3.10 / 3.11 / 3.14에서 테스트 통과)
- **표준 라이브러리만 사용** — `pip install` 필요 없음

**이 문서를 읽는 순서**

```
 0. 미션 소개        무엇을, 왜 만드나
 1. 구조             어떤 구도로 나눴나
 2. 핵심 기술 4가지   어떻게 만들었나
 3. 데이터 안전장치   미션의 핵심을 어떻게 지켰나
 ─────────────────── 여기까지가 설계 설명 ───────────────────
 4 ~ 11. 사용법      실행 · 저장 파일 · 명령 · CSV · 오류 · 보너스
 12. 검증            테스트 97개 + 10만 건 실측
 부록               요구사항 체크표 · 용어 정리 · 문서
```

---

## 0. 미션 소개

**한 줄 설명**: Python 표준 라이브러리로 **파일에 저장되는 콘솔 가계부**를 만들되, **오류가 나도 데이터가 안전하고 고치기 쉬운 구조**로 완성하는 미션입니다.

```
 무엇을?    🧾 콘솔 가계부 (터미널에서 명령어로 수입·지출 기록)
    │
 무엇으로?  🐍 Python 표준 라이브러리만  +  💾 파일(JSONL)에 저장
    │
 기능은?    추가 · 검색 · 월별 요약 · 예산 경고 · CSV 가져오기/내보내기
    │
 구조는?    제너레이터 · 데코레이터 · 타입 힌트 · 모듈 분리
    │
    ▼
 ★ 핵심     기능 수 ✕  →  오류가 나도 데이터 안전 + 고치기 쉬움 ⭕
```

> 미션 문구: **"작은 서비스"란 기능이 많은 것이 아니라, 예외 상황에서도 데이터가 안전한 것이다.**

그래서 이 프로젝트는 두 가지에 집중했습니다.

| 목표 | 이 문서에서 |
| --- | --- |
| **고치기 쉬운 구조** | [1. 구조](#1-구조), [2. 핵심 기술 4가지](#2-핵심-기술-4가지) |
| **데이터 안전** | [3. 데이터 안전장치](#3-데이터-안전장치) |

---

## 1. 구조

**기준**: 바뀌는 이유가 다른 코드끼리 나눴습니다. 화면을 바꿀 때는 CLI만, 저장 방식을 바꿀 때는 저장소만 고치면 됩니다.

```
  사람 (터미널)
     │  python -m budget_app add
     ▼
 ┌─ ① CLI ──── cli.py · prompts.py · formatter.py
 │              사람과 대화: 명령 해석, 입력 받기, 화면 출력
 │     ▼
 ├─ ② 서비스 ── services.py
 │              규칙 판단: 카테고리 확인, id 발급, 요약·예산 계산
 │     ▼
 └─ ③ 저장소 ── storage.py
                파일 다루기: 읽기/쓰기, 안전한 교체
   ④ 모델  models.py   모든 계층이 함께 쓰는 데이터 모양 (Transaction 등)
   + 공통 도구: validators.py(입력 검사) · decorators.py(오류·로그) · errors.py(오류 모양)
```

| 계층 | 하는 일 | 하지 않는 일 |
| --- | --- | --- |
| ① CLI | 명령 해석, 입력 받기, 화면 출력 | 계산, 파일 접근 |
| ② 서비스 (`BudgetService`) | 카테고리 확인, id 발급, 검색·요약, 사용 중 카테고리 삭제 막기 | 입력 받기, 파일 형식 다루기 |
| ③ 저장소 (`TransactionRepository`, `CategoryStore`, `BudgetStore`, `RecurringStore`) | 파일 1개당 클래스 1개로 읽기/쓰기 | 규칙 판단 |
| ④ 모델 (`Transaction` 등) | 데이터의 칸과 타입 정의 | 저장, 계산, 출력 |

**일은 위에서 아래로만 시킵니다.** `add` 명령 하나는 이렇게 지나갑니다.

```
__main__.py → cli.py(명령 해석) → prompts.py(질문) → validators.py(검사)
           → services.py(카테고리 확인, id 발급) → storage.py(파일 끝에 한 줄 추가)
           → cli.py([저장 완료] id 출력)
```

- import 방향도 같습니다. `cli` → `services` → `storage` → `models`. 거꾸로 가져다 쓰는 곳은 없습니다.
- 화면 출력(`print`)은 CLI 쪽 파일과 `decorators.py`에만 있고, 서비스·저장소·모델에는 없습니다.
- 그래서 서비스는 사람이 입력하지 않아도 **자동 테스트로 따로 검사**할 수 있습니다.

**폴더 구조**

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

코드 안에는 `# [요구 4.6]`처럼 **미션 요구사항 번호**를 주석으로 표시해 두었습니다.

---

## 2. 핵심 기술 4가지

```
 ┌ 제너레이터 ── 파일을 한 번에 다 읽지 않고 한 줄씩 처리   → 메모리 절약
 ├ 데코레이터 ── 모든 명령에 필요한 기능을 한 곳에 모음     → 복사 없음, 빠뜨림 없음
 ├ 타입 힌트 ─── 함수가 무엇을 받고 돌려주는지 적어 둠      → 실수 예방
 └ 모듈 분리 ─── 역할별로 파일을 나눔                       → 고칠 곳이 좁아짐 (1. 구조)
```

### 2-1. 제너레이터: 파일을 한 줄씩 읽기

`return`은 결과를 **한꺼번에** 돌려주고, `yield`는 **하나씩** 넘겨줍니다. 파일이 아무리 커도 메모리에는 지금 처리 중인 한 줄만 올라갑니다.

```python
# storage.py — read_jsonl
def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):   # 파일에서 한 줄씩 꺼냄
            ...
            yield record                                 # 1건 넘겨주고 멈춤 → 다음 요청 때 이어서

# services.py — search (list는 조건 없는 search)
matched = (tx for tx in self.transactions.iter_all() if condition.matches(tx))  # 조건에 맞는 것만 한 건씩
return heapq.nlargest(limit, matched, key=Transaction.latest_key)               # 최신 limit건만 기억
```

```
 transactions.jsonl ──한 줄씩──▶ read_jsonl ──▶ 조건 검사 ──▶ 최신 N건만 기억

 10만 건 실측 (최대 메모리)
 전체를 한 번에 읽기  ████████████████████████████████████████ 61 MB
 제너레이터 스트리밍  ▏ 0.05 MB
```

### 2-2. 데코레이터: 공통 기능을 한 곳에

명령 함수 18개 모두에 **오류 처리**와 **실행 기록**이 필요합니다. 같은 코드를 18번 복사하지 않고, 함수 위에 `@` 한 줄로 붙였습니다.

```python
@log_execution    # 바깥: 명령 이름·종료 코드·걸린 시간을 data/app.log 에 기록
@handle_errors    # 안쪽: 오류 → [오류]/[힌트] 출력 + 종료 코드 1
def cmd_add(args, service) -> int:
    ...           # 명령 함수에는 그 명령의 핵심 일만 남음
```

```
 명령 실행 ─▶ [log_execution: 시간 재기 시작]
                 ─▶ [handle_errors: 오류 감시]
                       ─▶ cmd_add 실행
                 ◀─ 오류가 나면 [오류]/[힌트]로 바꿔 출력
           ◀─ [log_execution: 걸린 시간을 app.log에 기록]
```

### 2-3. 타입 힌트: 함수의 입력·출력 약속

```
def  이름 ( 입력: 종류 )  ->  돌려주는 것
```

| 코드 | 읽는 법 | 얻은 효과 |
| --- | --- | --- |
| `def get(self, month: str) -> int \| None` (`storage.py` `BudgetStore`) | 월(글자)을 주면 예산(숫자)을, **없으면 None**을 준다 | 예산이 없는 달도 빠뜨리지 않고 처리 → `formatter.py`의 `if summary.budget is not None` |
| `def read_jsonl(path: Path) -> Iterator[dict]` | 파일 위치를 주면 데이터를 **하나씩** 꺼내 준다 | 첫 줄만 보고 "한 줄씩 읽는 함수"임을 앎 |
| `def search(self, condition: SearchFilter, limit: int) -> list[Transaction]` | 조건과 개수를 주면 **거래 목록**을 준다 | 무엇을 넣고 무엇을 받는지 바로 앎 |

데이터 모양도 타입과 함께 정의했습니다 (`models.py`).

```python
@dataclass
class Transaction:
    id: str          # "TX-000012"
    type: str        # "income" / "expense"
    date: str        # "YYYY-MM-DD"
    amount: int      # 양수
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)
```

### 2-4. 모듈 분리

[1. 구조](#1-구조)에서 설명한 4개 계층입니다. 필수 기준은 3개 이상 모듈인데, 이 프로젝트는 역할별로 10개 파일로 나눴습니다.

---

## 3. 데이터 안전장치

미션의 핵심인 **"예외 상황에서도 데이터가 안전한가"** 에 대한 답입니다.

| 이런 상황이 오면 | 이렇게 막습니다 | 확인 방법 |
| --- | --- | --- |
| 날짜·금액·타입을 잘못 입력 | **그 항목만 다시 묻기**. 잘못된 값은 저장되지 않음 | `add`에서 `2024-13-40` 입력 |
| 수정·삭제 중 프로그램이 꺼짐 | **임시 파일에 다 쓴 뒤 한 번에 교체** (원자적 저장). 원본은 그대로 | `python -m unittest tests.test_storage.AtomicWriteTest -v` |
| 사용 중인 카테고리를 삭제 | **삭제를 막음**. 거래가 없는 카테고리를 가리키는 일이 없도록 | `category remove --name food` |
| CSV에 깨진 줄이 섞임 | **줄 번호와 이유를 알려 주고 건너뜀**. `--strict`면 전부 취소 | `import --from samples/import_broken.csv` |
| 없는 id, 파일 문제 등 오류 | 스택트레이스 대신 **원인 + 해결 힌트**, 종료 코드 1 | `delete --id TX-999999` → `echo $?` |
| 처음 실행이라 파일이 없음 | 폴더·파일·기본 카테고리를 **자동 생성** | `rm -rf data` 후 아무 명령 |

**원자적 저장 (update / delete)**

```
 transactions.jsonl (원본)
        │  한 줄씩 읽으면서, 바꿀 줄만 바꿔서
        ▼
 transactions.jsonl.tmp (임시 파일)에 전부 쓰기
        │  끝까지 성공했을 때만
        ▼
 os.replace()  →  원본과 한 번에 교체 ✅

 ✗ 쓰는 도중 실패하면  →  임시 파일만 지우고, 원본은 그대로
```

```python
# storage.py — write_jsonl_atomic
tmp_path = path.with_name(path.name + ".tmp")
try:
    with tmp_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        ...
    os.replace(tmp_path, path)          # 다 썼을 때만 원본과 교체
finally:
    tmp_path.unlink(missing_ok=True)    # 실패했다면 남은 임시 파일 정리
```

**깨진 CSV 처리 (import)**

```
 CSV 한 줄씩 검사
   ├─ 정상 → 등록 대기 목록에
   └─ 문제 → "N번째 줄: 이유" 기록
        │
        ▼
 기본      → 정상 줄만 저장 + 건너뛴 줄 보고   (부분 성공)
 --strict  → 하나라도 문제면 아무것도 저장 안 함 (전체 취소)
        │
 저장은 마지막에 한 번, 원자적으로 → 도중에 실패해도 기존 데이터는 그대로
```

---

## 4. 실행 방법

프로젝트 폴더(`B2-1/`)에서 실행합니다.

```bash
python -m budget_app <command> [options]

python -m budget_app --help          # 전체 명령 목록
python -m budget_app add --help      # 명령별 사용법 (모든 명령·하위 명령 지원)
```

- 옵션은 모두 `--` 표기로 통일했습니다. (`-h` 없이 `--help`만 사용)
- 옵션은 **명령 뒤에** 씁니다. 예: `python -m budget_app list --limit 5`
- macOS에서 `python`이 없으면 `python3`로 실행하세요.

## 5. 저장 파일 위치와 형식

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

**JSONL을 고른 이유**: 한 줄이 거래 1건이라 **한 줄씩 읽는 제너레이터와 잘 맞고**, 값마다 이름표가 있어 태그 목록이나 쉼표가 들어간 메모도 그대로 저장됩니다. 엑셀로 바로 열 수 없는 단점은 **CSV 내보내기**로 보완했습니다.

**초기 실행 동작 (안 A)**
- 폴더나 파일이 없으면 **자동으로 만듭니다.**
- 카테고리가 비어 있으면 **기본 카테고리를 자동 생성**하고 안내 메시지를 출력합니다.
  ```
  [안내] 카테고리가 비어 있어 기본 카테고리를 만들었습니다: food, transport, rent, salary, etc
  ```

## 6. 명령 요약

```
 기록하기            찾아보기             정리·관리              주고받기
 ─────────          ─────────           ──────────            ─────────
 add    추가         list   목록(최신순)   summary  월별 요약      import  CSV → 가계부
 update 수정         search 조건 검색      budget   월 예산·경고   export  가계부 → CSV
 delete 삭제                              category 카테고리 관리
```

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

## 7. 주요 명령 실행 예시

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

## 8. update 방식: 옵션 방식으로 고정

`update`는 **옵션 방식(안 A)** 으로 고정했습니다. 준 옵션의 항목만 바뀌고 나머지는 그대로입니다.

```bash
python -m budget_app update --id <id> [--date YYYY-MM-DD] [--type income|expense] \
       [--category 이름] [--amount 금액] [--memo 메모] [--tags 태그1,태그2]
```

- 없는 id → `[오류] 없는 데이터입니다` (종료 코드 1)
- 바꿀 옵션을 하나도 안 주면 → `[오류] 수정할 항목이 없습니다`
- `--memo ""`, `--tags ""` 처럼 빈 값을 주면 메모·태그를 지웁니다.
- 저장은 [원자적 저장](#3-데이터-안전장치)으로 처리합니다.

## 9. import / export CSV 스키마

**스키마**란 파일이 지켜야 할 **칸의 약속**입니다. 어떤 칸이 있고, 반드시 있어야 하는지, 어떤 값이 들어가는지를 정해 둔 것입니다. 약속이 고정되어 있어야 다른 사람이 만든 CSV도 가져올 수 있고, 내보낸 CSV를 엑셀에서 열거나 다시 가져올 수 있습니다.

```
 CSV 파일 (samples/import_ok.csv)

 date      ,type   ,category,amount,memo ,tags          ← 1행: 헤더 (칸 이름, 반드시 포함)
 2024-01-05,expense,food    ,12000 ,점심 ,"meal,friend"  ← 2행부터: 거래 1건씩
  │          │       │        │      │     │
  │          │       │        │      │     └ 선택: 쉼표로 구분, 쉼표가 있으면 "따옴표"로 감쌈
  │          │       │        │      └────── 선택: 아무 문자열
  │          │       │        └───────────── 필수: 양수 정수 (0, 음수, 소수 X)
  │          │       └────────────────────── 필수: category list 에 등록된 이름
  │          └────────────────────────────── 필수: income 또는 expense
  └───────────────────────────────────────── 필수: YYYY-MM-DD
```

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

**CSV와 저장 파일(JSONL)의 관계**: CSV에는 `id`가 없습니다. import할 때 프로그램이 새 번호를 붙이고, export할 때는 번호를 빼고 씁니다.

```
 import:  CSV 한 행 ──검사──▶ id 발급 ──▶ transactions.jsonl 에 한 줄 추가
          2024-01-05,expense,food,12000,점심,"meal,friend"
            → {"id": "TX-000003", "type": "expense", "date": "2024-01-05", "amount": 12000,
               "category": "food", "memo": "점심", "tags": ["meal", "friend"]}

 export:  transactions.jsonl ──조건으로 거르기──▶ id 빼고 CSV 한 행으로
```
(`TX-000003`은 예시입니다. 실제 번호는 이미 저장된 거래 수에 따라 정해집니다.)

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

**export**
```
$ python -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (5 records)
```
- `--month YYYY-MM` 또는 `--from YYYY-MM-DD` / `--to YYYY-MM-DD` 중 **하나 이상 필수**입니다.
- `--category`, `--type`, `--q`, `--tag` 조건도 함께 쓸 수 있습니다.

## 10. 오류 처리와 종료 코드

오류는 스택트레이스 대신 **원인 + 해결 힌트**로 출력합니다. (담당: `@handle_errors`)

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

## 11. 보너스 기능

| 기능 | 명령 / 위치 | 설명 |
| --- | --- | --- |
| 저장 원자성 | `storage.py`의 `write_jsonl_atomic()` | 임시 파일에 쓰고 `os.replace()`로 교체 ([3. 데이터 안전장치](#3-데이터-안전장치)) |
| 표 정렬 | `formatter.py` | 외부 라이브러리 없이 열 너비를 맞춥니다. 한글은 화면에서 2칸을 차지하는 점까지 계산합니다 |
| 백업 | `backup` | `data/backups/<날짜-시간>/`에 저장 파일 복사 |
| 반복 내역 | `recurring add / list / remove / apply --month` | 월급·월세 규칙 저장 후 해당 월에 자동 생성. 같은 달에 다시 실행해도 중복이 생기지 않고, 31일 규칙은 짧은 달에 마지막 날로 맞춥니다 |

---

## 12. 검증

**자동 테스트**

```bash
python -m unittest          # 97개 테스트 (검증 / 저장소 / 서비스 / 출력 / CLI)
```

**10만 건 실측**

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

- **메모리는 거의 늘지 않습니다.** 스트리밍 덕분에 전체 로드 대비 약 1,000분의 1입니다.
- **병목은 시간**입니다. 명령마다 파일을 처음부터 끝까지 훑고, update/delete는 파일 전체를 다시 씁니다.
- 개선 방향: 마지막 id를 별도 파일에 저장, 월별로 파일 분리, 또는 표준 라이브러리 `sqlite3`로 바꾸고 인덱스 사용.

---

## 부록 A. 요구사항 체크표

**과제 목표 (설명할 수 있어야 하는 것)**

| 과제 목표 | 설명 위치 |
| --- | --- |
| 파일 기반 저장으로 CRUD·검색·요약·입출력 구현 | [5. 저장 파일](#5-저장-파일-위치와-형식), [6. 명령 요약](#6-명령-요약), [9. CSV 스키마](#9-import--export-csv-스키마) |
| 계층(모델/저장소/서비스/CLI)의 책임 | [1. 구조](#1-구조) |
| 제너레이터 스트리밍의 이유와 동작 | [2-1. 제너레이터](#2-1-제너레이터-파일을-한-줄씩-읽기), [12. 검증](#12-검증) |
| 데코레이터로 공통 관심사 분리 | [2-2. 데코레이터](#2-2-데코레이터-공통-기능을-한-곳에) |
| 타입 힌트로 입출력 계약 명확화 | [2-3. 타입 힌트](#2-3-타입-힌트-함수의-입력출력-약속) |

**추가 조건 (최종 결과물 필수 구성)**

| 추가 조건 | 충족 내용 | 위치 |
| --- | --- | --- |
| 데이터를 3개 이상 파일로 영구 저장 | `transactions` / `categories` / `budgets` (+ 보너스 `recurring`) `.jsonl` | [5. 저장 파일](#5-저장-파일-위치와-형식) |
| README: 실행 방법 | `python -m budget_app <command> [options]` | [4. 실행 방법](#4-실행-방법) |
| README: 저장 파일 위치/형식 | `./data/`, JSONL, `--data-dir`로 변경 | [5. 저장 파일](#5-저장-파일-위치와-형식) |
| README: 주요 명령 예시 | 명령별 실제 실행 화면 | [6. 명령 요약](#6-명령-요약), [7. 실행 예시](#7-주요-명령-실행-예시) |
| README: import/export CSV 스키마 | 칸 6개의 이름·필수 여부·값 형식과 예시 | [9. CSV 스키마](#9-import--export-csv-스키마) |

## 부록 B. 용어 정리

| 용어 | 뜻 | 이 프로젝트에서 |
| --- | --- | --- |
| **작은 서비스** | 기능 수보다 데이터 안전을 우선하는 프로그램 | 입력 검증, 원자적 저장, 삭제 보호 |
| **CRUD** | 만들기(Create)·읽기(Read)·고치기(Update)·지우기(Delete) | `add` / `list`·`search` / `update` / `delete` |
| **영구 저장** | 프로그램을 꺼도 데이터가 남음 | `data/` 폴더의 파일 |
| **JSONL** | 한 줄에 JSON 하나 = 데이터 1건인 텍스트 파일 | 저장 형식 |
| **CSV** | 쉼표로 칸을 나눈 표 형식 텍스트 (엑셀에서 열림) | `import` / `export` 형식 |
| **스키마** | 파일이 지켜야 할 칸의 약속 (칸 이름·필수 여부·값 형식) | [9. CSV 스키마](#9-import--export-csv-스키마) |
| **헤더** | CSV 첫 줄의 칸 이름 | `date,type,category,amount,memo,tags` |
| **계층 (레이어)** | 역할별로 나눈 코드 층 | CLI → 서비스 → 저장소 → 모델 |
| **클래스** | 관련 있는 데이터와 기능을 묶은 틀 | `BudgetService`, `Transaction` 등 |
| **dataclass** | 칸(필드)만 적으면 데이터 클래스를 만들어 주는 도구 | `models.py`의 `Transaction` |
| **제너레이터** | `yield`로 값을 하나씩 넘겨주는 함수 | `storage.py`의 `read_jsonl` |
| **스트리밍** | 데이터를 한꺼번에 담지 않고 흘려 보내며 처리 | `list`, `search`, `summary` |
| **데코레이터** | 함수 위에 `@이름`을 붙여 앞뒤에 기능을 덧붙이는 문법 | `decorators.py` |
| **공통 관심사** | 모든 기능에 똑같이 필요한 일 (오류 처리·로그·시간 측정) | 데코레이터로 분리 |
| **타입 힌트** | `x: int`, `-> str`처럼 값의 종류를 적어 둔 표시 | 모든 함수 |
| **대화형 입력** | 프로그램이 묻고 사용자가 답하는 방식 (`input()`) | `add`, `category add` |
| **옵션 인자** | 명령 뒤에 `--이름 값`으로 주는 방식 | `list --limit 5` |
| **원자적 저장** | 전부 되거나 전혀 안 되거나 (중간 상태 없음) | 임시 파일 + `os.replace()` |
| **종료 코드 (exit code)** | 프로그램이 끝날 때 남기는 숫자. 0 = 정상 | 오류 시 1 또는 2 |
| **스택트레이스** | 오류가 난 위치까지의 함수 호출 기록. 개발자용이라 사용자에게는 어려움 | 출력하지 않고 `[오류]` + `[힌트]`로 대체 |

## 부록 C. 문서

- [docs/01_설계전략.md](docs/01_설계전략.md) — 구조, 결정 사항과 그 이유
- [docs/02_실행가이드.md](docs/02_실행가이드.md) — 필수 기능을 한 번씩 체험하는 단계별 가이드 (약 10분)
- [docs/03_시연가이드.md](docs/03_시연가이드.md) — 가계부를 처음 쓰는 직장인이 두 달(월 10건씩) 동안 차근차근 기록하는 시연 가이드 (예산 설정 → 8월 기록·결산 → 9월 기록·결산 → 돌아보기 → 고치기 → 내보내기·가져오기)
