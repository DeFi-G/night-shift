import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import provider
from app import Server
from engine import Engine
from inference_ledger import Ledger, MODEL
from test_night_shift import upload, until, memory_request

UAT = Path.home() / "Documents" / "Night-Shift-UAT"

PINS = {
    "01-history-paper.txt":
        "cd11e4ea50fe8b96397bd951a665b704645ef42902251da7ed8fef2a1e104b89",
    "02-social-metrics.csv":
        "887fa8e4c99366539afa846d3f3fde6337c6b1012165c0e2433090d06c7514b4",
    "03-trading-records.csv":
        "73ba9881a76f512ff010d61316891325bfa5f1f03feba2ede5a50cacfad9228d",
    "04-agent-blueprint.txt":
        "e3f90cd5a1d7865f40c4e6443c56867a53c35f6056e58a9c80b80f64224bb200",
    "05-business-expenses.csv":
        "df8c0c0c7b3221cc53b7fc4cd324a337a3db0f058a1c1c71927f9d6ba8a44ffb"
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def finish(text, refs):
    return {"finish": text, "references": refs}

def calc(operation, left, right):
    return {
        "tool": "calculate",
        "operation": operation,
        "left": left,
        "right": right
    }

class SyntheticGateway:
    mode = "ollama"

    def __init__(self, ledger, actions):
        self.ledger = ledger
        self.actions = iter(actions)
        self.calls = []

    def ask(self, messages, check):
        check()

        action = next(self.actions)

        with patch.object(
            provider, "Ledger", return_value=self.ledger
        ), patch.object(
            provider.http.client, "HTTPSConnection"
        ) as transport:

            client = transport.return_value
            response = client.getresponse.return_value
            response.status = 200

            response.read.return_value = json.dumps({
                "model": MODEL,
                "done": True,
                "prompt_eval_count": 100,
                "eval_count": 40,
                "message": {
                    "content": json.dumps(action)
                }
            }).encode()

            pipe = MagicMock()

            provider.gateway(
                pipe, "offline-test", MODEL, messages
            )

            success, answer = pipe.send.call_args.args[0]

            assert success, answer

            request = json.loads(
                client.request.call_args.args[2]
            )

            assert request["model"] == MODEL
            assert request["stream"] is False
            assert "tools" not in request
            assert request["options"]["num_predict"] == 512
            assert request["options"]["num_ctx"] == 8192

            context = json.loads(
                request["messages"][-1]["content"]
            )

            self.calls.append(context)

            check()
            return answer


class LifecycleTests(unittest.TestCase):

    def run_assignment(
        self, name, assignment, actions, expected_tool
    ):
        source = UAT / name
        original = source.read_bytes()

        self.assertEqual(sha(original), PINS[name])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            ledger = Ledger.initialize(root / "ledger")
            intelligence = SyntheticGateway(ledger, actions)

            engine = Engine(
                root / "runtime", intelligence, seconds=15
            )

            engine.start()

            try:
                with Server(
                    engine, "fixture-local-password", 0
                ) as server:

                    payload = {
                        "assignment": assignment,
                        "files": [upload(name, original)],
                        "cloud_consent": True
                    }

                    status, body = memory_request(
                        server, "POST", "/api/jobs", payload
                    )

                    self.assertEqual(status, 202)
                    job = json.loads(body)["id"]

                    # No connected browser is required.
                    completed = until(
                        lambda: engine.get(job),
                        "COMPLETED"
                    )

                    report = completed["report"]
                    path = "/api/jobs/" + job

                    status, raw = memory_request(
                        server, "GET", path + "/report.json"
                    )

                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(raw), report)

                    status, raw = memory_request(
                        server, "GET", path + "/report.md"
                    )

                    self.assertEqual(status, 200)
                    self.assertIn(
                        b"Deterministic verification", raw
                    )

                    states = [
                        e["state"] for e in completed["events"]
                    ]

                    self.assertEqual(
                        states[:3],
                        ["READY", "QUEUED", "CLOCKED_IN"]
                    )

                    self.assertEqual(
                        states[-2:], ["VERIFYING", "COMPLETED"]
                    )

                    evidence = report["evidence"]

                    self.assertEqual(
                        evidence[0]["action"]["tool"],
                        "inventory"
                    )

                    self.assertEqual(
                        evidence[1]["action"]["tool"],
                        expected_tool
                    )

                    self.assertEqual(
                        intelligence.calls[0]["evidence"][1]
                        ["action"]["tool"],
                        expected_tool
                    )

                    verification = report["verification"]

                    self.assertEqual(
                        verification["input_integrity"],
                        "verified"
                    )

                    self.assertEqual(
                        verification["model_summary_accuracy"],
                        "not_independently_verified"
                    )

                    self.assertEqual(
                        verification["recommendation_accuracy"],
                        "not_independently_verified"
                    )

                    self.assertEqual(
                        report["inference_requests"],
                        len(actions)
                    )

                    self.assertLessEqual(len(actions), 5)

                    self.assertEqual(
                        ledger.status()["requests"],
                        len(actions)
                    )

                    self.assertEqual(
                        ledger.status()["unresolved"], 0
                    )

                    self.assertEqual(
                        (engine.root / job / "originals" /
                         name).read_bytes(),
                        original
                    )

                    self.assertEqual(
                        (engine.root / job / "project" /
                         name).read_bytes(),
                        original
                    )

                    self.assertEqual(
                        source.read_bytes(), original
                    )

                    for finding in verification[
                        "analytical_findings"
                    ]:
                        self.assertEqual(
                            finding["status"],
                            "recomputed_match"
                        )

                        self.assertEqual(
                            finding["result"],
                            evidence[
                                finding["evidence_id"] - 1
                            ]["result"]
                        )

                    print(
                        "LIFECYCLE PASS:",
                        name,
                        "requests:", len(actions),
                        "evidence:", len(evidence),
                        "verification:",
                        verification["analytical_status"]
                    )

                    return report

            finally:
                engine.close()

    def test_history_paper(self):
        report = self.run_assignment(
            "01-history-paper.txt",
            "Proofread the history paper and cite source lines.",
            [finish(
                "Synthetic proofreading report. "
                "Review spelling and grammar using E2.",
                [2]
            )],
            "read"
        )

        self.assertEqual(
            report["verification"]["analytical_status"],
            "not_applicable"
        )

    def test_social_metrics(self):
        report = self.run_assignment(
            "02-social-metrics.csv",
            "Analyze platform performance and calculate totals.",
            [finish(
                "Synthetic analytical report. See E2.",
                [2]
            )],
            "analyze_csv"
        )

        stats = report["evidence"][1]["result"]["analysis"]

        self.assertEqual(stats["row_count"], 5)

        for column, total in {
            "Views": "10000",
            "WatchMinutes": "3780",
            "NewFollowers": "88",
            "Posts": "34"
        }.items():
            self.assertEqual(
                stats["numeric"][column]["sum"], total
            )

        self.assertEqual(
            report["verification"]["analytical_status"],
            "recomputed_match"
        )

    def test_trading_records(self):
        report = self.run_assignment(
            "03-trading-records.csv",
            "Analyze historical trading performance.",
            [
                calc("subtract", "250", "30"),
                calc("percent", "3", "6"),
                finish(
                    "Synthetic trading report. See E2-E4.",
                    [2, 3, 4]
                )
            ],
            "analyze_csv"
        )

        evidence = report["evidence"]
        stats = evidence[1]["result"]["analysis"]["numeric"]
        pnl = stats["GrossPnL"]

        self.assertEqual(pnl["count"], 6)
        self.assertEqual(pnl["sum"], "250")
        self.assertEqual(pnl["positive_count"], 3)
        self.assertEqual(pnl["negative_count"], 3)
        self.assertEqual(pnl["positive_sum"], "410")
        self.assertEqual(pnl["negative_sum"], "-160")
        self.assertEqual(pnl["minimum"], "-80")
        self.assertEqual(pnl["maximum"], "200")
        self.assertEqual(stats["Fee"]["sum"], "30")
        self.assertEqual(evidence[2]["result"]["result"], "220")
        self.assertEqual(evidence[3]["result"]["result"], "50")

        self.assertEqual(
            report["verification"]["analytical_evidence_count"],
            3
        )

    def test_agent_blueprint(self):
        report = self.run_assignment(
            "04-agent-blueprint.txt",
            "Review architecture and operational safeguards.",
            [
                {"tool": "inspect"},
                {"tool": "search", "query": "None specified"},
                {"tool": "search", "query": "Permissions"},
                {"tool": "search", "query": "Execution"},
                finish(
                    "Synthetic architecture report. "
                    "Review the collected safeguards evidence.",
                    [2, 4, 5, 6]
                )
            ],
            "read"
        )

        self.assertEqual(report["inference_requests"], 5)
        self.assertEqual(len(report["evidence"]), 6)

    def test_business_expenses(self):
        report = self.run_assignment(
            "05-business-expenses.csv",
            "Analyze expenses and potential savings.",
            [
                calc("add", "43", "12"),
                calc("subtract", "215", "55"),
                calc("multiply", "55", "12"),
                calc("percent", "55", "215"),
                finish(
                    "Synthetic expense report. See E2-E6.",
                    [2, 3, 4, 5, 6]
                )
            ],
            "analyze_csv"
        )

        evidence = report["evidence"]
        analysis = evidence[1]["result"]["analysis"]

        self.assertEqual(
            analysis["numeric"]["MonthlyCost"]["sum"],
            "215"
        )

        self.assertEqual(
            evidence[2]["result"]["result"], "55"
        )

        self.assertEqual(
            evidence[3]["result"]["result"], "160"
        )

        self.assertEqual(
            evidence[4]["result"]["result"], "660"
        )

        from decimal import Decimal

        percentage = Decimal(
            evidence[5]["result"]["result"]
        )

        self.assertEqual(
            percentage.quantize(Decimal("0.01")),
            Decimal("25.58")
        )

        self.assertEqual(
            report["verification"]["analytical_evidence_count"],
            5
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)