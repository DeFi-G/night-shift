import tempfile
import unittest
from pathlib import Path

from workspace import tool, digest
from report_verification import verify_analytical_evidence


class VerificationTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

        self.data = b"Item,Cost\nA,10\nB,20\n"
        self.path = self.root / "data.csv"
        self.path.write_bytes(self.data)

        self.manifest = {
            "files": [{
                "path": "data.csv",
                "bytes": len(self.data),
                "sha256": digest(self.data)
            }]
        }

    def entry(self, action):
        return {
            "id": 1,
            "action": action,
            "result": tool(self.root, self.manifest, action)
        }

    def verify(self, evidence):
        return verify_analytical_evidence(
            self.root, self.manifest, evidence, lambda: None
        )

    def test_csv_recomputed(self):
        result = self.verify([self.entry({
            "tool": "analyze_csv",
            "path": "data.csv"
        })])

        self.assertEqual(
            result["analytical_status"], "recomputed_match"
        )

        findings = result["analytical_findings"]

        self.assertEqual(
            findings[0]["result"]["analysis"]["numeric"]["Cost"]["sum"],
            "30"
        )

    def test_calculator_recomputed(self):
        result = self.verify([self.entry({
            "tool": "calculate",
            "operation": "multiply",
            "left": "12",
            "right": "55"
        })])

        self.assertEqual(
            result["analytical_findings"][0]["result"]["result"],
            "660"
        )

    def test_modified_result_rejected(self):
        entry = self.entry({
            "tool": "calculate",
            "operation": "add",
            "left": "10",
            "right": "20"
        })

        entry["result"]["result"] = "999"

        with self.assertRaises(RuntimeError):
            self.verify([entry])

    def test_modified_csv_rejected(self):
        entry = self.entry({
            "tool": "analyze_csv",
            "path": "data.csv"
        })

        self.path.write_bytes(b"Item,Cost\nA,999\n")

        with self.assertRaises(RuntimeError):
            self.verify([entry])

    def test_no_analytical_evidence(self):
        result = self.verify([])

        self.assertEqual(
            result["analytical_status"], "not_applicable"
        )
        self.assertEqual(
            result["analytical_evidence_count"], 0
        )

    def test_nonanalytical_evidence(self):
        result = self.verify([{
            "id": 1,
            "action": {"tool": "inventory"},
            "result": []
        }])

        self.assertEqual(
            result["analytical_evidence_count"], 0
        )

    def test_model_accuracy_not_certified(self):
        result = self.verify([])

        self.assertEqual(
            result["model_summary_accuracy"],
            "not_independently_verified"
        )

        self.assertEqual(
            result["recommendation_accuracy"],
            "not_independently_verified"
        )

    def test_source_preserved(self):
        self.verify([self.entry({
            "tool": "analyze_csv",
            "path": "data.csv"
        })])

        self.assertEqual(
            self.path.read_bytes(), self.data
        )

    def test_cancellation_propagates(self):
        class Cancelled(Exception):
            pass

        def check():
            raise Cancelled()

        with self.assertRaises(Cancelled):
            verify_analytical_evidence(
                self.root,
                self.manifest,
                [self.entry({
                    "tool": "analyze_csv",
                    "path": "data.csv"
                })],
                check
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
