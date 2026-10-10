"""출력 모양(formatter.py) 테스트 — [보너스] 표 정렬"""

import unittest

from budget_app.formatter import display_width, format_error, format_table


class FormatterTest(unittest.TestCase):
    def test_korean_takes_two_columns(self):
        self.assertEqual(display_width("abc"), 3)
        self.assertEqual(display_width("점심"), 4)

    def test_table_columns_line_up_with_korean(self):
        table = format_table(["메모", "금액"], [["점심", "15000"], ["coffee", "4500"]], right_columns=(1,))
        lines = table.splitlines()
        positions = [display_width(line[: line.index("|")]) for line in lines if "|" in line]
        self.assertEqual(len(set(positions)), 1)  # 모든 줄의 '|' 위치가 같음
        self.assertTrue(lines[-1].endswith(" 4500"))  # 금액은 오른쪽 정렬

    def test_error_has_cause_and_hint(self):
        self.assertEqual(format_error("원인", "힌트"), "[오류] 원인\n[힌트] 힌트")


if __name__ == "__main__":
    unittest.main()
