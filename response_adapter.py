
import json
import re

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def parse_content(content):
    text = content.strip()
    lines = text.splitlines()

    if (
        len(lines) >= 3
        and lines[0].strip().lower() in ("```", "```json")
        and lines[-1].strip() == "```"
    ):
        text = chr(10).join(lines[1:-1]).strip()

    return json.loads(
        text,
        object_pairs_hook=unique_object
    )


SCHEMAS = {
    "inventory": set(),
    "inspect": set(),
    "read": {"path"},
    "search": {"query"}
}

def validate(action):
    if not isinstance(action, dict):
        raise ValueError("Expected an object")

    if set(action) == {"finish", "references"}:
        summary = action["finish"]
        refs = action["references"]

        if (
            not isinstance(summary, str)
            or not 1 <= len(summary.strip()) <= 3000
            or not isinstance(refs, list)
            or not 1 <= len(refs) <= 6
            or any(type(i) is not int or i < 1 for i in refs)
        ):
            raise ValueError("Invalid report schema")

        return action

    name = action.get("tool")

    if not isinstance(name, str) or name not in SCHEMAS:
        raise ValueError("Tool not allowed")

    required = SCHEMAS[name]

    if set(action) != required | {"tool"}:
        raise ValueError("Unexpected tool arguments")

    for key in required:
        value = action[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Invalid tool argument")

    return action


def normalize(message):
    if not isinstance(message, dict):
        raise ValueError("Invalid message")

    content = message.get("content", "")
    calls = message.get("tool_calls", [])

    if not isinstance(content, str) or len(content) > 8192:
        raise ValueError("Invalid content")

    if not isinstance(calls, list):
        raise ValueError("Invalid native tool calls")

    if content.strip() and calls:
        raise ValueError("Ambiguous response")

    if content.strip():
        action = parse_content(content)

    elif len(calls) == 1:
        call = calls[0]

        if not isinstance(call, dict):
            raise ValueError("Invalid call")

        fn = call.get("function")

        if not isinstance(fn, dict):
            raise ValueError("Invalid function")

        name = fn.get("name")
        args = fn.get("arguments")

        if isinstance(args, str):
            if len(args) > 8192:
                raise ValueError("Arguments too large")
            args = parse_content(args)

        if not isinstance(args, dict):
            raise ValueError("Invalid arguments")

        aliases = {
            "tool.inventory": "inventory",
            "tool.inspect": "inspect",
            "tool.read": "read",
            "tool.search": "search",
            "tool.finish": "finish"
        }

        if not isinstance(name, str):
            raise ValueError("Invalid function name")

        name = aliases.get(name, name)
        args = dict(args)

        if name == "read" and "max_lines" in args:
            limit = args.pop("max_lines")

            if type(limit) is not int or limit != 20:
                raise ValueError("Unsupported read limit")

        if name == "finish":
            action = args

            if set(action) != {"finish", "references"}:
                raise ValueError("Invalid finish arguments")

        elif isinstance(name, str) and name in SCHEMAS:
            if "tool" in args:
                raise ValueError("Conflicting tool argument")
            action = {"tool": name, **args}

        else:
            raise ValueError("Unknown native function")

    else:
        raise ValueError("Missing or multiple tool calls")

    output = json.dumps(validate(action), ensure_ascii=False)

    if len(output.encode("utf-8")) > 8192:
        raise ValueError("Normalized response too large")

    return output
