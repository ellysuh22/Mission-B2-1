"""
출력 모양 — 데이터를 '보기 좋은 문자열'로 바꿉니다. [보너스: 외부 라이브러리 없이 표 정렬]

하는 일 : 거래 목록 표, 월별 요약, 카테고리/예산/반복 규칙 목록, 오류 메시지의 모양 만들기
안 하는 일: 계산(services), 파일 읽기/쓰기(storage), 실제 print (cli가 합니다)
"""

import unicodedata

from .models import MonthlySummary, RecurringRule, Transaction


def format_error(message: str, hint: str = "") -> str:
    """[요구 4.14] 오류를 '원인 + 해결 힌트' 두 줄로 만듭니다."""
    text = f"[오류] {message}"
    if hint:
        text += f"\n[힌트] {hint}"
    return text


# ── 표 정렬 [보너스] ──────────────────────────────────────


def display_width(text: str) -> int:
    """화면에서 차지하는 칸 수. 한글 같은 넓은 글자는 2칸, 영문·숫자는 1칸."""
    return sum(2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in text)


def pad(text: str, width: int, right: bool = False) -> str:
    """text 옆을 빈칸으로 채워 width 칸에 맞춥니다. right=True면 오른쪽 정렬(금액용)."""
    spaces = " " * (width - display_width(text))
    return spaces + text if right else text + spaces


def format_table(headers: list[str], rows: list[list[str]], right_columns: tuple[int, ...] = ()) -> str:
    """열 너비를 맞춘 표를 만듭니다. right_columns: 오른쪽 정렬할 열 번호(0부터)."""
    all_rows = [headers] + rows
    widths = [max(display_width(row[i]) for row in all_rows) for i in range(len(headers))]
    lines = []
    for row in all_rows:
        cells = [pad(cell, widths[i], i in right_columns) for i, cell in enumerate(row)]
        lines.append(" | ".join(cells).rstrip())
    lines.insert(1, "-+-".join("-" * width for width in widths))  # 머리글 아래 구분선
    return "\n".join(lines)


# ── 명령별 출력 모양 ─────────────────────────────────────


def format_transactions(transactions: list[Transaction]) -> str:
    """[요구 4.6, 4.8] 거래 목록 표."""
    if not transactions:
        return "조건에 맞는 거래가 없습니다."
    rows = [
        [tx.id, tx.date, tx.type, tx.category, str(tx.amount), tx.memo, ",".join(tx.tags)]
        for tx in transactions
    ]
    headers = ["ID", "날짜", "타입", "카테고리", "금액", "메모", "태그"]
    return format_table(headers, rows, right_columns=(4,))


def format_summary(summary: MonthlySummary) -> str:
    """[요구 4.9, 4.10] 월별 요약 + 예산 사용률 / 초과 경고."""
    lines = [f"[{summary.month} 월별 요약]"]
    if summary.count == 0:
        lines.append("데이터 없음 (이 달에 기록된 거래가 없습니다)")
    else:
        lines.append(f"총 수입: {summary.total_income}원")
        lines.append(f"총 지출: {summary.total_expense}원")
        lines.append(f"잔액: {summary.balance}원")

    if summary.budget is not None:
        lines.append(f"예산: {summary.budget}원 (사용률 {summary.budget_usage:.1f}%)")
        if summary.over_budget > 0:
            lines.append(f"[경고] 예산을 {summary.over_budget}원 초과했습니다!")

    if summary.count > 0:
        lines.append("")
        lines.append(f"지출 TOP {len(summary.top_expenses)}")
        if not summary.top_expenses:
            lines.append("(지출 내역 없음)")
        for rank, (category, total) in enumerate(summary.top_expenses, start=1):
            lines.append(f"{rank}) {category} {total}원")
    return "\n".join(lines)


def format_categories(names: list[str]) -> str:
    """[요구 4.11] 카테고리 목록. 예: '- food'"""
    if not names:
        return "등록된 카테고리가 없습니다."
    return "\n".join(f"- {name}" for name in names)


def format_budgets(budgets: dict[str, int]) -> str:
    """[요구 4.10] 월별 예산 목록 표."""
    if not budgets:
        return "설정된 예산이 없습니다. (예: budget set --month 2024-01 --amount 500000)"
    rows = [[month, f"{amount}원"] for month, amount in sorted(budgets.items())]
    return format_table(["월", "예산"], rows, right_columns=(1,))


def format_rules(rules: list[RecurringRule]) -> str:
    """[보너스] 반복 규칙 목록 표."""
    if not rules:
        return "등록된 반복 규칙이 없습니다. (예: recurring add)"
    rows = [
        [rule.id, f"매월 {rule.day}일", rule.type, rule.category, str(rule.amount), rule.memo,
         ",".join(rule.applied_months)]
        for rule in rules
    ]
    headers = ["ID", "날짜", "타입", "카테고리", "금액", "메모", "생성한 달"]
    return format_table(headers, rows, right_columns=(4,))
