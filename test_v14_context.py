import json
import unittest

from evidence_context import (
    automatic_action,
    bounded_messages,
    message_size
)
from inference_ledger import MAX_MESSAGE_BYTES
from provider import protocol_options, validate_reporting_answer


class ContextTests(unittest.TestCase):

    def messages(self, evidence, assignment="Analyze data"):
        return [
            {"role": "system", "content": "Analyze evidence."},
            {"role": "user", "content": json.dumps({
                "assignment": assignment,
                "evidence": evidence,
                "requests_left": 2,
                "correction": ""
            })}
        ]

    def entry(self, index, tool, result):
        return {
            "id": index,
            "action": {"tool": tool},
            "result": result
        }

    def test_small_context_unchanged(self):
        messages = self.messages([
            self.entry(1, "inventory", [])
        ])
        self.assertEqual(bounded_messages(messages), messages)

    def test_oversized_context_bounded(self):
        messages = self.messages([
            self.entry(1, "inventory", []),
            self.entry(2, "read", "x" * 20000)
        ])
        result = bounded_messages(messages)
        self.assertLessEqual(
            message_size(result), MAX_MESSAGE_BYTES
        )
        evidence = json.loads(result[-1]["content"])["evidence"]
        self.assertTrue(evidence[1]["result"]["omitted"])

    def test_original_evidence_preserved(self):
        messages = self.messages([
            self.entry(1, "read", "x" * 20000)
        ])
        original = json.dumps(messages)
        bounded_messages(messages)
        self.assertEqual(json.dumps(messages), original)

    def test_analytical_priority(self):
        messages = self.messages([
            self.entry(1, "read", "x" * 5000),
            self.entry(2, "analyze_csv", "y" * 5000)
        ])
        result = bounded_messages(messages)
        evidence = json.loads(result[-1]["content"])["evidence"]
        self.assertEqual(evidence[1]["result"], "y" * 5000)
        self.assertTrue(evidence[0]["result"]["omitted"])

    def test_unicode_serialized_limit(self):
        messages = self.messages([
            self.entry(1, "read", "\u00e9" * 3000)
        ])
        self.assertLessEqual(
            message_size(bounded_messages(messages)),
            MAX_MESSAGE_BYTES
        )

    def test_omitted_reference_rejected(self):
        messages = bounded_messages(self.messages([
            self.entry(1, "inventory", []),
            self.entry(2, "read", "x" * 20000)
        ]))

        with self.assertRaises(ValueError):
            validate_reporting_answer(
                '{"finish":"Answer","references":[2]}',
                messages
            )

    def test_six_evidence_entries(self):
        messages = self.messages([
            self.entry(i, "inventory", [])
            for i in range(1, 7)
        ])
        self.assertEqual(
            protocol_options(messages), {"format": "json"}
        )

    def test_automatic_csv(self):
        self.assertEqual(
            automatic_action({"files": [
                {"path": "data.csv", "bytes": 100}
            ]}),
            {"tool": "analyze_csv", "path": "data.csv"}
        )

    def test_automatic_text(self):
        self.assertEqual(
            automatic_action({"files": [
                {"path": "notes.txt", "bytes": 100}
            ]}),
            {"tool": "read", "path": "notes.txt"}
        )

    def test_oversized_csv_not_automatic(self):
        self.assertIsNone(automatic_action({"files": [
            {"path": "data.csv", "bytes": 32769}
        ]}))

    def test_multiple_files_not_automatic(self):
        self.assertIsNone(automatic_action({"files": [
            {"path": "a.csv", "bytes": 100},
            {"path": "b.csv", "bytes": 100}
        ]}))

    def test_no_files(self):
        self.assertIsNone(automatic_action({"files": []}))

    def test_metadata_limit(self):
        messages = self.messages(
            [self.entry(1, "inventory", [])],
            assignment="x" * 20000
        )
        with self.assertRaises(RuntimeError):
            bounded_messages(messages)


if __name__ == "__main__":
    unittest.main(verbosity=2)
