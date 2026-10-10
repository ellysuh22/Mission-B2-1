"""저장소(storage.py) 테스트 — 스트리밍 읽기 [요구 4.6], 원자적 저장 [요구 4.7]"""

import inspect
import tempfile
import unittest
from pathlib import Path

from budget_app.errors import BudgetAppError
from budget_app.models import Transaction
from budget_app.storage import (
    BudgetStore,
    CategoryStore,
    TransactionRepository,
    backup_data_dir,
    prepare_data_dir,
    read_csv_rows,
    read_jsonl,
    write_csv,
    write_jsonl_atomic,
)


def make_tx(number: int, date: str = "2024-01-15", category: str = "food") -> Transaction:
    return Transaction(
        id=f"TX-{number:06d}", type="expense", date=date, amount=1000 * number, category=category
    )


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class ReadJsonlTest(TempDirTestCase):
    def test_returns_generator_that_reads_line_by_line(self):
        path = self.dir / "a.jsonl"
        path.write_text('{"n": 1}\n\n{"n": 2}\n', encoding="utf-8")
        rows = read_jsonl(path)
        self.assertTrue(inspect.isgenerator(rows))
        self.assertEqual(list(rows), [{"n": 1}, {"n": 2}])

    def test_missing_file_reads_as_empty(self):
        self.assertEqual(list(read_jsonl(self.dir / "none.jsonl")), [])

    def test_broken_line_reports_file_and_line_number(self):
        path = self.dir / "a.jsonl"
        path.write_text('{"n": 1}\n{broken\n', encoding="utf-8")
        with self.assertRaises(BudgetAppError) as ctx:
            list(read_jsonl(path))
        self.assertIn("a.jsonl", ctx.exception.message)
        self.assertIn("2번째 줄", ctx.exception.message)
        self.assertTrue(ctx.exception.hint)


class AtomicWriteTest(TempDirTestCase):
    def test_writes_all_records(self):
        path = self.dir / "a.jsonl"
        write_jsonl_atomic(path, [{"n": 1}, {"memo": "점심"}])
        self.assertEqual(path.read_text(encoding="utf-8"), '{"n": 1}\n{"memo": "점심"}\n')

    def test_failure_in_the_middle_keeps_original_file(self):
        path = self.dir / "a.jsonl"
        path.write_text('{"n": 1}\n', encoding="utf-8")

        def records_that_fail():
            yield {"n": 2}
            raise RuntimeError("쓰는 도중 실패")

        with self.assertRaises(RuntimeError):
            write_jsonl_atomic(path, records_that_fail())
        self.assertEqual(path.read_text(encoding="utf-8"), '{"n": 1}\n')
        self.assertEqual([p.name for p in self.dir.iterdir()], ["a.jsonl"])  # 임시 파일도 정리됨


class TransactionRepositoryTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TransactionRepository(self.dir / "transactions.jsonl")

    def test_add_then_iterate_in_file_order(self):
        self.repo.add(make_tx(1))
        self.repo.add(make_tx(2))
        self.assertTrue(inspect.isgenerator(self.repo.iter_all()))
        self.assertEqual([tx.id for tx in self.repo.iter_all()], ["TX-000001", "TX-000002"])

    def test_last_number(self):
        self.assertEqual(self.repo.last_number(), 0)
        self.repo.add(make_tx(7))
        self.repo.add(make_tx(3))
        self.assertEqual(self.repo.last_number(), 7)

    def test_find(self):
        self.repo.add(make_tx(1))
        self.assertEqual(self.repo.find("TX-000001").amount, 1000)
        self.assertIsNone(self.repo.find("TX-999999"))

    def test_update_replaces_only_that_line(self):
        self.repo.add(make_tx(1))
        self.repo.add(make_tx(2))
        changed = make_tx(1)
        changed.amount = 99999
        self.repo.update(changed)
        self.assertEqual([tx.amount for tx in self.repo.iter_all()], [99999, 2000])

    def test_delete_removes_only_that_line(self):
        self.repo.add(make_tx(1))
        self.repo.add(make_tx(2))
        self.repo.delete("TX-000001")
        self.assertEqual([tx.id for tx in self.repo.iter_all()], ["TX-000002"])

    def test_add_many_appends_after_existing(self):
        self.repo.add(make_tx(1))
        self.repo.add_many([make_tx(2), make_tx(3)])
        self.assertEqual(self.repo.last_number(), 3)


class SmallStoresTest(TempDirTestCase):
    def test_category_store(self):
        store = CategoryStore(self.dir / "categories.jsonl")
        store.add("food")
        store.add("rent")
        store.remove("food")
        self.assertEqual(store.list_names(), ["rent"])

    def test_budget_store_overwrites_same_month(self):
        store = BudgetStore(self.dir / "budgets.jsonl")
        self.assertIsNone(store.get("2024-01"))
        store.set("2024-01", 500000)
        store.set("2024-02", 300000)
        store.set("2024-01", 400000)
        self.assertEqual(store.get("2024-01"), 400000)
        self.assertEqual(store.load_all(), {"2024-01": 400000, "2024-02": 300000})


class DataDirTest(TempDirTestCase):
    def test_prepare_creates_folder_and_files(self):
        data_dir = self.dir / "data"
        prepare_data_dir(data_dir)
        names = sorted(p.name for p in data_dir.iterdir())
        self.assertEqual(
            names, ["budgets.jsonl", "categories.jsonl", "recurring.jsonl", "transactions.jsonl"]
        )

    def test_backup_copies_data_files(self):
        prepare_data_dir(self.dir)
        (self.dir / "categories.jsonl").write_text('{"name": "food"}\n', encoding="utf-8")
        backup_dir = backup_data_dir(self.dir)
        self.assertEqual(
            (backup_dir / "categories.jsonl").read_text(encoding="utf-8"), '{"name": "food"}\n'
        )


class CsvTest(TempDirTestCase):
    def test_write_then_read(self):
        path = self.dir / "out.csv"
        count = write_csv(path, ["date", "memo"], [{"date": "2024-01-15", "memo": "점심, 커피"}])
        self.assertEqual(count, 1)
        self.assertEqual(
            list(read_csv_rows(path, ["date"])), [(2, {"date": "2024-01-15", "memo": "점심, 커피"})]
        )

    def test_missing_required_column(self):
        path = self.dir / "in.csv"
        path.write_text("date,memo\n2024-01-15,점심\n", encoding="utf-8")
        with self.assertRaises(BudgetAppError) as ctx:
            list(read_csv_rows(path, ["date", "amount"]))
        self.assertIn("amount", ctx.exception.message)

    def test_missing_file(self):
        with self.assertRaises(BudgetAppError):
            list(read_csv_rows(self.dir / "none.csv", ["date"]))

    def test_non_utf8_file(self):
        path = self.dir / "cp949.csv"
        path.write_bytes("date,memo\n2024-01-15,점심\n".encode("cp949"))
        with self.assertRaises(BudgetAppError) as ctx:
            list(read_csv_rows(path, ["date"]))
        self.assertIn("UTF-8", ctx.exception.message)

    def test_reads_excel_utf8_bom(self):
        path = self.dir / "bom.csv"
        path.write_text("date,memo\n2024-01-15,점심\n", encoding="utf-8-sig")
        self.assertEqual(list(read_csv_rows(path, ["date"]))[0][1]["date"], "2024-01-15")


if __name__ == "__main__":
    unittest.main()
