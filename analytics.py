"""Bounded, deterministic numerical analysis for Night Shift."""

import csv
import io
import re

from decimal import Decimal, localcontext

MAX_BYTES = 32768
MAX_ROWS = 200
MAX_COLUMNS = 16
MAX_GROUPS = 12
MAX_CELL = 240

NUMBER = re.compile(
    r"[+-]?(?:[0-9]{1,15}(?:\.[0-9]{1,8})?|\.[0-9]{1,8})",
    re.ASCII
)


def number(value):
    if not isinstance(value, str):
        raise ValueError("Expected decimal text")

    value = value.strip()

    if not NUMBER.fullmatch(value):
        raise ValueError("Unsupported decimal value")

    return Decimal(value)


def display(value):
    if value == 0:
        return "0"

    return format(value.normalize(), "f")


def calculate(operation, left, right):
    a = number(left)
    b = number(right)

    with localcontext() as context:
        context.prec = 40

        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Division by zero")
            result = a / b
        elif operation == "percent":
            if b == 0:
                raise ValueError("Percentage denominator is zero")
            result = a / b * 100
        else:
            raise ValueError("Unsupported calculation")

        return {
            "operation": operation,
            "left": display(a),
            "right": display(b),
            "result": display(result),
            "precision": 40
        }


def parse_csv(data):
    if not isinstance(data, bytes):
        raise ValueError("Expected CSV bytes")

    if not 1 <= len(data) <= MAX_BYTES:
        raise ValueError("CSV exceeds analytical size limit")

    if b"\x00" in data:
        raise ValueError("Invalid CSV content")

    text = data.decode("utf-8-sig", errors="strict")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)

    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("CSV is empty") from None

    headers = [value.strip() for value in headers]

    if (
        not 1 <= len(headers) <= MAX_COLUMNS
        or any(not h or len(h) > 80 for h in headers)
        or len({h.casefold() for h in headers}) != len(headers)
    ):
        raise ValueError("Invalid or duplicate CSV headers")

    rows = []

    while True:
        start_line = reader.line_num + 1

        try:
            values = next(reader)
        except StopIteration:
            break

        if len(rows) >= MAX_ROWS:
            raise ValueError("CSV exceeds analytical row limit")

        if (
            len(values) != len(headers)
            or any(len(v) > MAX_CELL for v in values)
        ):
            raise ValueError("Invalid CSV row")

        rows.append({
            "line": start_line,
            "end_line": reader.line_num,
            "values": [v.strip() for v in values]
        })

    if not rows:
        raise ValueError("CSV contains no data rows")

    return headers, rows


def analyze_csv(data):
    headers, rows = parse_csv(data)

    numeric = {}
    categorical = {}

    with localcontext() as context:
        context.prec = 40

        for index, header in enumerate(headers):
            raw = [row["values"][index] for row in rows]

            try:
                values = [number(value) for value in raw]
            except ValueError:
                groups = list(dict.fromkeys(raw))

                if len(groups) <= MAX_GROUPS and all(groups):
                    categorical[header] = {
                        "index": index,
                        "groups": groups
                    }

                continue

            positive = [v for v in values if v > 0]
            negative = [v for v in values if v < 0]

            low = min(values)
            high = max(values)

            numeric[header] = {
                "index": index,
                "values": values,
                "statistics": {
                    "count": len(values),
                    "sum": display(sum(values, Decimal(0))),
                    "mean": display(sum(values, Decimal(0)) / len(values)),
                    "positive_count": len(positive),
                    "negative_count": len(negative),
                    "zero_count": values.count(Decimal(0)),
                    "positive_sum": display(sum(positive, Decimal(0))),
                    "negative_sum": display(sum(negative, Decimal(0))),
                    "minimum": display(low),
                    "maximum": display(high),
                    "minimum_line": rows[values.index(low)]["line"],
                    "maximum_line": rows[values.index(high)]["line"]
                }
            }

        grouped = {}

        for category, definition in categorical.items():
            groups = {}

            for label in definition["groups"]:
                indexes = [
                    i for i, row in enumerate(rows)
                    if row["values"][definition["index"]] == label
                ]

                groups[label] = {
                    "count": len(indexes),
                    "source_lines": [rows[i]["line"] for i in indexes],
                    "totals": {
                        column: display(sum(
                            (item["values"][i] for i in indexes),
                            Decimal(0)
                        ))
                        for column, item in numeric.items()
                    }
                }

            grouped[category] = groups

        return {
            "row_count": len(rows),
            "columns": headers,
            "numeric": {
                name: item["statistics"]
                for name, item in numeric.items()
            },
            "grouped": grouped,
            "non_numeric_columns": [
                name for name in headers if name not in numeric
            ],
            "scope": {
                "complete_file": True,
                "first_data_line": rows[0]["line"],
                "last_data_line": rows[-1]["end_line"],
                "decimal_precision": 40
            }
        }