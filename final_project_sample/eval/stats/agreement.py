"""Compare human holdout labels with judge/system predictions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FIELDS = ("intent", "issue_code", "sentiment", "pass")
HUMAN_FIELDS = {"intent": "human_intent", "issue_code": "human_issue_code", "sentiment": "human_sentiment", "pass": "human_pass"}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _case_map(rows: list[dict], label: str) -> dict[str, dict]:
    ids = [row.get("case_id") for row in rows]
    if any(case_id is None for case_id in ids):
        raise ValueError(f"{label} contains a row without case_id")
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise ValueError(f"{label} contains duplicate case_id(s): {duplicates}")
    return dict(zip(ids, rows))


def align_rows(human_rows: list[dict], prediction_rows: list[dict]) -> list[tuple[dict, dict]]:
    human = _case_map(human_rows, "human labels")
    predictions = _case_map(prediction_rows, "predictions")
    missing = sorted(set(human) - set(predictions))
    extra = sorted(set(predictions) - set(human))
    if missing or extra:
        raise ValueError(f"case_id mismatch: missing_in_predictions={missing}; extra_in_predictions={extra}")
    return [(human[case_id], predictions[case_id]) for case_id in human]


def _prediction_value(row: dict, field: str) -> Any:
    prediction = row.get("prediction") or {}
    judge = row.get("judge") or {}
    if field == "pass":
        if "pass" in judge:
            return judge["pass"]
        if "pass" in row:
            return row["pass"]
        return prediction.get("pass")
    return row.get(field, prediction.get(field))


def _human_value(row: dict, field: str) -> Any:
    return row[HUMAN_FIELDS[field]]


def cohen_kappa(left: list[Any], right: list[Any]) -> float:
    """Return Cohen's kappa, with a deterministic value for constant labels."""
    if len(left) != len(right) or not left:
        raise ValueError("Cohen's kappa requires equally sized, non-empty observations")
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    categories = set(left) | set(right)
    expected = sum((left.count(category) / len(left)) * (right.count(category) / len(right)) for category in categories)
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def agreement(human_rows: list[dict], prediction_rows: list[dict]) -> dict[str, dict[str, float | int]]:
    aligned = align_rows(human_rows, prediction_rows)
    result: dict[str, dict[str, float | int]] = {"cases": {"n": len(aligned)}}
    for field in FIELDS:
        human_values = [_human_value(human, field) for human, _ in aligned]
        prediction_values = [_prediction_value(prediction, field) for _, prediction in aligned]
        matches = sum(a == b for a, b in zip(human_values, prediction_values))
        result[field] = {
            "exact_matches": matches,
            "n": len(aligned),
            "agreement": matches / len(aligned) if aligned else 0.0,
            "kappa": cohen_kappa(human_values, prediction_values) if aligned else 0.0,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human", required=True, help="Completed human-label JSONL")
    parser.add_argument("--predictions", required=True, help="Judge/system prediction JSONL")
    args = parser.parse_args()
    result = agreement(load_jsonl(args.human), load_jsonl(args.predictions))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
