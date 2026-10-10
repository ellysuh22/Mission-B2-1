"""
입력 검증 — 사용자가 입력한 '글자'를 검사해서 올바른 값으로 바꿉니다.

하는 일 : 날짜 / 월 / 타입 / 금액 / 태그 / 카테고리 이름 / 반복 날짜의 형식 검사
안 하는 일: 카테고리가 '등록되어 있는지' 확인 (파일을 봐야 하므로 services 담당)

[요구 4.3] 모든 함수는 문제가 있으면 ValidationError(원인, 힌트)를 던집니다.
대화형 입력(prompts.py)은 이 오류를 받으면 다시 묻고,
옵션 입력(cli.py)은 오류 메시지를 보여주고 종료합니다.
"""

import re
from datetime import datetime

from .errors import ValidationError
from .models import TRANSACTION_TYPES

DATE_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}")  # 숫자4-숫자2-숫자2
MONTH_SHAPE = re.compile(r"\d{4}-\d{2}")  # 숫자4-숫자2


def _is_real_date(text: str, date_format: str) -> bool:
    """달력에 실제로 있는 날짜인지 확인합니다. (2024-13-40, 2023-02-29 → False)"""
    try:
        datetime.strptime(text, date_format)
    except ValueError:
        return False
    return True


def parse_date(text: str) -> str:
    """날짜 검사: ① 모양이 YYYY-MM-DD인지 ② 달력에 있는 날짜인지."""
    text = text.strip()
    if DATE_SHAPE.fullmatch(text) and _is_real_date(text, "%Y-%m-%d"):
        return text
    raise ValidationError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", "예: 2024-01-15")


def parse_month(text: str) -> str:
    """월 검사: ① 모양이 YYYY-MM인지 ② 1~12월인지."""
    text = text.strip()
    if MONTH_SHAPE.fullmatch(text) and _is_real_date(text, "%Y-%m"):
        return text
    raise ValidationError("월 형식이 올바르지 않습니다 (YYYY-MM).", "예: 2024-01")


def parse_type(text: str) -> str:
    """타입 검사: income(수입) 또는 expense(지출)만 허용합니다."""
    text = text.strip().lower()
    if text in TRANSACTION_TYPES:
        return text
    raise ValidationError(
        f"허용되지 않은 타입입니다: {text}",
        "수입이면 income, 지출이면 expense 를 입력하세요.",
    )


def parse_amount(text: str) -> int:
    """금액 검사: ① 정수인지 ② 0보다 큰지(양수)."""
    text = text.strip()
    if not text.removeprefix("-").isdigit():
        raise ValidationError(
            f"금액은 숫자로 입력해야 합니다: {text}",
            "예: 15000 (쉼표·소수점·단위 없이 숫자만)",
        )
    amount = int(text)
    if amount <= 0:
        raise ValidationError("금액은 0보다 커야 합니다 (양수).", "예: 15000")
    return amount


def parse_tags(text: str) -> list[str]:
    """'meal, friend' → ['meal', 'friend']. 태그는 선택 항목이라 오류가 없습니다."""
    return [tag.strip() for tag in text.split(",") if tag.strip()]


def parse_name(text: str) -> str:
    """카테고리 이름 검사: 비어 있으면 안 됩니다."""
    name = text.strip()
    if name:
        return name
    raise ValidationError("카테고리 이름이 비어 있습니다.", "예: food")


def parse_day(text: str) -> int:
    """[보너스] 반복 내역의 '매월 며칠' 검사: 1~31."""
    text = text.strip()
    if text.isdigit() and 1 <= int(text) <= 31:
        return int(text)
    raise ValidationError(
        f"날짜(일)는 1~31 사이 숫자여야 합니다: {text}",
        "예: 25 (31을 넣으면 짧은 달에는 마지막 날에 만들어집니다)",
    )
