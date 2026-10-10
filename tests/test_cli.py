"""CLI 테스트 — 실제로 `python -m budget_app ...`을 실행해서 출력과 종료 코드를 확인합니다."""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ALL_COMMANDS = [
    [],
    ["add"], ["list"], ["search"], ["summary"], ["update"], ["delete"],
    ["import"], ["export"], ["backup"],
    ["budget"], ["budget", "set"], ["budget", "list"],
    ["category"], ["category", "add"], ["category", "list"], ["category", "remove"],
    ["recurring"], ["recurring", "add"], ["recurring", "list"],
    ["recurring", "remove"], ["recurring", "apply"],
]


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.data_dir = self.dir / "data"

    def tearDown(self):
        self._tmp.cleanup()

    def run_app(self, *args: str, input_text: str = "") -> subprocess.CompletedProcess:
        command = [sys.executable, "-m", "budget_app", *args, "--data-dir", str(self.data_dir)]
        return subprocess.run(
            command, input=input_text, capture_output=True, text=True, cwd=PROJECT_ROOT
        )

    def add(self, date="2024-01-15", tx_type="expense", category="food", amount="15000", memo="점심", tags="meal"):
        answers = "\n".join([date, tx_type, category, amount, memo, tags]) + "\n"
        result = self.run_app("add", input_text=answers)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def assert_friendly_error(self, result, exit_code=1):
        self.assertEqual(result.returncode, exit_code)
        self.assertIn("[오류]", result.stderr)
        self.assertIn("[힌트]", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class HelpTest(CliTestCase):
    def test_every_command_has_help_with_double_dash_only(self):
        for command in ALL_COMMANDS:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "budget_app", *command, "--help"],
                    capture_output=True, text=True, cwd=PROJECT_ROOT,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("--help", result.stdout)
                self.assertIsNone(re.search(r"(?<![-\w])-h\b", result.stdout))  # -h 없음


class AddListTest(CliTestCase):
    def test_first_run_creates_default_categories_with_notice(self):
        result = self.run_app("category", "list")
        self.assertIn("[안내]", result.stdout)
        self.assertIn("- food", result.stdout)
        self.assertEqual(
            sorted(p.name for p in self.data_dir.glob("*.jsonl")),
            ["budgets.jsonl", "categories.jsonl", "recurring.jsonl", "transactions.jsonl"],
        )

    def test_add_prints_new_id_and_data_survives_restart(self):
        result = self.add()
        self.assertIn("[저장 완료] id=TX-000001", result.stdout)
        listed = self.run_app("list")  # 새 프로세스 = 프로그램 재실행
        self.assertIn("TX-000001", listed.stdout)
        self.assertIn("점심", listed.stdout)

    def test_add_asks_again_after_invalid_input(self):
        answers = "\n".join(["2024-13-40", "2024-01-15", "spend", "expense", "shopping", "food",
                             "-500", "15000", "점심", "meal"]) + "\n"
        result = self.run_app("add", input_text=answers)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[저장 완료] id=TX-000001", result.stdout)
        self.assertIn("날짜 형식이 올바르지 않습니다", result.stderr)
        self.assertIn("허용되지 않은 타입", result.stderr)
        self.assertIn("등록되지 않은 카테고리", result.stderr)
        self.assertIn("0보다 커야", result.stderr)

    def test_add_input_cancelled_exits_with_error_without_traceback(self):
        result = self.run_app("add", input_text="2024-13-40\n")
        self.assert_friendly_error(result)

    def test_list_latest_first_with_limit_and_more_notice(self):
        self.add(date="2024-01-10", memo="첫째")
        self.add(date="2024-01-20", memo="둘째")
        self.add(date="2024-01-15", memo="셋째")
        result = self.run_app("list", "--limit", "2")
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        rows = [line for line in lines if line.startswith("TX-")]
        self.assertEqual([row.split()[0] for row in rows], ["TX-000002", "TX-000003"])
        self.assertIn("--limit", result.stdout)

    def test_list_rejects_invalid_limit(self):
        self.assert_friendly_error(self.run_app("list", "--limit", "0"), exit_code=2)


class SearchSummaryBudgetTest(CliTestCase):
    def test_search_by_condition(self):
        self.add(category="food", memo="점심 김밥")
        self.add(category="transport", memo="버스", tags="")
        result = self.run_app("search", "--category", "transport")
        self.assertIn("버스", result.stdout)
        self.assertNotIn("김밥", result.stdout)

    def test_search_rejects_from_after_to(self):
        self.assert_friendly_error(self.run_app("search", "--from", "2024-02-01", "--to", "2024-01-01"))

    def test_budget_set_list_and_summary_warning(self):
        self.add(tx_type="income", category="salary", amount="3000000", memo="", tags="")
        self.add(category="rent", amount="150000")
        result = self.run_app("budget", "set", "--month", "2024-01", "--amount", "100000")
        self.assertIn("[저장 완료] 2024-01 예산 100000원", result.stdout)
        self.assertIn("2024-01", self.run_app("budget", "list").stdout)

        summary = self.run_app("summary", "--month", "2024-01", "--top", "3")
        self.assertEqual(summary.returncode, 0)
        for text in ["총 수입: 3000000원", "총 지출: 150000원", "잔액: 2850000원",
                     "예산: 100000원 (사용률 150.0%)", "[경고]", "지출 TOP", "1) rent 150000원"]:
            self.assertIn(text, summary.stdout)

    def test_summary_month_without_data(self):
        self.assertIn("데이터 없음", self.run_app("summary", "--month", "2030-01").stdout)

    def test_summary_invalid_month(self):
        self.assert_friendly_error(self.run_app("summary", "--month", "2024-13"))

    def test_summary_missing_month_option(self):
        self.assert_friendly_error(self.run_app("summary"), exit_code=2)


class UpdateDeleteCategoryTest(CliTestCase):
    def test_update_with_options(self):
        self.add()
        result = self.run_app("update", "--id", "TX-000001", "--amount", "20000", "--memo", "저녁")
        self.assertIn("[수정 완료] id=TX-000001", result.stdout)
        self.assertIn("20000", self.run_app("list").stdout)

    def test_update_without_fields(self):
        self.add()
        self.assert_friendly_error(self.run_app("update", "--id", "TX-000001"))

    def test_update_and_delete_unknown_id(self):
        for args in (["update", "--id", "TX-999999", "--amount", "1"], ["delete", "--id", "TX-999999"]):
            with self.subTest(args=args):
                result = self.run_app(*args)
                self.assert_friendly_error(result)
                self.assertIn("없는 데이터", result.stderr)

    def test_delete(self):
        self.add()
        self.assertIn("[삭제 완료] id=TX-000001", self.run_app("delete", "--id", "TX-000001").stdout)
        self.assertNotIn("TX-000001", self.run_app("list").stdout)

    def test_category_add_interactive_and_remove(self):
        result = self.run_app("category", "add", input_text="hobby\n")
        self.assertIn("[저장 완료] category=hobby", result.stdout)
        result = self.run_app("category", "remove", "--name", "hobby")
        self.assertIn("[삭제 완료] category=hobby", result.stdout)

    def test_category_remove_in_use_is_blocked(self):
        self.add(category="food")
        self.assert_friendly_error(self.run_app("category", "remove", "--name", "food"))


class ImportExportTest(CliTestCase):
    def test_import_reports_counts_and_reasons(self):
        csv_path = self.dir / "in.csv"
        csv_path.write_text(
            "date,type,category,amount,memo,tags\n"
            "2024-01-15,expense,food,15000,점심,meal\n"
            "2024-01-16,expense,food,abc,,\n",
            encoding="utf-8",
        )
        result = self.run_app("import", "--from", str(csv_path))
        self.assertEqual(result.returncode, 0)
        self.assertIn("[완료] imported=1, skipped=1", result.stdout)
        self.assertIn("3번째 줄", result.stdout)

    def test_import_missing_file(self):
        self.assert_friendly_error(self.run_app("import", "--from", str(self.dir / "none.csv")))

    def test_export(self):
        self.add()
        out = self.dir / "export.csv"
        result = self.run_app("export", "--out", str(out), "--month", "2024-01")
        self.assertIn("(1 records)", result.stdout)
        self.assertTrue(out.read_text(encoding="utf-8").startswith("date,type,category,amount,memo,tags"))

    def test_export_requires_period(self):
        self.assert_friendly_error(self.run_app("export", "--out", str(self.dir / "x.csv")))


class BonusAndLogTest(CliTestCase):
    def test_backup(self):
        self.add()
        result = self.run_app("backup")
        self.assertIn("[백업 완료]", result.stdout)
        self.assertEqual(len(list((self.data_dir / "backups").iterdir())), 1)

    def test_recurring_add_list_apply(self):
        answers = "income\nsalary\n3000000\n25\n월급\n\n"
        result = self.run_app("recurring", "add", input_text=answers)
        self.assertIn("[저장 완료] id=RC-001", result.stdout)
        self.assertIn("월급", self.run_app("recurring", "list").stdout)
        applied = self.run_app("recurring", "apply", "--month", "2024-01")
        self.assertIn("1건", applied.stdout)
        self.assertIn("2024-01-25", self.run_app("list").stdout)

    def test_decorator_writes_execution_log(self):
        self.run_app("list")
        self.run_app("delete", "--id", "TX-999999")
        log = (self.data_dir / "app.log").read_text(encoding="utf-8")
        self.assertIn("command=cmd_list exit_code=0", log)
        self.assertIn("command=cmd_delete exit_code=1", log)


if __name__ == "__main__":
    unittest.main()
