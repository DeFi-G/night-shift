import json
import unittest

from response_adapter import normalize
from provider import protocol_options, investigation_messages


class AuthorizationTests(unittest.TestCase):

    def accepted(self, action):
        result = normalize({"content": json.dumps(action)})
        self.assertEqual(json.loads(result), action)

    def rejected(self, action):
        with self.assertRaises(ValueError):
            normalize({"content": json.dumps(action)})

    def context(self, evidence, remaining):
        return [{"role": "user", "content": json.dumps({
            "assignment": "Analyze supplied evidence.",
            "evidence": evidence,
            "requests_left": remaining,
            "correction": ""
        })}]

    def test_csv_allowed(self):
        self.accepted({
            "tool": "analyze_csv", "path": "data.csv"
        })

    def test_calculator_operations(self):
        for operation in (
            "add", "subtract", "multiply", "divide", "percent"
        ):
            self.accepted({
                "tool": "calculate",
                "operation": operation,
                "left": "10",
                "right": "2"
            })

    def test_arbitrary_operation_rejected(self):
        self.rejected({
            "tool": "calculate",
            "operation": "execute",
            "left": "1",
            "right": "2"
        })

    def test_expression_rejected(self):
        self.rejected({
            "tool": "calculate",
            "operation": "add",
            "left": "1+2",
            "right": "3"
        })

    def test_numeric_argument_rejected(self):
        self.rejected({
            "tool": "calculate",
            "operation": "add",
            "left": 1,
            "right": "2"
        })

    def test_zero_denominator_rejected(self):
        self.rejected({
            "tool": "calculate",
            "operation": "percent",
            "left": "10",
            "right": "0"
        })

    def test_extra_arguments_rejected(self):
        self.rejected({
            "tool": "analyze_csv",
            "path": "data.csv",
            "command": "execute"
        })

    def test_missing_arguments_rejected(self):
        self.rejected({"tool": "analyze_csv"})

    def test_existing_tools_preserved(self):
        for action in (
            {"tool": "inventory"},
            {"tool": "inspect"},
            {"tool": "read", "path": "notes.txt"},
            {"tool": "search", "query": "TODO"}
        ):
            self.accepted(action)

    def test_analytical_evidence_allowed(self):
        evidence = [
            {
                "id": 1,
                "action": {"tool": "inventory"},
                "result": []
            },
            {
                "id": 2,
                "action": {
                    "tool": "analyze_csv",
                    "path": "data.csv"
                },
                "result": {}
            },
            {
                "id": 3,
                "action": {
                    "tool": "calculate",
                    "operation": "add",
                    "left": "1",
                    "right": "2"
                },
                "result": {"result": "3"}
            }
        ]

        messages = self.context(evidence, 2)

        self.assertEqual(
            protocol_options(messages), {"format": "json"}
        )

        guide = investigation_messages(messages)[0]["content"]

        self.assertIn("analyze_csv", guide)
        self.assertIn("calculate", guide)

        final = protocol_options(self.context(evidence, 1))

        self.assertIsInstance(final["format"], dict)
        self.assertNotIn("tools", final)

    def test_unknown_evidence_tool_rejected(self):
        evidence = [{
            "id": 1,
            "action": {"tool": "shell"},
            "result": {}
        }]

        with self.assertRaises(RuntimeError):
            protocol_options(self.context(evidence, 2))

    def test_report_preserved(self):
        self.accepted({
            "finish": "Calculated total is 3.",
            "references": [1, 2]
        })


if __name__ == "__main__":
    unittest.main(verbosity=2)
