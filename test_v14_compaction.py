import json
import unittest

from analytics import analyze_csv
from evidence_context import (
    analytical_projections,
    bounded_messages,
    message_size
)
from inference_ledger import MAX_MESSAGE_BYTES
from provider import validate_reporting_answer


class CompactionTests(unittest.TestCase):

    def entry(self):
        rows = ["Category,Cost"]

        for i in range(200):
            rows.append(f"Group-{i % 4},{i + 1}")

        data = ("\n".join(rows) + "\n").encode("utf-8")

        return {
            "id": 1,
            "action": {
                "tool": "analyze_csv",
                "path": "data.csv"
            },
            "result": {
                "path": "data.csv",
                "sha256": "a" * 64,
                "analysis": analyze_csv(data)
            }
        }

    def messages(self, entry, assignment="Analyze data"):
        return [
            {"role": "system", "content": "Analyze evidence."},
            {"role": "user", "content": json.dumps({
                "assignment": assignment,
                "evidence": [entry],
                "requests_left": 1,
                "correction": ""
            })}
        ]

    def test_projection_levels(self):
        projections = list(analytical_projections(self.entry()))

        self.assertEqual(
            [p["result"]["projection"] for p in projections],
            [
                "compact",
                "numeric_statistics",
                "essential_statistics"
            ]
        )

    def test_totals_preserved(self):
        for entry in analytical_projections(self.entry()):
            stats = entry["result"]["analysis"]["numeric"]["Cost"]

            self.assertEqual(stats["sum"], "20100")
            self.assertEqual(stats["count"], 200)
            self.assertEqual(stats["maximum"], "200")
            self.assertEqual(stats["minimum"], "1")

    def test_group_totals_preserved(self):
        entry = self.entry()
        compact = next(analytical_projections(entry))

        original = entry["result"]["analysis"]["grouped"]
        projected = compact["result"]["analysis"]["grouped"]

        for category, groups in original.items():
            for label, group in groups.items():
                self.assertEqual(
                    projected[category][label]["totals"],
                    group["totals"]
                )
                self.assertNotIn(
                    "source_lines", projected[category][label]
                )

    def test_original_unchanged(self):
        entry = self.entry()
        before = json.dumps(entry, sort_keys=True)

        list(analytical_projections(entry))

        self.assertEqual(
            json.dumps(entry, sort_keys=True), before
        )

    def test_projection_scope(self):
        for entry in analytical_projections(self.entry()):
            result = entry["result"]

            self.assertTrue(result["omitted_details"])
            self.assertTrue(
                result["analysis"]["scope"]["complete_file"]
            )

    def test_nonanalytical_evidence_not_projected(self):
        entry = {
            "id": 1,
            "action": {"tool": "read"},
            "result": []
        }

        self.assertEqual(
            list(analytical_projections(entry)), []
        )

    def test_oversized_analytical_context(self):
        entry = self.entry()

        entry["result"]["analysis"]["grouped"][
            "Category"
        ]["Group-0"]["source_lines"] = list(range(10000))

        messages = self.messages(entry)

        self.assertGreater(
            message_size(messages), MAX_MESSAGE_BYTES
        )

        bounded = bounded_messages(messages)

        self.assertLessEqual(
            message_size(bounded), MAX_MESSAGE_BYTES
        )

        result = json.loads(
            bounded[-1]["content"]
        )["evidence"][0]["result"]

        self.assertEqual(result["projection"], "compact")

        self.assertEqual(
            result["analysis"]["numeric"]["Cost"]["sum"],
            "20100"
        )

    def test_projected_reference_allowed(self):
        entry = next(analytical_projections(self.entry()))

        answer = '{"finish":"Total is 20100.","references":[1]}'

        self.assertEqual(
            validate_reporting_answer(
                answer, self.messages(entry)
            ),
            answer
        )

    def test_impossible_projection_omitted(self):
        entry = self.entry()

        entry["result"]["analysis"]["columns"] = [
            "x" * 20000
        ]

        bounded = bounded_messages(self.messages(entry))

        result = json.loads(
            bounded[-1]["content"]
        )["evidence"][0]["result"]

        self.assertTrue(result["omitted"])

        with self.assertRaises(ValueError):
            validate_reporting_answer(
                '{"finish":"Answer","references":[1]}',
                bounded
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
