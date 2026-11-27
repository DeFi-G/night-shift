import unittest
import csv

from analytics import calculate, analyze_csv


class AnalyticsTests(unittest.TestCase):

    def test_exact_decimal_addition(self):
        self.assertEqual(
            calculate("add", "0.1", "0.2")["result"],
            "0.3"
        )

    def test_percentage(self):
        self.assertEqual(
            calculate("percent", "3", "6")["result"],
            "50"
        )

    def test_multiplication(self):
        self.assertEqual(
            calculate("multiply", "55", "12")["result"],
            "660"
        )

    def test_subtraction(self):
        self.assertEqual(
            calculate("subtract", "215", "55")["result"],
            "160"
        )

    def test_zero_denominator(self):
        with self.assertRaises(ValueError):
            calculate("divide", "10", "0")

    def test_unsupported_operation(self):
        with self.assertRaises(ValueError):
            calculate("execute", "1", "2")

    def test_expression_rejected(self):
        with self.assertRaises(ValueError):
            calculate("add", "1+2", "3")

    def test_nonfinite_rejected(self):
        for value in ("NaN", "Infinity", "1e999"):
            with self.assertRaises(ValueError):
                calculate("add", value, "1")

    def test_column_totals(self):
        data = b"Name,Views,Minutes\nA,2400,360\nB,5200,780\nC,1800,1440\nD,320,640\nE,280,560\n"
        result = analyze_csv(data)

        self.assertEqual(result["row_count"], 5)
        self.assertEqual(result["numeric"]["Views"]["sum"], "10000")
        self.assertEqual(result["numeric"]["Minutes"]["sum"], "3780")
        self.assertEqual(result["numeric"]["Minutes"]["maximum_line"], 4)

    def test_signed_statistics(self):
        data = b"Asset,Amount\nA,120\nB,-80\nC,200\nA,-50\nB,90\nC,-30\n"
        result = analyze_csv(data)["numeric"]["Amount"]

        self.assertEqual(result["positive_count"], 3)
        self.assertEqual(result["negative_count"], 3)
        self.assertEqual(result["positive_sum"], "410")
        self.assertEqual(result["negative_sum"], "-160")
        self.assertEqual(result["sum"], "250")
        self.assertEqual(result["maximum"], "200")
        self.assertEqual(result["minimum"], "-80")

    def test_grouped_totals(self):
        data = b"Item,Cost,Status\nA,70,Essential\nB,90,Essential\nC,43,Unused\nD,12,Duplicate\n"
        result = analyze_csv(data)

        self.assertEqual(result["numeric"]["Cost"]["sum"], "215")
        self.assertEqual(
            result["grouped"]["Status"]["Essential"]["totals"]["Cost"],
            "160"
        )
        self.assertEqual(
            result["grouped"]["Status"]["Unused"]["totals"]["Cost"],
            "43"
        )

    def test_quoted_csv(self):
        data = b'Item,Cost\n"Item, A",12.50\nB,2.50\n'
        result = analyze_csv(data)
        self.assertEqual(result["numeric"]["Cost"]["sum"], "15")

    def test_multiline_source_reference(self):
        data = b'Item,Cost\n"First\nItem",10\nSecond,20\n'
        result = analyze_csv(data)
        self.assertEqual(result["numeric"]["Cost"]["maximum_line"], 4)

    def test_duplicate_headers(self):
        with self.assertRaises(ValueError):
            analyze_csv(b"Cost,cost\n1,2\n")

    def test_malformed_row(self):
        with self.assertRaises(ValueError):
            analyze_csv(b"A,B\n1,2,3\n")

    def test_missing_numeric_value(self):
        result = analyze_csv(b"Name,Cost\nA,10\nB,\n")
        self.assertNotIn("Cost", result["numeric"])

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            analyze_csv(b"x" * 32769)

    def test_row_limit(self):
        with self.assertRaises(ValueError):
            analyze_csv(b"Cost\n" + b"1\n" * 201)

    def test_empty_dataset(self):
        with self.assertRaises(ValueError):
            analyze_csv(b"Cost\n")

    def test_zero_values(self):
        result = analyze_csv(b"Amount\n0\n1\n-1\n")
        self.assertEqual(result["numeric"]["Amount"]["zero_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)