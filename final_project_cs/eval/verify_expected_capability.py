"""Independent checks for the golden expected_capability labels."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval" / "datasets" / "golden.jsonl"

ALLOWED = {
    "order": {"order.verify", "order.create", "payment.status", "procurement.quote"},
    "shipping": {"fulfillment.track", "shipment.status", "shipment.exception"},
    "return": {"return.check_eligibility", "return.request", "refund.calculate"},
    "exchange": {"return.check_eligibility", "return.request", "refund.calculate"},
}
AUTOMATIC = {
    "order": "order.verify",
    "shipping": "fulfillment.track",
    "return": "return.check_eligibility",
    "exchange": "return.check_eligibility",
}
TARGET_PREFIXES = ("g-order-", "g-shipping-", "g-return-", "g-exchange-")


def rows():
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line]


def main():
    data = rows()
    target = [row for row in data if row["case_id"].startswith(TARGET_PREFIXES)]
    invalid = [
        (row["case_id"], row["expected_capability"])
        for row in target
        if row.get("expected_capability") is not None
        and row.get("expected_capability") not in ALLOWED[row["expected_intent"]]
    ]
    coverage = {
        intent: Counter(row.get("expected_capability") for row in target if row["expected_intent"] == intent)
        for intent in ALLOWED
    }
    missing = {
        intent: sorted(ALLOWED[intent] - set(counts) - {None})
        for intent, counts in coverage.items()
    }
    changed = [
        row["case_id"] for row in target
        if row.get("expected_capability") != AUTOMATIC[row["expected_intent"]]
    ]

    print(f"target_cases={len(target)}")
    print(f"allowed_value_check={'PASS' if not invalid else 'FAIL'} invalid={invalid}")
    print(f"coverage_counts={dict(coverage)}")
    print(f"coverage_check={'PASS' if not any(missing.values()) else 'FAIL'} missing={missing}")
    print(f"automatic_selection_different_count={len(changed)}")
    print(f"automatic_selection_different_case_ids={changed}")
    return 1 if invalid or any(missing.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
