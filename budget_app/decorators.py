"""
[요구 4.13] 데코레이터 — 모든 명령에 공통으로 필요한 기능(공통 관심사)을 분리합니다.

모든 명령(add, list, ...)에 똑같이 필요한 일 두 가지:
  1) @handle_errors  : 오류가 나면 스택트레이스 대신 "[오류] 원인 / [힌트] 해결법"을 보여주고
                       종료 코드 1을 돌려줍니다.
  2) @log_execution  : 어떤 명령을 실행했고, 결과(종료 코드)가 무엇이고, 몇 초 걸렸는지
                       data/app.log 에 기록합니다.

이 코드를 명령 함수마다 복사해 넣지 않고, 함수 위에 @ 한 줄만 붙여서 재사용합니다.
→ 명령 함수에는 '그 명령의 핵심 일'만 남아 읽기 쉬워집니다.
"""

import functools
import logging
import sys
import time
from typing import Callable

from .errors import BudgetAppError
from .formatter import format_error

logger = logging.getLogger("budget_app")


def handle_errors(func: Callable[..., int]) -> Callable[..., int]:
    """오류를 잡아서 친절한 메시지로 바꾸고, 종료 코드 1을 돌려줍니다. [요구 4.14]"""

    @functools.wraps(func)  # 감싼 뒤에도 원래 함수 이름(cmd_add 등)이 유지되게 함
    def wrapper(*args, **kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except BudgetAppError as error:  # 우리가 예상한 오류 (원인 + 힌트를 가지고 있음)
            print(format_error(error.message, error.hint), file=sys.stderr)
        except (KeyboardInterrupt, EOFError):  # Ctrl+C, Ctrl+D 로 입력을 끊은 경우
            print(format_error("입력이 중단되었습니다.", "명령을 처음부터 다시 실행해 주세요."), file=sys.stderr)
        except OSError as error:  # 파일/폴더 문제 (권한, 경로 등)
            print(
                format_error(
                    f"파일을 읽거나 쓸 수 없습니다: {error.filename or error}",
                    "경로가 맞는지, 폴더가 있는지, 권한이 있는지 확인하세요.",
                ),
                file=sys.stderr,
            )
        except Exception as error:  # 예상하지 못한 오류도 스택트레이스 없이 안내
            print(
                format_error(
                    f"예상하지 못한 오류가 발생했습니다: {error}",
                    "입력값을 확인하고 다시 실행해 주세요. 반복되면 data/backups 로 복원하세요.",
                ),
                file=sys.stderr,
            )
        return 1

    return wrapper


def log_execution(func: Callable[..., int]) -> Callable[..., int]:
    """명령 이름, 종료 코드, 걸린 시간을 로그 파일(data/app.log)에 남깁니다."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> int:
        start = time.perf_counter()
        exit_code = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info("command=%s exit_code=%d elapsed=%.3fs", func.__name__, exit_code, elapsed)
        return exit_code

    return wrapper
