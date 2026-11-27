
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import provider
from inference_ledger import Ledger, MODEL

context = {
    "assignment": "Offline V14 protocol qualification",
    "evidence": [
        {
            "id": 1,
            "action": {"tool": "inventory"},
            "result": ["a.txt"]
        },
        {
            "id": 2,
            "action": {"tool": "read", "path": "a.txt"},
            "result": [{"text": "Synthetic evidence"}]
        }
    ],
    "requests_left": 3,
    "correction": ""
}

def messages(remaining):
    data = dict(context, requests_left=remaining)
    return [
        {"role": "system", "content": "Original guide"},
        {"role": "user", "content": json.dumps(data)}
    ]

assert provider.protocol_options(messages(3)) == {"format": "json"}
assert isinstance(provider.protocol_options(messages(1))["format"], dict)

cases = [
    (3, {"content": '{"tool":"read","path":"a.txt"}'}, True),
    (3, {"content": '{"finish":"Report","references":[2]}'}, True),
    (3, {"content": '{"finish":"Report","references":[99]}'}, False),
    (3, {"content": "", "tool_calls": [
        {"function": {"name": "inspect", "arguments": {}}}
    ]}, False),
    (1, {"content": '{"tool":"inventory"}'}, False),
    (1, {"content": '{"finish":"Report","references":[2]}'}, True),
    (3, {"content": '{"tool":"shell","command":"test"}'}, False),
    (3, {"content": '{"tool":"read","path":"a.txt","extra":1}'}, False),
    (1, {"content": '{"finish":"Truncated'}, False),
    (1, {"content": '{"finish":"Report","references":[true]}'}, False)
]

for number, (remaining, message, accepted) in enumerate(cases, 1):
    with tempfile.TemporaryDirectory() as temp:
        ledger = Ledger.initialize(Path(temp) / "ledger")

        with patch.object(provider, "Ledger", return_value=ledger), \
             patch.object(provider.http.client, "HTTPSConnection") as transport:

            client = transport.return_value
            response = client.getresponse.return_value
            response.status = 200

            response.read.return_value = json.dumps({
                "model": MODEL,
                "done": True,
                "prompt_eval_count": 100,
                "eval_count": 40,
                "message": message
            }).encode()

            pipe = MagicMock()

            provider.gateway(
                pipe, "offline-test", MODEL, messages(remaining)
            )

            success, answer = pipe.send.call_args.args[0]
            assert success, answer

            action = json.loads(answer)

            assert ("_rejected" not in action) == accepted

            request = json.loads(client.request.call_args.args[2])

            assert "format" in request
            assert "tools" not in request
            assert request["stream"] is False
            assert request["options"]["num_predict"] == 512
            assert request["options"]["num_ctx"] == 8192

            assert ledger.status()["requests"] == 1
            assert ledger.status()["unresolved"] == 0

    print(f"PASS: V14 protocol case {number:02d}")

print("PASS: V14 structured protocol 10/10")
print("No live inference requested")
