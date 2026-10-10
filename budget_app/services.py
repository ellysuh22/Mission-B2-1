"""
② 서비스 계층 — 가계부의 '규칙'을 담당합니다.

하는 일 : 카테고리 등록 여부 확인, id 발급, 검색·요약 계산, 예산 사용률,
          사용 중인 카테고리 삭제 막기, import/export, 반복 내역, 백업
안 하는 일: 사람과 대화하기(cli), 파일 형식(JSONL/CSV) 다루기(storage)

CLI는 BudgetService의 메서드만 부르고, 파일 작업은 저장소 클래스에게 맡깁니다.
"""

import calendar
import dataclasses
import heapq
from collections import Counter
from pathlib import Path

from .errors import BudgetAppError, ValidationError
from .models import (
    INCOME,
    ImportResult,
    MonthlySummary,
    RecurringRule,
    SearchFilter,
    Transaction,
    id_number,
    make_tx_id,
)
from .storage import (
    BUDGETS_FILE,
    CATEGORIES_FILE,
    RECURRING_FILE,
    TRANSACTIONS_FILE,
    BudgetStore,
    CategoryStore,
    RecurringStore,
    TransactionRepository,
    backup_data_dir,
    prepare_data_dir,
    read_csv_rows,
    write_csv,
)
from .validators import parse_amount, parse_date, parse_tags, parse_type

# [요구 4.4 안 A] 카테고리가 비어 있으면 자동으로 만드는 기본 카테고리
DEFAULT_CATEGORIES = ["food", "transport", "rent", "salary", "etc"]

# [요구 4.12] import/export CSV 고정 스키마
CSV_COLUMNS = ["date", "type", "category", "amount", "memo", "tags"]
REQUIRED_COLUMNS = ["date", "type", "category", "amount"]


class BudgetService:
    """가계부 서비스 — 기능 규칙을 모아 둔 클래스."""

    def __init__(self, data_dir: Path) -> None:
        prepare_data_dir(data_dir)  # [요구 4.4] 파일이 없으면 자동 생성
        self.data_dir = data_dir
        self.transactions = TransactionRepository(data_dir / TRANSACTIONS_FILE)
        self.categories = CategoryStore(data_dir / CATEGORIES_FILE)
        self.budgets = BudgetStore(data_dir / BUDGETS_FILE)
        self.recurring = RecurringStore(data_dir / RECURRING_FILE)

    # ── 카테고리 [요구 4.11] ─────────────────────────────────

    def ensure_default_categories(self) -> bool:
        """[요구 4.4 안 A] 카테고리가 하나도 없으면 기본 카테고리를 만듭니다. 만들었으면 True."""
        if self.categories.list_names():
            return False
        for name in DEFAULT_CATEGORIES:
            self.categories.add(name)
        return True

    def list_categories(self) -> list[str]:
        return self.categories.list_names()

    def add_category(self, name: str) -> None:
        if name in self.list_categories():
            raise BudgetAppError(
                f"이미 등록된 카테고리입니다: {name}", "category list 로 목록을 확인하세요."
            )
        self.categories.add(name)

    def remove_category(self, name: str) -> None:
        """사용 중인 카테고리는 삭제를 막습니다.

        이유: 거래가 '없는 카테고리'를 가리키는 고아 데이터가 생기지 않게 하려고.
        """
        self.check_category(name)
        used = sum(1 for tx in self.transactions.iter_all() if tx.category == name)
        if used > 0:
            raise BudgetAppError(
                f"'{name}' 카테고리를 사용하는 거래가 {used}건 있어 삭제할 수 없습니다.",
                f"search --category {name} 로 거래를 찾고, "
                "update --id <id> --category <다른 카테고리> 로 바꾼 뒤 다시 삭제하세요.",
            )
        rule_ids = [rule.id for rule in self.recurring.load_all() if rule.category == name]
        if rule_ids:
            raise BudgetAppError(
                f"'{name}' 카테고리를 사용하는 반복 규칙이 있어 삭제할 수 없습니다: {', '.join(rule_ids)}",
                "recurring remove --id <id> 로 규칙을 먼저 삭제하세요.",
            )
        self.categories.remove(name)

    def check_category(self, name: str) -> None:
        """등록된 카테고리인지 확인합니다. 아니면 오류."""
        names = self.list_categories()
        if name not in names:
            raise BudgetAppError(
                f"등록되지 않은 카테고리입니다: {name}",
                f"사용 가능: {', '.join(names)} (새 카테고리는 category add 로 등록)",
            )

    # ── 거래 추가 / 목록 / 검색 [요구 4.5, 4.6, 4.8] ──────────────────

    def add_transaction(
        self,
        date: str,
        tx_type: str,
        category: str,
        amount: int,
        memo: str = "",
        tags: list[str] | None = None,
    ) -> Transaction:
        """거래 1건을 저장하고, 새 id가 붙은 거래를 돌려줍니다."""
        self.check_category(category)
        tx = Transaction(
            id=make_tx_id(self.transactions.last_number() + 1),
            type=tx_type,
            date=date,
            amount=amount,
            category=category,
            memo=memo,
            tags=list(tags or []),
        )
        self.transactions.add(tx)
        return tx

    def search(self, condition: SearchFilter, limit: int) -> list[Transaction]:
        """조건에 맞는 거래를 최신순으로 최대 limit건 돌려줍니다. (list = 조건 없는 search)

        ① iter_all()     : 파일을 한 줄씩 읽어 거래를 하나씩 넘김 (제너레이터)
        ② matched        : 조건에 맞는 것만 통과시킴 (제너레이터 표현식)
        ③ heapq.nlargest : 끝까지 훑으면서 '가장 최신 limit건'만 기억함
        → 거래가 10만 건이어도 메모리에는 limit건만 남습니다.
        """
        matched = (tx for tx in self.transactions.iter_all() if condition.matches(tx))
        return heapq.nlargest(limit, matched, key=Transaction.latest_key)

    # ── 수정 / 삭제 [요구 4.7] ───────────────────────────────

    def find_transaction(self, tx_id: str) -> Transaction:
        """id로 거래를 찾습니다. 없으면 '없는 데이터' 오류."""
        tx = self.transactions.find(tx_id)
        if tx is None:
            raise BudgetAppError(
                f"없는 데이터입니다: id={tx_id}",
                "list 또는 search 로 id를 확인하세요. (예: TX-000001)",
            )
        return tx

    def update_transaction(self, tx_id: str, changes: dict) -> Transaction:
        """changes에 들어 있는 항목만 바꿉니다. 예: {"amount": 20000}"""
        tx = self.find_transaction(tx_id)
        if "category" in changes:
            self.check_category(changes["category"])
        updated = dataclasses.replace(tx, **changes)  # 기존 거래를 복사하면서 바뀐 항목만 교체
        self.transactions.update(updated)
        return updated

    def delete_transaction(self, tx_id: str) -> Transaction:
        """거래를 삭제하고, 삭제한 거래를 돌려줍니다."""
        tx = self.find_transaction(tx_id)
        self.transactions.delete(tx_id)
        return tx

    # ── 월별 요약 / 예산 [요구 4.9, 4.10] ────────────────────────

    def monthly_summary(self, month: str, top: int) -> MonthlySummary:
        """한 달 요약. 파일을 한 줄씩 읽으며 합계만 더합니다. (전체를 메모리에 올리지 않음)"""
        count = total_income = total_expense = 0
        expense_by_category: Counter = Counter()  # {카테고리: 지출 합계}
        for tx in self.transactions.iter_all():
            if tx.month != month:
                continue
            count += 1
            if tx.type == INCOME:
                total_income += tx.amount
            else:
                total_expense += tx.amount
                expense_by_category[tx.category] += tx.amount
        return MonthlySummary(
            month=month,
            count=count,
            total_income=total_income,
            total_expense=total_expense,
            top_expenses=expense_by_category.most_common(top),  # 합계가 큰 순서로 top개
            budget=self.budgets.get(month),
        )

    def set_budget(self, month: str, amount: int) -> None:
        self.budgets.set(month, amount)

    def list_budgets(self) -> dict[str, int]:
        return self.budgets.load_all()

    # ── 가져오기 / 내보내기 [요구 4.12] ───────────────────────────

    def import_csv(self, csv_path: Path, strict: bool = False) -> ImportResult:
        """CSV의 거래를 한꺼번에 등록합니다.

        - 행마다 검사 → 문제 있는 행은 "N번째 줄: 이유"를 기록하고 건너뜀 (부분 성공 + 리포트)
        - strict=True 이면 문제 행이 하나라도 있을 때 아무것도 저장하지 않음 (전체 취소)
        - 저장은 마지막에 한 번, 원자적으로 → 도중에 실패해도 기존 데이터는 그대로
        """
        categories = self.list_categories()
        next_number = self.transactions.last_number() + 1
        new_transactions: list[Transaction] = []
        skipped: list[str] = []

        for line_no, row in read_csv_rows(csv_path, REQUIRED_COLUMNS):
            try:
                tx = row_to_transaction(row, make_tx_id(next_number), categories)
            except ValidationError as error:
                skipped.append(f"{line_no}번째 줄: {error.message}")
                continue
            new_transactions.append(tx)
            next_number += 1

        if strict and skipped:
            details = "\n  ".join(skipped)
            raise BudgetAppError(
                f"문제 있는 행이 {len(skipped)}개 있어 아무것도 가져오지 않았습니다 (--strict).\n  {details}",
                "CSV를 고친 뒤 다시 실행하거나, --strict 없이 실행해 정상 행만 가져오세요.",
            )
        self.transactions.add_many(new_transactions)
        return ImportResult(imported=len(new_transactions), skipped=skipped)

    def export_csv(self, out_path: Path, condition: SearchFilter) -> int:
        """조건에 맞는 거래를 CSV로 저장하고 건수를 돌려줍니다. (기간 조건 필수)"""
        if not (condition.month or condition.date_from or condition.date_to):
            raise BudgetAppError(
                "export 에는 기간 조건이 꼭 필요합니다.",
                "예: export --out export.csv --month 2024-01  또는  --from 2024-01-01 --to 2024-01-31",
            )
        rows = (transaction_to_row(tx) for tx in self.transactions.iter_all() if condition.matches(tx))
        return write_csv(out_path, CSV_COLUMNS, rows)

    # ── 반복 내역 [보너스] ────────────────────────────────────

    def add_recurring(
        self,
        tx_type: str,
        day: int,
        amount: int,
        category: str,
        memo: str = "",
        tags: list[str] | None = None,
    ) -> RecurringRule:
        """반복 규칙을 저장합니다. 예: 매월 25일 월급."""
        self.check_category(category)
        rules = self.recurring.load_all()
        number = max((id_number(rule.id) for rule in rules), default=0) + 1
        rule = RecurringRule(
            id=f"RC-{number:03d}",
            type=tx_type,
            day=day,
            amount=amount,
            category=category,
            memo=memo,
            tags=list(tags or []),
        )
        rules.append(rule)
        self.recurring.save_all(rules)
        return rule

    def list_recurring(self) -> list[RecurringRule]:
        return self.recurring.load_all()

    def remove_recurring(self, rule_id: str) -> None:
        rules = self.recurring.load_all()
        remaining = [rule for rule in rules if rule.id != rule_id]
        if len(remaining) == len(rules):
            raise BudgetAppError(
                f"없는 반복 규칙입니다: id={rule_id}", "recurring list 로 id를 확인하세요."
            )
        self.recurring.save_all(remaining)

    def apply_recurring(self, month: str) -> list[Transaction]:
        """반복 규칙으로 해당 월의 거래를 만듭니다.

        - 이미 만든 달(applied_months)은 건너뜀 → 두 번 실행해도 중복이 생기지 않음
        - 31일 규칙도 2월에는 마지막 날(28/29일)로 맞춤
        """
        year, month_number = int(month[:4]), int(month[5:7])
        last_day = calendar.monthrange(year, month_number)[1]
        rules = self.recurring.load_all()
        created: list[Transaction] = []
        for rule in rules:
            if month in rule.applied_months:
                continue
            tx = self.add_transaction(
                date=f"{month}-{min(rule.day, last_day):02d}",
                tx_type=rule.type,
                category=rule.category,
                amount=rule.amount,
                memo=rule.memo,
                tags=rule.tags,
            )
            rule.applied_months.append(month)
            created.append(tx)
        self.recurring.save_all(rules)
        return created

    # ── 백업 [보너스] ────────────────────────────────────────

    def backup(self) -> Path:
        return backup_data_dir(self.data_dir)


# ── CSV 행 ↔ Transaction 변환 ─────────────────────────────────


def cell(row: dict, column: str) -> str:
    """CSV 칸 값을 꺼냅니다. 칸이 없거나 비어 있으면 ''."""
    return (row.get(column) or "").strip()


def row_to_transaction(row: dict, tx_id: str, categories: list[str]) -> Transaction:
    """CSV 한 행을 검사해서 Transaction으로 바꿉니다. 문제가 있으면 ValidationError."""
    date = parse_date(cell(row, "date"))
    tx_type = parse_type(cell(row, "type"))
    category = cell(row, "category")
    if category not in categories:
        raise ValidationError(f"등록되지 않은 카테고리입니다: {category}")
    amount = parse_amount(cell(row, "amount"))
    return Transaction(
        id=tx_id,
        type=tx_type,
        date=date,
        amount=amount,
        category=category,
        memo=cell(row, "memo"),
        tags=parse_tags(cell(row, "tags")),
    )


def transaction_to_row(tx: Transaction) -> dict:
    """Transaction을 CSV 한 행으로 바꿉니다. (태그 목록은 쉼표로 이어 붙임)"""
    return {
        "date": tx.date,
        "type": tx.type,
        "category": tx.category,
        "amount": tx.amount,
        "memo": tx.memo,
        "tags": ",".join(tx.tags),
    }
