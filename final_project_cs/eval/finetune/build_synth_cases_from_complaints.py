"""Turn real data.go.kr consumer-complaint Q&A into synthetic eval cases,
same shape as build_synth_cases_from_orders.py, but using ORGANIC customer
message text instead of a handful of templates -- addressing the input-
diversity gap found in docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md §6.4
(v6's holdout had only 2 unique draft strings across 84 examples because
every synthetic case used templated messages driving the same deterministic
Team capability).

The "question" field is a real customer complaint (data.go.kr consumer
mediation cases). It is NOT tied to a specific order in our DB -- there is
no real order to look up for it -- so each complaint is paired with a
randomly sampled REAL Naver/Coupang order (same recent-date synthesis as
build_synth_cases_from_orders.py, for the same reason: real historical
paid_at dates are almost always outside the return window) purely to give
return_refund.py concrete facts to reason against. The complaint's own
"answer" field (real mediator reasoning) is NOT used as a training target --
it answers a DIFFERENT question (what the LAW says) than what
response.generate needs to produce (review a draft reply against OUR
evidence) and using it as a target would be answering from unrelated
context, exactly what this project's evidence discipline forbids.

Usage:
    python -m eval.finetune.build_synth_cases_from_complaints --out eval/finetune/synth_cases_from_complaints.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPLAINT_FILES = [
    "datasets/voc/data_go_kr_consumer_complaints/processed/return_refund_evidence_relevant_cases.jsonl",
    "datasets/voc/data_go_kr_consumer_complaints/processed/fulfillment_logistics_relevant_cases.jsonl",
]
ORDER_FILES = [
    "datasets/commerce/naver_order_history/processed/orders.jsonl",
    "datasets/commerce/coupang_order_history/processed/orders.jsonl",
]


def _load_jsonl(*paths: str) -> list[dict]:
    rows = []
    for path in paths:
        p = ROOT.parent / path
        if not p.exists():
            continue
        rows.extend(json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    return rows


def build(complaints: list[dict], orders: list[dict], *, limit: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    confirmed_orders = [o for o in orders if o.get("order_status") == "구매확정완료"]
    rng.shuffle(complaints)

    cases = []
    seen_seq = set()
    for complaint in complaints:
        seq = complaint.get("seq")
        if seq in seen_seq:  # both files can share the same underlying case
            continue
        seen_seq.add(seq)
        if not confirmed_orders:
            break
        order = rng.choice(confirmed_orders)
        product_name = (order.get("product") or {}).get("name") or "주문 상품"
        message = complaint["question"].strip()
        if not message:
            continue
        case_id = f"synth-complaint-{seq}"
        total_price = (order.get("product") or {}).get("total_price") or (order.get("payment") or {}).get("amount") or 0
        quantity = (order.get("product") or {}).get("quantity") or 1
        synthetic_ordered_at = (datetime.now(UTC) - timedelta(days=rng.randint(1, 4))).isoformat()
        cases.append({
            "case_id": case_id,
            "message": message,
            "channel": "web",
            "expected_intent": "return",
            "expected_issue_code": "return_period_check",
            "expected_sentiment": "neutral",
            "expected_next_action": "respond",
            "expected_capability": "return.check_eligibility",
            "notes": f"real data.go.kr complaint text (seq={seq}, category={complaint.get('item_category')}), "
                     f"paired with a real order for DB facts -- see build_synth_cases_from_complaints.py docstring",
            "_seed_order": {
                "order_no_source": str(order.get("order_id")),
                "total_cents": int(total_price),
                "item_count": int(quantity),
                "status": "delivered",
                "ordered_at": synthetic_ordered_at,
                "product_name": product_name,
            },
        })
        if len(cases) >= limit:
            break
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="eval/finetune/synth_cases_from_complaints.jsonl")
    parser.add_argument("--limit", type=int, default=140)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    complaints = _load_jsonl(*COMPLAINT_FILES)
    orders = _load_jsonl(*ORDER_FILES)
    cases = build(complaints, orders, limit=args.limit, seed=args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(json.dumps({"complaints_loaded": len(complaints), "orders_loaded": len(orders), "cases_written": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
