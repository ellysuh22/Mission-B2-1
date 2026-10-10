"""
10만 건 실험 — "거래가 10만 건이 되면 어떻게 될까?"를 직접 측정합니다.

사용법 (프로젝트 폴더에서):
    python scripts/make_big_data.py                 # bigdata/ 폴더에 10만 건 만들고 측정
    python scripts/make_big_data.py --count 50000

측정 항목: 걸린 시간 + 최대 메모리
    1) list   : 스트리밍(제너레이터)으로 최신 10건 찾기
    2) 비교   : 파일 전체를 리스트로 한 번에 올린 뒤 정렬해서 최신 10건 찾기
    3) summary: 스트리밍으로 한 달 합계 계산
    4) id 발급: 새 id를 만들려고 파일 전체를 훑기 (병목 확인)
    5) update : 1건 수정하려고 파일 전체를 다시 쓰기 (병목 확인)
"""

import argparse
import random
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # budget_app 을 import 하기 위해

from budget_app.formatter import pad  # noqa: E402
from budget_app.models import SearchFilter, Transaction, make_tx_id  # noqa: E402
from budget_app.services import BudgetService  # noqa: E402
from budget_app.storage import write_jsonl_atomic  # noqa: E402


def generate(service: BudgetService, count: int) -> None:
    """가짜 거래 count건을 만들어 저장합니다. (제너레이터로 만들어서 메모리를 아낌)"""
    random.seed(0)
    categories = ["food", "transport", "rent", "etc"]

    def fake_records():
        for number in range(1, count + 1):
            tx = Transaction(
                id=make_tx_id(number),
                type="expense",
                date=f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                amount=random.randint(1000, 50000),
                category=random.choice(categories),
                memo="테스트 데이터",
            )
            yield tx.to_dict()

    write_jsonl_atomic(service.transactions.path, fake_records())


def measure(label: str, work) -> None:
    """work()를 실행해서 걸린 시간과 최대 메모리를 출력합니다."""
    start = time.perf_counter()
    work()
    elapsed = time.perf_counter() - start

    tracemalloc.start()  # 메모리 측정은 시간이 더 걸려서 따로 한 번 더 실행
    work()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"{pad(label, 40)} {elapsed:6.2f}초   최대 메모리 {peak / 1024 / 1024:7.2f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="10만 건 실험")
    parser.add_argument("--count", type=int, default=100_000)
    parser.add_argument("--data-dir", default="bigdata")
    args = parser.parse_args()

    service = BudgetService(Path(args.data_dir))
    service.ensure_default_categories()
    print(f"거래 {args.count}건 생성 중... ({args.data_dir}/)")
    generate(service, args.count)
    size_mb = service.transactions.path.stat().st_size / 1024 / 1024
    print(f"파일 크기: {size_mb:.1f} MB\n")

    measure("1) list: 스트리밍 + 최신 10건", lambda: service.search(SearchFilter(), 10))
    measure(
        "2) 비교: 전체를 리스트로 올린 뒤 정렬",
        lambda: sorted(service.transactions.iter_all(), key=Transaction.latest_key, reverse=True)[:10],
    )
    measure("3) summary: 스트리밍 합계", lambda: service.monthly_summary("2024-06", 3))
    measure("4) 새 id 발급 (전체 훑기)", service.transactions.last_number)
    first = service.find_transaction(make_tx_id(1))
    measure("5) update 1건 (전체 다시 쓰기)", lambda: service.transactions.update(first))


if __name__ == "__main__":
    main()
