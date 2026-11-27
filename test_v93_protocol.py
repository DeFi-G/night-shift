
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import provider
from response_adapter import normalize
from inference_ledger import Ledger, MODEL

valid = {"finish": "Synthetic report.", "references": [2]}
plain = json.dumps(valid)
fenced = "```json\n" + plain + "\n```"

assert json.loads(normalize({"content": plain})) == valid
assert json.loads(normalize({"content": fenced})) == valid

invalid = [
    "not JSON",
    "Explanation:\n" + plain,
    '{"finish":"a","finish":"b","references":[1]}',
    '{"finish":"","references":[1]}',
    '{"finish":"a","references":["E1"]}',
    '{"finish":"a","references":[true]}',
    '{"finish":"a","references":[0]}',
    '{"finish":"a","references":[1],"extra":true}',
    '{"tool":"shell","command":"anything"}'
]

for content in invalid:
    try:
        normalize({"content": content})
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid response accepted")

print("PASS: Plain and fenced JSON accepted.")
print("PASS: Nine malformed responses rejected.")

context = {
    "assignment": "Synthetic reporting qualification",
    "evidence": [
        {"id": 1, "action": {"tool": "inventory"}, "result": []},
        {"id": 2, "action": {"tool": "read", "path": "a.txt"},
         "result": [{"text": "Synthetic evidence"}]}
    ],
    "requests_left": 1,
    "correction": ""
}

messages = [
    {"role": "system", "content": "Original investigation guide"},
    {"role": "user", "content": json.dumps(context)}
]

with tempfile.TemporaryDirectory() as temp:
    ledger = Ledger.initialize(Path(temp) / "ledger")

    with patch.object(provider, "Ledger", return_value=ledger), \
         patch.object(provider.http.client, "HTTPSConnection") as transport:

        client = transport.return_value
        response = client.getresponse.return_value
        response.status = 200

        cases = [
            ({"content": fenced}, True),
            ({"content": '{"finish":"a","references":[99]}'}, False),
            ({"content": '{"tool":"inventory"}'}, False),
            ({"content": "Malformed response"}, False),
            ({"content": plain}, True)
        ]

        for message, accepted in cases:
            response.read.return_value = json.dumps({
                "model": MODEL,
                "done": True,
                "prompt_eval_count": 100,
                "eval_count": 40,
                "message": message
            }).encode()

            pipe = MagicMock()
            provider.gateway(pipe, "offline-test", MODEL, messages)

            success, answer = pipe.send.call_args.args[0]
            assert success, answer
            action = json.loads(answer)

            if accepted:
                assert action == valid
            else:
                assert set(action) == {"_rejected"}
                assert action["_rejected"]

            request = json.loads(client.request.call_args.args[2])

            assert isinstance(request["format"], dict)
            assert request["format"]["type"] == "object"
            assert "tools" not in request
            assert request["stream"] is False
            assert "final report writer" in request["messages"][0]["content"]

        assert ledger.status()["requests"] == 5
        assert ledger.status()["unresolved"] == 0

print("PASS: Dedicated reporting request contract.")
print("PASS: Unknown evidence IDs rejected.")
print("PASS: Investigative actions rejected during reporting.")
print("PASS: Specific corrective feedback generated.")
print("PASS: Simulated receipts settled.")
