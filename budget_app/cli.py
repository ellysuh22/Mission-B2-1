"""
① CLI 계층 — 사람과 대화하는 부분입니다.

하는 일 : 명령어/옵션 해석(argparse) → 입력값 검사 → 서비스 호출 → 결과 출력
안 하는 일: 계산·규칙(services), 파일 읽기/쓰기(storage)

이 파일의 구성
  1. 명령 함수(cmd_*) : 명령 하나 = 함수 하나. 모두 같은 3단계 → ① 입력 검사 ② 서비스 호출 ③ 출력
  2. 명령어/옵션 정의  : argparse. 여기 적은 설명이 --help 화면에 나옵니다.
  3. 실행 시작점(main)

모든 명령 함수에는 데코레이터 두 개를 붙여 공통 기능을 재사용합니다.
  @log_execution  ← 바깥: 명령 이름·종료 코드·걸린 시간을 data/app.log 에 기록
  @handle_errors  ← 안쪽: 오류를 [오류]/[힌트] 메시지로 바꾸고 종료 코드 1 반환
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Callable, NoReturn, TypeVar

from .decorators import handle_errors, log_execution
from .errors import ValidationError
from .formatter import (
    format_budgets,
    format_categories,
    format_error,
    format_rules,
    format_summary,
    format_transactions,
)
from .models import TRANSACTION_TYPES, SearchFilter
from .prompts import ask, ask_category
from .services import DEFAULT_CATEGORIES, BudgetService
from .validators import (
    parse_amount,
    parse_date,
    parse_day,
    parse_month,
    parse_name,
    parse_tags,
    parse_type,
)

T = TypeVar("T")


# ════════════════════════════════════════════════════════════════
# 1. 명령 함수 — 명령 하나 = 함수 하나
# ════════════════════════════════════════════════════════════════

# ── 거래 ───────────────────────────────────────────────


@log_execution
@handle_errors
def cmd_add(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.5] 거래 추가 — 대화형으로 하나씩 묻고, 틀리면 그 항목만 다시 묻습니다."""
    tx = service.add_transaction(
        date=ask("날짜(YYYY-MM-DD): ", parse_date),
        tx_type=ask("타입(income/expense): ", parse_type),
        category=ask_category(service.list_categories()),
        amount=ask("금액(양수): ", parse_amount),
        memo=input("메모(선택): ").strip(),
        tags=parse_tags(input("태그(쉼표로 구분, 없으면 엔터): ")),
    )
    print(f"[저장 완료] id={tx.id}")
    return 0


@log_execution
@handle_errors
def cmd_list(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.6] 거래 목록 — 최신순으로 --limit 건까지."""
    show_transactions(service, SearchFilter(), args.limit)
    return 0


@log_execution
@handle_errors
def cmd_search(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.8] 거래 검색 — --from/--to/--category/--type/--q/--tag 조건, 최신순."""
    show_transactions(service, build_filter(args), args.limit)
    return 0


@log_execution
@handle_errors
def cmd_update(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.7] 거래 수정 — 옵션 방식으로 고정. 준 옵션의 항목만 바꿉니다."""
    changes: dict = {}
    if args.date is not None:
        changes["date"] = parse_date(args.date)
    if args.type is not None:
        changes["type"] = args.type
    if args.category is not None:
        changes["category"] = args.category
    if args.amount is not None:
        changes["amount"] = parse_amount(args.amount)
    if args.memo is not None:
        changes["memo"] = args.memo
    if args.tags is not None:
        changes["tags"] = parse_tags(args.tags)
    if not changes:
        raise ValidationError(
            "수정할 항목이 없습니다.", "예: update --id TX-000001 --amount 20000 --memo 저녁"
        )

    tx = service.update_transaction(args.id, changes)
    print(f"[수정 완료] id={tx.id}")
    print(format_transactions([tx]))
    return 0


@log_execution
@handle_errors
def cmd_delete(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.7] 거래 삭제 — delete --id <id>"""
    tx = service.delete_transaction(args.id)
    print(f"[삭제 완료] id={tx.id}")
    return 0


# ── 요약 / 예산 ────────────────────────────────────────────


@log_execution
@handle_errors
def cmd_summary(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.9] 월별 요약 — 총수입/총지출/잔액 + 지출 TOP N + 예산 사용률."""
    month = parse_month(args.month)
    print(format_summary(service.monthly_summary(month, args.top)))
    return 0


@log_execution
@handle_errors
def cmd_budget_set(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.10] 예산 설정 — budget set --month YYYY-MM --amount 금액"""
    month = parse_month(args.month)
    amount = parse_amount(args.amount)
    service.set_budget(month, amount)
    print(f"[저장 완료] {month} 예산 {amount}원")
    return 0


@log_execution
@handle_errors
def cmd_budget_list(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.10] 예산 조회 — 월별 예산 목록."""
    print(format_budgets(service.list_budgets()))
    return 0


# ── 카테고리 ─────────────────────────────────────────────


@log_execution
@handle_errors
def cmd_category_add(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.11] 카테고리 추가 — --name 을 안 주면 대화형으로 묻습니다."""
    name = parse_name(args.name) if args.name is not None else ask("카테고리명: ", parse_name)
    service.add_category(name)
    print(f"[저장 완료] category={name}")
    return 0


@log_execution
@handle_errors
def cmd_category_list(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.11] 카테고리 목록."""
    print(format_categories(service.list_categories()))
    return 0


@log_execution
@handle_errors
def cmd_category_remove(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.11] 카테고리 삭제 — 사용 중이면 삭제를 막습니다."""
    name = parse_name(args.name) if args.name is not None else ask("삭제할 카테고리명: ", parse_name)
    service.remove_category(name)
    print(f"[삭제 완료] category={name}")
    return 0


# ── 가져오기 / 내보내기 ──────────────────────────────────────


@log_execution
@handle_errors
def cmd_import(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.12] CSV 가져오기 — 처리 건수 + 건너뛴 행의 이유를 출력합니다."""
    result = service.import_csv(Path(args.from_path), strict=args.strict)
    print(f"[완료] imported={result.imported}, skipped={len(result.skipped)}")
    for reason in result.skipped:
        print(f"  - 건너뜀: {reason}")
    return 0


@log_execution
@handle_errors
def cmd_export(args: argparse.Namespace, service: BudgetService) -> int:
    """[요구 4.12] CSV 내보내기 — --month 또는 --from/--to 조건 필수."""
    count = service.export_csv(Path(args.out), build_filter(args))
    print(f"[완료] {args.out} ({count} records)")
    return 0


# ── 보너스: 백업 / 반복 내역 ─────────────────────────────────


@log_execution
@handle_errors
def cmd_backup(args: argparse.Namespace, service: BudgetService) -> int:
    """[보너스] 백업 — 저장 파일을 타임스탬프 폴더에 복사합니다."""
    print(f"[백업 완료] {service.backup()}")
    return 0


@log_execution
@handle_errors
def cmd_recurring_add(args: argparse.Namespace, service: BudgetService) -> int:
    """[보너스] 반복 규칙 추가 — 대화형 (add와 같은 방식)."""
    rule = service.add_recurring(
        tx_type=ask("타입(income/expense): ", parse_type),
        category=ask_category(service.list_categories()),
        amount=ask("금액(양수): ", parse_amount),
        day=ask("매월 며칠(1~31): ", parse_day),
        memo=input("메모(선택): ").strip(),
        tags=parse_tags(input("태그(쉼표로 구분, 없으면 엔터): ")),
    )
    print(f"[저장 완료] id={rule.id} (매월 {rule.day}일 {rule.category} {rule.amount}원)")
    return 0


@log_execution
@handle_errors
def cmd_recurring_list(args: argparse.Namespace, service: BudgetService) -> int:
    """[보너스] 반복 규칙 목록."""
    print(format_rules(service.list_recurring()))
    return 0


@log_execution
@handle_errors
def cmd_recurring_remove(args: argparse.Namespace, service: BudgetService) -> int:
    """[보너스] 반복 규칙 삭제."""
    service.remove_recurring(args.id)
    print(f"[삭제 완료] id={args.id}")
    return 0


@log_execution
@handle_errors
def cmd_recurring_apply(args: argparse.Namespace, service: BudgetService) -> int:
    """[보너스] 반복 규칙으로 해당 월 거래 자동 생성 (같은 달에 다시 실행해도 중복 없음)."""
    month = parse_month(args.month)
    created = service.apply_recurring(month)
    print(f"[완료] {month} 반복 내역 {len(created)}건 생성")
    if created:
        print(format_transactions(created))
    else:
        print("(새로 만들 거래가 없습니다. 이미 생성했거나 규칙이 없습니다.)")
    return 0


# ── 명령 함수들이 함께 쓰는 도우미 ──────────────────────────────


def show_transactions(service: BudgetService, condition: SearchFilter, limit: int) -> None:
    """최신순 limit건을 표로 출력합니다. 1건 더 가져와서 '더 있는지'도 알려줍니다."""
    found = service.search(condition, limit + 1)
    print(format_transactions(found[:limit]))
    if len(found) > limit:
        print(f"... 최신 {limit}건만 표시했습니다. 더 보려면 --limit 값을 늘리세요.")


def build_filter(args: argparse.Namespace) -> SearchFilter:
    """검색 옵션들을 검사해서 SearchFilter(검색 조건 묶음)로 만듭니다. (search, export 공용)"""
    condition = SearchFilter(
        date_from=optional(args.date_from, parse_date),
        date_to=optional(args.date_to, parse_date),
        month=optional(args.month, parse_month),
        category=args.category,
        type=args.type,
        keyword=args.q,
        tag=args.tag,
    )
    if condition.date_from and condition.date_to and condition.date_from > condition.date_to:
        raise ValidationError(
            "--from 날짜가 --to 날짜보다 늦습니다.", "예: --from 2024-01-01 --to 2024-01-31"
        )
    return condition


def optional(text: str | None, parse: Callable[[str], T]) -> T | None:
    """옵션을 안 줬으면 None, 줬으면 parse 함수로 검사한 값을 돌려줍니다."""
    return None if text is None else parse(text)


# ════════════════════════════════════════════════════════════════
# 2. 명령어 / 옵션 정의 (argparse)
# ════════════════════════════════════════════════════════════════


class Parser(argparse.ArgumentParser):
    """[요구 4.1] 옵션은 '--'로 통일(-h 없이 --help만), 형식 오류도 [오류]/[힌트]로 출력."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, add_help=False, **kwargs)
        self.add_argument("--help", action="help", help="사용 방법을 보여줍니다.")

    def error(self, message: str) -> NoReturn:
        print(
            format_error(
                f"명령 형식이 올바르지 않습니다 — {message}",
                f"{self.prog} --help 로 사용 방법을 확인하세요.",
            ),
            file=sys.stderr,
        )
        sys.exit(2)


def positive_int(text: str) -> int:
    """--limit, --top 처럼 1 이상의 정수만 받는 옵션용."""
    if text.isdigit() and int(text) > 0:
        return int(text)
    raise argparse.ArgumentTypeError(f"1 이상의 정수가 필요합니다: {text}")


def build_parser() -> Parser:
    # 모든 명령에 공통으로 붙는 옵션
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", default="data", help="데이터 폴더 위치 (기본: ./data)")

    # search / export 가 함께 쓰는 검색 조건 옵션
    filters = argparse.ArgumentParser(add_help=False)
    filters.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작 날짜 (포함)")
    filters.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="끝 날짜 (포함)")
    filters.add_argument("--month", metavar="YYYY-MM", help="특정 월")
    filters.add_argument("--category", help="카테고리")
    filters.add_argument("--type", choices=TRANSACTION_TYPES, help="income 또는 expense")
    filters.add_argument("--q", metavar="KEYWORD", help="메모에 들어 있는 단어")
    filters.add_argument("--tag", help="태그")

    parser = Parser(prog="python -m budget_app", description="나만의 용돈 기입장 — 콘솔 가계부")
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    def add_command(group, name: str, description: str, handler, parents=()) -> Parser:
        """명령 하나를 등록하고, 실행할 명령 함수(handler)를 연결합니다."""
        command = group.add_parser(
            name, help=description, description=description, parents=[common, *parents]
        )
        command.set_defaults(handler=handler)
        return command

    # 거래
    add_command(commands, "add", "거래 추가 (대화형 입력)", cmd_add)

    p = add_command(commands, "list", "거래 목록 (최신순)", cmd_list)
    p.add_argument("--limit", type=positive_int, default=10, help="최대 출력 건수 (기본 10)")

    p = add_command(commands, "search", "거래 검색 (최신순)", cmd_search, parents=[filters])
    p.add_argument("--limit", type=positive_int, default=10, help="최대 출력 건수 (기본 10)")

    p = add_command(commands, "update", "거래 수정 (옵션 방식: 바꿀 항목만 지정)", cmd_update)
    p.add_argument("--id", required=True, help="수정할 거래 id (예: TX-000001)")
    p.add_argument("--date", metavar="YYYY-MM-DD", help="새 날짜")
    p.add_argument("--type", choices=TRANSACTION_TYPES, help="새 타입")
    p.add_argument("--category", help="새 카테고리 (등록된 것만)")
    p.add_argument("--amount", help="새 금액 (양수)")
    p.add_argument("--memo", help="새 메모 (빈 값 \"\" 이면 지움)")
    p.add_argument("--tags", help="새 태그, 쉼표로 구분 (빈 값 \"\" 이면 지움)")

    p = add_command(commands, "delete", "거래 삭제", cmd_delete)
    p.add_argument("--id", required=True, help="삭제할 거래 id (예: TX-000001)")

    # 요약 / 예산
    p = add_command(commands, "summary", "월별 요약 (예산이 있으면 사용률·초과 경고)", cmd_summary)
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="요약할 월")
    p.add_argument("--top", type=positive_int, default=3, help="지출 TOP N (기본 3)")

    budget = commands.add_parser("budget", help="예산 설정/조회", description="예산 설정/조회")
    budget_commands = budget.add_subparsers(dest="action", required=True, metavar="<action>")
    p = add_command(budget_commands, "set", "월 예산 설정 (이미 있으면 덮어씀)", cmd_budget_set)
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="예산을 정할 월")
    p.add_argument("--amount", required=True, help="예산 금액 (양수)")
    add_command(budget_commands, "list", "월별 예산 목록", cmd_budget_list)

    # 카테고리
    category = commands.add_parser("category", help="카테고리 관리", description="카테고리 관리")
    category_commands = category.add_subparsers(dest="action", required=True, metavar="<action>")
    p = add_command(category_commands, "add", "카테고리 추가", cmd_category_add)
    p.add_argument("--name", help="카테고리 이름 (생략하면 대화형으로 입력)")
    add_command(category_commands, "list", "카테고리 목록", cmd_category_list)
    p = add_command(category_commands, "remove", "카테고리 삭제 (사용 중이면 막음)", cmd_category_remove)
    p.add_argument("--name", help="카테고리 이름 (생략하면 대화형으로 입력)")

    # 가져오기 / 내보내기
    p = add_command(commands, "import", "CSV 가져오기", cmd_import)
    p.add_argument("--from", dest="from_path", required=True, metavar="FILE", help="가져올 CSV 경로")
    p.add_argument("--strict", action="store_true", help="문제 행이 하나라도 있으면 전부 취소")

    p = add_command(
        commands, "export", "CSV 내보내기 (--month 또는 --from/--to 필수)", cmd_export, parents=[filters]
    )
    p.add_argument("--out", required=True, metavar="FILE", help="저장할 CSV 경로")

    # 보너스
    add_command(commands, "backup", "데이터 백업 (타임스탬프 폴더에 복사)", cmd_backup)

    recurring = commands.add_parser("recurring", help="반복 내역 관리", description="반복 내역 관리")
    recurring_commands = recurring.add_subparsers(dest="action", required=True, metavar="<action>")
    add_command(recurring_commands, "add", "반복 규칙 추가 (대화형)", cmd_recurring_add)
    add_command(recurring_commands, "list", "반복 규칙 목록", cmd_recurring_list)
    p = add_command(recurring_commands, "remove", "반복 규칙 삭제", cmd_recurring_remove)
    p.add_argument("--id", required=True, help="삭제할 규칙 id (예: RC-001)")
    p = add_command(recurring_commands, "apply", "반복 규칙으로 해당 월 거래 생성", cmd_recurring_apply)
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="거래를 만들 월")

    return parser


# ════════════════════════════════════════════════════════════════
# 3. 실행 시작점
# ════════════════════════════════════════════════════════════════


def main(argv: list[str] | None = None) -> int:
    """[요구 4.14] 종료 코드: 0 = 성공, 1 = 실행 중 오류, 2 = 명령 형식 오류."""
    args = build_parser().parse_args(argv)  # 형식이 틀리면 여기서 [오류] 출력 후 종료 코드 2
    return run(args)


@handle_errors
def run(args: argparse.Namespace) -> int:
    """데이터 폴더 준비 → 로그 설정 → 명령 함수 실행."""
    data_dir = Path(args.data_dir)
    service = BudgetService(data_dir)
    logging.basicConfig(
        filename=data_dir / "app.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        force=True,
    )
    if service.ensure_default_categories():
        print(f"[안내] 카테고리가 비어 있어 기본 카테고리를 만들었습니다: {', '.join(DEFAULT_CATEGORIES)}")
    return args.handler(args, service)
