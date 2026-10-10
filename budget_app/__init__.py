"""
나만의 용돈 기입장 — 파일(JSONL) 기반 콘솔 가계부.

계층 구조 (위에서 아래로만 호출합니다)
  ① cli.py        사람과 대화: 명령 해석, 입력, 출력
  ② services.py   기능 규칙: 검색, 요약, 예산, 카테고리, import/export
  ③ storage.py    파일 담당: JSONL 읽기(제너레이터) / 쓰기(원자적 저장)
  ④ models.py     데이터 모양: Transaction 등 dataclass

실행: python -m budget_app <command> [options]
"""
