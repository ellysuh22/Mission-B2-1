"""
③ 저장소 계층 — 파일을 읽고 쓰는 일만 합니다.

하는 일 :
  - JSONL 파일을 '한 줄씩' 읽어서 넘겨주기 (제너레이터 → 파일 전체를 메모리에 올리지 않음)
  - 파일 끝에 한 줄 추가하기 (add)
  - 임시 파일에 다 쓴 뒤 한 번에 교체하기 (update/delete — 원자적 저장)
  - import/export용 CSV 읽기/쓰기, 백업 복사
안 하는 일: "카테고리가 등록됐나?", "금액이 양수인가?" 같은 규칙 판단 (services 담당)
          → 저장 형식을 바꾸고 싶으면 이 파일만 고치면 됩니다.

JSONL(JSON Lines) = 한 줄에 JSON 하나 = 데이터 1건.
"""

import csv
import itertools
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from .errors import BudgetAppError
from .models import RecurringRule, Transaction, id_number

# [요구 4.4] 저장 파일 3개 이상으로 분리 (+ 보너스 반복 규칙 파일)
TRANSACTIONS_FILE = "transactions.jsonl"
CATEGORIES_FILE = "categories.jsonl"
BUDGETS_FILE = "budgets.jsonl"
RECURRING_FILE = "recurring.jsonl"
DATA_FILES = (TRANSACTIONS_FILE, CATEGORIES_FILE, BUDGETS_FILE, RECURRING_FILE)


# ── 공통 도구 함수: 아래 저장소 클래스들은 모두 이 3개만 사용합니다 ─────────


def read_jsonl(path: Path) -> Iterator[dict]:
    """[요구 4.6] 파일을 한 줄씩 읽어 dict를 하나씩 넘겨줍니다. (제너레이터)

    return 대신 yield를 쓰면 '한 줄 읽기 → 넘겨주기 → 다음 줄 읽기' 순서로 동작해서
    파일이 10만 줄이어도 메모리에는 지금 처리 중인 한 줄만 올라갑니다.
    """
    if not path.exists():
        return
    with path.open(encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue  # 빈 줄은 건너뜀
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise BudgetAppError(
                    f"{path.name} 파일의 {line_no}번째 줄이 손상되었습니다.",
                    "data/backups 의 백업으로 복원하거나, 해당 줄을 직접 고쳐 주세요.",
                )
            yield record


def append_jsonl(path: Path, record: dict) -> None:
    """파일 끝에 한 줄을 추가합니다. (기존 내용은 건드리지 않음)"""
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_jsonl_atomic(path: Path, records: Iterable[dict]) -> None:
    """[요구 4.7][보너스: 저장 원자성] 임시 파일에 전부 쓴 뒤, 원본과 한 번에 교체합니다.

    1) 같은 폴더의 임시 파일(예: transactions.jsonl.tmp)에 한 줄씩 씀
    2) 끝까지 다 썼을 때만 os.replace()로 원본과 '한 번에' 바꿔치기
    → 쓰는 도중 오류가 나거나 프로그램이 꺼져도 원본 파일은 멀쩡합니다.
    """
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())  # 디스크에 확실히 기록
        os.replace(tmp_path, path)  # 한 번에 교체 (원자적)
    finally:
        tmp_path.unlink(missing_ok=True)  # 실패했다면 남은 임시 파일 정리


# ── 저장소 클래스: 파일 1개 = 클래스 1개 ────────────────────────────


class TransactionRepository:
    """transactions.jsonl 담당 — 거래 읽기 / 추가 / 수정 / 삭제."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def iter_all(self) -> Iterator[Transaction]:
        """[요구 4.6] 거래를 파일에 적힌 순서대로 하나씩 넘겨줍니다. (제너레이터)"""
        for record in read_jsonl(self.path):
            yield Transaction.from_dict(record)

    def find(self, tx_id: str) -> Transaction | None:
        """id로 거래 1건을 찾습니다. 없으면 None."""
        for tx in self.iter_all():
            if tx.id == tx_id:
                return tx
        return None

    def last_number(self) -> int:
        """저장된 id 중 가장 큰 번호. (TX-000012 → 12, 거래가 없으면 0)"""
        return max((id_number(tx.id) for tx in self.iter_all()), default=0)

    def add(self, tx: Transaction) -> None:
        """[요구 4.5] 거래 1건을 파일 끝에 추가합니다."""
        append_jsonl(self.path, tx.to_dict())

    def add_many(self, transactions: list[Transaction]) -> None:
        """여러 건을 한 번에 추가합니다. (import용, 기존 + 새 거래를 원자적으로 저장)"""
        if not transactions:
            return
        old_records = read_jsonl(self.path)
        new_records = (tx.to_dict() for tx in transactions)
        write_jsonl_atomic(self.path, itertools.chain(old_records, new_records))

    def update(self, new_tx: Transaction) -> None:
        """[요구 4.7] id가 같은 줄만 새 내용으로 바꿔서 원자적으로 다시 씁니다."""
        records = (
            new_tx.to_dict() if tx.id == new_tx.id else tx.to_dict() for tx in self.iter_all()
        )
        write_jsonl_atomic(self.path, records)

    def delete(self, tx_id: str) -> None:
        """[요구 4.7] id가 같은 줄만 빼고 원자적으로 다시 씁니다."""
        records = (tx.to_dict() for tx in self.iter_all() if tx.id != tx_id)
        write_jsonl_atomic(self.path, records)


class CategoryStore:
    """categories.jsonl 담당 — 카테고리 이름 목록. 한 줄 예: {"name": "food"}"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_names(self) -> list[str]:
        return [record["name"] for record in read_jsonl(self.path)]

    def add(self, name: str) -> None:
        append_jsonl(self.path, {"name": name})

    def remove(self, name: str) -> None:
        records = ({"name": other} for other in self.list_names() if other != name)
        write_jsonl_atomic(self.path, records)


class BudgetStore:
    """budgets.jsonl 담당 — 월별 예산. 한 줄 예: {"month": "2024-01", "amount": 500000}"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> dict[str, int]:
        """{월: 예산} 형태로 모두 읽습니다. 예: {"2024-01": 500000}"""
        return {record["month"]: record["amount"] for record in read_jsonl(self.path)}

    def get(self, month: str) -> int | None:
        """그 달 예산. 설정하지 않았으면 None."""
        return self.load_all().get(month)

    def set(self, month: str, amount: int) -> None:
        """그 달 예산을 저장합니다. 이미 있으면 덮어씁니다. (원자적 저장)"""
        budgets = self.load_all()
        budgets[month] = amount
        records = ({"month": m, "amount": a} for m, a in sorted(budgets.items()))
        write_jsonl_atomic(self.path, records)


class RecurringStore:
    """[보너스] recurring.jsonl 담당 — 반복 내역 규칙 목록."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> list[RecurringRule]:
        return [RecurringRule.from_dict(record) for record in read_jsonl(self.path)]

    def save_all(self, rules: list[RecurringRule]) -> None:
        write_jsonl_atomic(self.path, (rule.to_dict() for rule in rules))


# ── 데이터 폴더 준비 / 백업 ─────────────────────────────────────


def prepare_data_dir(data_dir: Path) -> None:
    """[요구 4.4] 데이터 폴더와 저장 파일이 없으면 빈 파일로 만들어 둡니다."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        (data_dir / name).touch(exist_ok=True)


def backup_data_dir(data_dir: Path) -> Path:
    """[보너스: 백업] 저장 파일들을 data/backups/<날짜-시간>/ 폴더에 복사합니다."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = data_dir / "backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in DATA_FILES:
        shutil.copy2(data_dir / name, backup_dir / name)
    return backup_dir


# ── CSV (import / export) ────────────────────────────────────────


def read_csv_rows(path: Path, required_columns: list[str]) -> Iterator[tuple[int, dict]]:
    """[요구 4.12] CSV를 한 행씩 읽어 (줄 번호, {컬럼: 값})을 넘겨줍니다. (제너레이터)

    encoding="utf-8-sig": UTF-8이면서, 엑셀이 파일 맨 앞에 붙이는 표시(BOM)도 허용합니다.
    """
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = [col for col in required_columns if col not in (reader.fieldnames or [])]
            if missing:
                raise BudgetAppError(
                    f"CSV 헤더에 필수 컬럼이 없습니다: {', '.join(missing)}",
                    "첫 줄(헤더) 예: date,type,category,amount,memo,tags",
                )
            for row in reader:
                yield reader.line_num, row
    except FileNotFoundError:
        raise BudgetAppError(
            f"파일을 찾을 수 없습니다: {path}",
            "경로를 확인하세요. 예: import --from samples/import_ok.csv",
        )
    except UnicodeDecodeError:
        raise BudgetAppError(
            f"UTF-8 형식의 CSV가 아닙니다: {path}",
            "엑셀이라면 '다른 이름으로 저장 → CSV UTF-8(쉼표로 분리)'로 저장하세요.",
        )


def write_csv(path: Path, columns: list[str], rows: Iterable[dict]) -> int:
    """[요구 4.12] rows를 UTF-8·헤더 포함 CSV로 저장하고, 저장한 행 수를 돌려줍니다."""
    count = 0
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count
