"""서비스(services.py) 테스트 — 기능 규칙"""

import tempfile
import unittest
from pathlib import Path

from budget_app.errors import BudgetAppError
from budget_app.models import SearchFilter
from budget_app.services import DEFAULT_CATEGORIES, BudgetService


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.service = BudgetService(self.dir / "data")
        self.service.ensure_default_categories()

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, date="2024-01-15", tx_type="expense", category="food", amount=1000, memo="", tags=None):
        return self.service.add_transaction(
            date=date, tx_type=tx_type, category=category, amount=amount, memo=memo, tags=tags
        )


class CategoryTest(ServiceTestCase):
    def test_default_categories_created_only_once(self):
        self.assertEqual(self.service.list_categories(), DEFAULT_CATEGORIES)
        self.assertFalse(self.service.ensure_default_categories())

    def test_add_duplicate_category_fails(self):
        self.service.add_category("hobby")
        with self.assertRaises(BudgetAppError):
            self.service.add_category("hobby")

    def test_remove_unused_category(self):
        self.service.remove_category("etc")
        self.assertNotIn("etc", self.service.list_categories())

    def test_remove_category_in_use_by_transaction_is_blocked(self):
        self.add(category="food")
        with self.assertRaises(BudgetAppError) as ctx:
            self.service.remove_category("food")
        self.assertIn("1건", ctx.exception.message)
        self.assertIn("food", self.service.list_categories())

    def test_remove_category_in_use_by_recurring_rule_is_blocked(self):
        self.service.add_recurring(tx_type="expense", day=1, amount=500000, category="rent")
        with self.assertRaises(BudgetAppError):
            self.service.remove_category("rent")

    def test_remove_unknown_category_fails(self):
        with self.assertRaises(BudgetAppError):
            self.service.remove_category("nothing")


class AddTransactionTest(ServiceTestCase):
    def test_ids_increase(self):
        self.assertEqual(self.add().id, "TX-000001")
        self.assertEqual(self.add().id, "TX-000002")

    def test_unregistered_category_is_rejected(self):
        with self.assertRaises(BudgetAppError):
            self.add(category="shopping")


class SearchTest(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.add(date="2024-01-10", memo="점심 김밥", tags=["meal"])  # TX-000001
        self.add(date="2024-01-20", category="transport", memo="버스")  # TX-000002
        self.add(date="2024-01-10", tx_type="income", category="salary", amount=3000000)  # TX-000003
        self.add(date="2024-02-01", memo="저녁", tags=["meal", "friend"])  # TX-000004

    def ids(self, transactions):
        return [tx.id for tx in transactions]

    def test_latest_first_and_same_date_newer_id_first(self):
        found = self.service.search(SearchFilter(), limit=10)
        self.assertEqual(self.ids(found), ["TX-000004", "TX-000002", "TX-000003", "TX-000001"])

    def test_limit(self):
        self.assertEqual(self.ids(self.service.search(SearchFilter(), limit=2)), ["TX-000004", "TX-000002"])

    def test_each_condition(self):
        cases = [
            (SearchFilter(date_from="2024-01-15", date_to="2024-01-31"), ["TX-000002"]),
            (SearchFilter(category="food"), ["TX-000004", "TX-000001"]),
            (SearchFilter(type="income"), ["TX-000003"]),
            (SearchFilter(keyword="김밥"), ["TX-000001"]),
            (SearchFilter(tag="friend"), ["TX-000004"]),
            (SearchFilter(month="2024-02"), ["TX-000004"]),
        ]
        for condition, expected in cases:
            with self.subTest(condition=condition):
                self.assertEqual(self.ids(self.service.search(condition, limit=10)), expected)


class SummaryAndBudgetTest(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.add(tx_type="income", category="salary", amount=3000000)
        self.add(category="rent", amount=150000)
        self.add(category="food", amount=30000)
        self.add(category="food", amount=15000)
        self.add(category="transport", amount=20000)
        self.add(date="2024-02-01", category="food", amount=99999)  # 다른 달

    def test_totals_and_top_n(self):
        summary = self.service.monthly_summary("2024-01", top=2)
        self.assertEqual(summary.total_income, 3000000)
        self.assertEqual(summary.total_expense, 215000)
        self.assertEqual(summary.balance, 2785000)
        self.assertEqual(summary.top_expenses, [("rent", 150000), ("food", 45000)])
        self.assertIsNone(summary.budget)

    def test_month_without_data(self):
        self.assertEqual(self.service.monthly_summary("2024-03", top=3).count, 0)

    def test_budget_usage(self):
        self.service.set_budget("2024-01", 500000)
        summary = self.service.monthly_summary("2024-01", top=3)
        self.assertAlmostEqual(summary.budget_usage, 43.0)
        self.assertEqual(summary.over_budget, 0)

    def test_over_budget(self):
        self.service.set_budget("2024-01", 200000)
        self.assertEqual(self.service.monthly_summary("2024-01", top=3).over_budget, 15000)

    def test_list_budgets(self):
        self.service.set_budget("2024-02", 300000)
        self.service.set_budget("2024-01", 500000)
        self.assertEqual(self.service.list_budgets(), {"2024-01": 500000, "2024-02": 300000})


class UpdateDeleteTest(ServiceTestCase):
    def test_update_only_given_fields(self):
        tx = self.add(amount=1000, memo="점심")
        updated = self.service.update_transaction(tx.id, {"amount": 2000, "category": "etc"})
        self.assertEqual((updated.amount, updated.category, updated.memo), (2000, "etc", "점심"))
        self.assertEqual(self.service.find_transaction(tx.id).amount, 2000)

    def test_update_with_unregistered_category_fails(self):
        tx = self.add()
        with self.assertRaises(BudgetAppError):
            self.service.update_transaction(tx.id, {"category": "shopping"})

    def test_update_unknown_id_fails(self):
        with self.assertRaises(BudgetAppError) as ctx:
            self.service.update_transaction("TX-999999", {"amount": 1})
        self.assertIn("없는 데이터", ctx.exception.message)

    def test_delete(self):
        tx = self.add()
        self.service.delete_transaction(tx.id)
        self.assertEqual(self.service.search(SearchFilter(), limit=10), [])

    def test_delete_unknown_id_fails(self):
        with self.assertRaises(BudgetAppError) as ctx:
            self.service.delete_transaction("TX-999999")
        self.assertIn("없는 데이터", ctx.exception.message)


class ImportExportTest(ServiceTestCase):
    HEADER = "date,type,category,amount,memo,tags\n"

    def write_csv(self, body: str) -> Path:
        path = self.dir / "in.csv"
        path.write_text(self.HEADER + body, encoding="utf-8")
        return path

    def test_import_all_valid_rows(self):
        path = self.write_csv('2024-01-15,expense,food,15000,점심,"meal,friend"\n2024-01-16,income,salary,100,,\n')
        result = self.service.import_csv(path)
        self.assertEqual((result.imported, result.skipped), (2, []))
        first = self.service.find_transaction("TX-000001")
        self.assertEqual((first.memo, first.tags), ("점심", ["meal", "friend"]))

    def test_import_skips_broken_rows_and_reports_line_numbers(self):
        self.add()  # 기존 거래 TX-000001
        path = self.write_csv(
            "2024-01-15,expense,food,15000,,\n"  # 2번째 줄: 정상
            "2024-02-30,expense,food,15000,,\n"  # 3번째 줄: 없는 날짜
            "2024-01-15,expense,food,-5,,\n"  # 4번째 줄: 음수 금액
            "2024-01-15,spend,food,5,,\n"  # 5번째 줄: 잘못된 타입
            "2024-01-15,expense,shopping,5,,\n"  # 6번째 줄: 등록 안 된 카테고리
            "2024-01-16,expense,food,3000,,\n"  # 7번째 줄: 정상
        )
        result = self.service.import_csv(path)
        self.assertEqual(result.imported, 2)
        self.assertEqual([line.split("번째")[0] for line in result.skipped], ["3", "4", "5", "6"])
        self.assertEqual(self.service.transactions.last_number(), 3)  # 기존 1건 + 새 2건

    def test_strict_import_saves_nothing_if_any_row_is_broken(self):
        path = self.write_csv("2024-01-15,expense,food,15000,,\n2024-01-15,expense,food,0,,\n")
        with self.assertRaises(BudgetAppError):
            self.service.import_csv(path, strict=True)
        self.assertEqual(self.service.search(SearchFilter(), limit=10), [])

    def test_export_requires_period(self):
        with self.assertRaises(BudgetAppError):
            self.service.export_csv(self.dir / "out.csv", SearchFilter(category="food"))

    def test_export_then_import_round_trip(self):
        self.add(date="2024-01-15", memo="점심, 커피", tags=["meal", "cafe"])
        self.add(date="2024-02-01")
        out = self.dir / "out.csv"
        count = self.service.export_csv(out, SearchFilter(month="2024-01"))
        self.assertEqual(count, 1)
        self.assertEqual(out.read_text(encoding="utf-8").splitlines()[0], "date,type,category,amount,memo,tags")

        other = BudgetService(self.dir / "other")
        other.ensure_default_categories()
        result = other.import_csv(out)
        self.assertEqual(result.imported, 1)
        tx = other.find_transaction("TX-000001")
        self.assertEqual((tx.memo, tx.tags), ("점심, 커피", ["meal", "cafe"]))


class RecurringTest(ServiceTestCase):
    def test_apply_creates_transactions_once_per_month(self):
        self.service.add_recurring(tx_type="income", day=25, amount=3000000, category="salary", memo="월급")
        created = self.service.apply_recurring("2024-01")
        self.assertEqual([(tx.date, tx.memo) for tx in created], [("2024-01-25", "월급")])
        self.assertEqual(self.service.apply_recurring("2024-01"), [])  # 두 번째는 중복 생성 안 함

    def test_day_31_becomes_last_day_of_short_month(self):
        self.service.add_recurring(tx_type="expense", day=31, amount=500000, category="rent")
        self.assertEqual(self.service.apply_recurring("2024-02")[0].date, "2024-02-29")

    def test_rule_ids_and_remove(self):
        first = self.service.add_recurring(tx_type="expense", day=1, amount=1, category="rent")
        second = self.service.add_recurring(tx_type="expense", day=2, amount=2, category="food")
        self.assertEqual((first.id, second.id), ("RC-001", "RC-002"))
        self.service.remove_recurring("RC-001")
        self.assertEqual([rule.id for rule in self.service.list_recurring()], ["RC-002"])
        with self.assertRaises(BudgetAppError):
            self.service.remove_recurring("RC-001")

    def test_rule_with_unregistered_category_is_rejected(self):
        with self.assertRaises(BudgetAppError):
            self.service.add_recurring(tx_type="expense", day=1, amount=1, category="shopping")


class BackupTest(ServiceTestCase):
    def test_backup_contains_transactions(self):
        self.add()
        backup_dir = self.service.backup()
        self.assertIn("TX-000001", (backup_dir / "transactions.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
