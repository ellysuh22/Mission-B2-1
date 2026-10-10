"""입력 검증(validators.py) 테스트 — [요구 4.3]"""

import unittest

from budget_app.errors import ValidationError
from budget_app.validators import (
    parse_amount,
    parse_date,
    parse_day,
    parse_month,
    parse_name,
    parse_tags,
    parse_type,
)


class ParseDateTest(unittest.TestCase):
    def test_accepts_valid_date(self):
        self.assertEqual(parse_date(" 2024-01-15 "), "2024-01-15")

    def test_rejects_wrong_shape(self):
        for text in ["2024/01/15", "2024-1-5", "20240115", ""]:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_date(text)

    def test_rejects_date_not_on_calendar(self):
        for text in ["2024-13-40", "2023-02-29"]:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_date(text)

    def test_error_has_message_and_hint(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_date("2024-13-40")
        self.assertIn("YYYY-MM-DD", ctx.exception.message)
        self.assertIn("2024-01-15", ctx.exception.hint)


class ParseMonthTest(unittest.TestCase):
    def test_accepts_valid_month(self):
        self.assertEqual(parse_month("2024-01"), "2024-01")

    def test_rejects_invalid_month(self):
        for text in ["2024-13", "2024-1", "2024-01-01", ""]:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_month(text)


class ParseTypeTest(unittest.TestCase):
    def test_accepts_income_and_expense(self):
        self.assertEqual(parse_type("income"), "income")
        self.assertEqual(parse_type(" EXPENSE "), "expense")

    def test_rejects_other_type(self):
        with self.assertRaises(ValidationError):
            parse_type("spend")


class ParseAmountTest(unittest.TestCase):
    def test_accepts_positive_integer(self):
        self.assertEqual(parse_amount(" 15000 "), 15000)

    def test_rejects_zero_and_negative(self):
        for text in ["0", "-500"]:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_amount(text)

    def test_rejects_non_number(self):
        for text in ["abc", "15,000", "1.5", "", "--5"]:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_amount(text)


class ParseTagsTest(unittest.TestCase):
    def test_splits_by_comma_and_drops_empty(self):
        self.assertEqual(parse_tags(" meal, friend ,,"), ["meal", "friend"])

    def test_empty_input_means_no_tags(self):
        self.assertEqual(parse_tags(""), [])


class ParseNameTest(unittest.TestCase):
    def test_strips_name(self):
        self.assertEqual(parse_name("  food "), "food")

    def test_rejects_empty_name(self):
        with self.assertRaises(ValidationError):
            parse_name("   ")


class ParseDayTest(unittest.TestCase):
    def test_accepts_1_to_31(self):
        self.assertEqual(parse_day("25"), 25)

    def test_rejects_out_of_range(self):
        for text in ["0", "32", "abc"]:
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_day(text)


if __name__ == "__main__":
    unittest.main()
