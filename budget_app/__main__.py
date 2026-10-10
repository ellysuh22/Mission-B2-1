"""실행 입구 — `python -m budget_app <command> [options]` 로 실행하면 이 파일이 시작됩니다."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())  # main()이 돌려준 종료 코드(0 = 성공, 그 외 = 오류)로 프로그램을 끝냄
