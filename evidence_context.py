import json

from inference_ledger import MAX_MESSAGE_BYTES


def message_size(messages):
    return len(json.dumps(
        messages, ensure_ascii=True
    ).encode("utf-8"))


def analytical_projections(entry):
    if entry["action"]["tool"] != "analyze_csv":
        return

    result = entry["result"]

    if not isinstance(result, dict):
        return

    analysis = result.get("analysis")

    if not isinstance(analysis, dict):
        return

    base = {
        "path": result["path"],
        "sha256": result["sha256"]
    }

    grouped = {
        category: {
            label: {
                "count": group["count"],
                "totals": group["totals"]
            }
            for label, group in groups.items()
        }
        for category, groups in analysis["grouped"].items()
    }

    compact = {
        **analysis,
        "grouped": grouped
    }

    yield {
        "id": entry["id"],
        "action": entry["action"],
        "result": {
            **base,
            "projection": "compact",
            "omitted_details": ["group source line lists"],
            "analysis": compact
        }
    }

    yield {
        "id": entry["id"],
        "action": entry["action"],
        "result": {
            **base,
            "projection": "numeric_statistics",
            "omitted_details": ["all grouped statistics"],
            "analysis": {
                key: value
                for key, value in analysis.items()
                if key != "grouped"
            }
        }
    }

    yield {
        "id": entry["id"],
        "action": entry["action"],
        "result": {
            **base,
            "projection": "essential_statistics",
            "omitted_details": [
                "all grouped statistics",
                "means",
                "positive and negative sums and counts",
                "zero counts"
            ],
            "analysis": {
                "row_count": analysis["row_count"],
                "columns": analysis["columns"],
                "numeric": {
                    column: {
                        key: stats[key]
                        for key in (
                            "count", "sum",
                            "minimum", "maximum",
                            "minimum_line", "maximum_line"
                        )
                    }
                    for column, stats in analysis["numeric"].items()
                },
                "non_numeric_columns":
                    analysis["non_numeric_columns"],
                "scope": analysis["scope"]
            }
        }
    }


def bounded_messages(messages):
    if message_size(messages) <= MAX_MESSAGE_BYTES:
        return messages

    context = json.loads(messages[-1]["content"])
    original = context["evidence"]

    projected = dict(context)

    projected["evidence"] = [
        {
            "id": entry["id"],
            "action": entry["action"],
            "result": {
                "omitted": True,
                "reason": "Inference context limit"
            }
        }
        for entry in original
    ]

    guide = messages[0]["content"] + (
        "\nEvidence marked omitted is unavailable for reasoning. "
        "Do not cite omitted results as support. "
        "Explicitly state material evidence limitations. "
        "Projected analytical evidence contains only selected facts. "
        "Do not infer omitted statistics or source details. "
        "Complete file scope describes computation, not context visibility."
    )

    def render():
        return [
            {"role": "system", "content": guide},
            {"role": "user", "content": json.dumps(
                projected, ensure_ascii=False
            )}
        ]

    if message_size(render()) > MAX_MESSAGE_BYTES:
        raise RuntimeError(
            "Assignment metadata exceeds inference context limit"
        )

    order = sorted(
        range(len(original)),
        key=lambda i: (
            original[i]["action"]["tool"] in (
                "calculate", "analyze_csv"
            ),
            i
        ),
        reverse=True
    )

    for index in order:
        previous = projected["evidence"][index]
        projected["evidence"][index] = original[index]

        if message_size(render()) > MAX_MESSAGE_BYTES:
            projected["evidence"][index] = previous

            for candidate in analytical_projections(original[index]):
                projected["evidence"][index] = candidate

                if message_size(render()) <= MAX_MESSAGE_BYTES:
                    break

                projected["evidence"][index] = previous

    return render()


def automatic_action(manifest):
    files = manifest["files"]

    if len(files) != 1:
        return None

    row = files[0]
    path = row["path"]
    size = row["bytes"]

    if path.lower().endswith(".csv"):
        if 0 < size <= 32768:
            return {"tool": "analyze_csv", "path": path}

    elif path.lower().endswith((".txt", ".md")):
        if 0 < size <= 4096:
            return {"tool": "read", "path": path}

    return None
