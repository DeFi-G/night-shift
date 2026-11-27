import json

from workspace import tool


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False
    )


def verify_analytical_evidence(root, manifest, evidence, check):
    verified = []

    for entry in evidence:
        check()

        action = entry["action"]

        if action["tool"] not in ("calculate", "analyze_csv"):
            continue

        try:
            recomputed = tool(root, manifest, action)

            if canonical(recomputed) != canonical(entry["result"]):
                raise ValueError("Analytical result mismatch")

        except (ValueError, TypeError, OSError):
            raise RuntimeError(
                "Deterministic evidence verification failed"
            ) from None

        verified.append({
            "evidence_id": entry["id"],
            "tool": action["tool"],
            "status": "recomputed_match",
            "result": recomputed
        })

    return {
        "input_integrity": "verified",
        "analytical_status": (
            "recomputed_match" if verified else "not_applicable"
        ),
        "analytical_evidence_count": len(verified),
        "analytical_findings": verified,
        "model_summary_accuracy": "not_independently_verified",
        "recommendation_accuracy": "not_independently_verified"
    }
