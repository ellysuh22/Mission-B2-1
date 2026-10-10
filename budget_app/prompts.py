"""
대화형 입력 — input()으로 하나씩 묻고, 틀리면 이유를 보여준 뒤 다시 묻습니다.

하는 일 : 질문 → 입력 → validators 함수로 검사 → 실패하면 [오류]/[힌트] 출력 후 다시 질문
안 하는 일: 저장 (cli가 입력받은 값을 services에 넘깁니다)
"""

import sys
from typing import Callable, TypeVar

from .errors import ValidationError
from .formatter import format_error

T = TypeVar("T")  # "어떤 타입이든" — parse 함수가 돌려주는 타입이 그대로 ask의 결과 타입이 됨


def ask(question: str, parse: Callable[[str], T]) -> T:
    """[요구 4.3] 올바른 값이 들어올 때까지 반복해서 묻습니다.

    parse: 입력 글자를 검사·변환하는 함수 (예: parse_date). 틀리면 ValidationError를 던짐.
    예) ask("금액(양수): ", parse_amount)  →  int 를 돌려줌
    """
    while True:
        text = input(question)
        try:
            return parse(text)
        except ValidationError as error:
            print(format_error(error.message, error.hint), file=sys.stderr)


def ask_category(categories: list[str]) -> str:
    """[요구 4.5] 등록된 카테고리만 받습니다. 없으면 목록을 보여주고 다시 묻습니다."""

    def parse_registered(text: str) -> str:
        name = text.strip()
        if name in categories:
            return name
        raise ValidationError(
            f"등록되지 않은 카테고리입니다: {name}",
            f"사용 가능: {', '.join(categories)} (새 카테고리는 category add 로 먼저 등록)",
        )

    return ask("카테고리: ", parse_registered)
