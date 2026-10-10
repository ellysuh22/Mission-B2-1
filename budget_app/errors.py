"""
오류 정의 — 프로그램 전체에서 쓰는 '오류'의 모양을 정합니다.

하는 일 : 오류가 날 때 "원인(message)"과 "해결 힌트(hint)"를 함께 들고 다니게 합니다.
안 하는 일: 화면 출력 (출력은 decorators.handle_errors 가 합니다)
"""


class BudgetAppError(Exception):
    """[요구 4.14] 사용자에게 보여줄 오류. 원인 + 해결 힌트를 함께 가집니다."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(BudgetAppError):
    """입력값 검증 실패. 대화형 입력에서는 이 오류가 나면 그 항목을 다시 묻습니다."""
