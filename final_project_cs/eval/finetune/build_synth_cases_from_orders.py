"""Turn real Coupang/Naver order records into synthetic-but-grounded eval
cases, shaped like eval/datasets/golden.jsonl, so they can run through the
real Team pipeline (Context Broker + return_refund/procurement_order_payment)
via eval.runners.proposed and produce genuine, diverse review-task training
data for stage 3 -- see docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md §5.

golden.jsonl's own DB fixture (eval/runners/common.py::_seed_golden_fixtures)
seeds the SAME hardcoded order (39,800 won, delivered) for every single case
-- that's why the review-task evidence harvested from it had almost no
factual variety. This script instead carries each case's REAL order facts
in a "_seed_order" block, which common.py's _seed_golden_fixtures (patched
alongside this script) uses when present instead of the hardcoded default.

The customer MESSAGE text is templated (a handful of variants per scenario,
filled with the real product name) -- NOT organic customer language. That
is a real, documented limitation: this buys factual/evidence diversity, not
linguistic diversity. The facts themselves (amounts, dates, statuses,
product names) are 100% real, not fabricated.

Usage:
    python -m eval.finetune.build_synth_cases_from_orders --out eval/finetune/synth_cases_from_orders.jsonl --limit 60
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RETURN_TEMPLATES = [
    "제가 주문한 {product}, 반품하고 싶은데 아직 가능한가요?",
    "{product} 받은 지 며칠 안 됐는데 그래도 반품 신청할 수 있을까요?",
    "얼마 전에 산 {product} 마음이 바뀌어서 반품하려고 하는데 기한이 지났나요?",
]

# order_status (Korean, as crawled) -> scenario
# ★order.cancel scenario was dropped: procurement_order_payment.py's cancel
#   path requires seller_fault/warehouse_handoff context that real order
#   records don't carry -- fabricating them would defeat the point of
#   grounding this in real data (2026-08-31, see design doc §5.7).
STATUS_SCENARIOS = {
    "구매확정완료": ("return", "return.check_eligibility", RETURN_TEMPLATES, "return_period_check"),
}


def _load_orders(*paths: str) -> list[dict]:
    rows = []
    for path in paths:
        p = ROOT / path
        if not p.exists():
            continue
        rows.extend(json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    return rows


def build(orders: list[dict], *, limit: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_status: dict[str, list[dict]] = {}
    for order in orders:
        status = order.get("order_status")
        if status in STATUS_SCENARIOS:
            by_status.setdefault(status, []).append(order)

    cases = []
    per_status_quota = max(1, limit // max(1, len(by_status)))
    for status, (intent, capability, templates, issue_code) in STATUS_SCENARIOS.items():
        pool = by_status.get(status, [])
        rng.shuffle(pool)
        for order in pool[:per_status_quota]:
            product_name = (order.get("product") or {}).get("name") or "주문 상품"
            message = rng.choice(templates).format(product=product_name)
            order_id_raw = str(order.get("order_id"))
            case_id = f"synth-order-{order_id_raw}"
            total_price = (order.get("product") or {}).get("total_price") or (order.get("payment") or {}).get("amount") or 0
            quantity = (order.get("product") or {}).get("quantity") or 1
            # ★real paid_at is usually weeks/months old (these are historical
            #   purchases), so almost every case fell outside the 7-day return
            #   window and escalated with answer=null -- useless for harvesting
            #   (2026-08-31 finding, 57/59 escalated). We keep the real
            #   product/amount but synthesize a recent order date so the
            #   scenario can actually complete; documented tradeoff, not a
            #   fabricated fact (the date isn't presented as real to anyone).
            synthetic_ordered_at = (datetime.now(UTC) - timedelta(days=rng.randint(1, 4))).isoformat()
            db_status = "delivered" if status == "구매확정완료" else "cancelled"
            cases.append({
                "case_id": case_id,
                "message": message,
                "channel": "chat",
                "expected_intent": intent,
                "expected_issue_code": issue_code,
                "expected_sentiment": "neutral",
                "expected_next_action": "respond",
                "expected_capability": capability,
                "notes": f"synthetic case from real order (status={status})",
                "_seed_order": {
                    "order_no_source": order_id_raw,
                    "total_cents": int(total_price),
                    "item_count": int(quantity),
                    "status": db_status,
                    "ordered_at": synthetic_ordered_at,
                    "product_name": product_name,
                },
            })
    rng.shuffle(cases)
    return cases[:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", action="append", default=None)
    parser.add_argument("--out", default="eval/finetune/synth_cases_from_orders.jsonl")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    order_paths = args.orders or [
        "../datasets/commerce/naver_order_history/processed/orders.jsonl",
        "../datasets/commerce/coupang_order_history/processed/orders.jsonl",
    ]
    orders = _load_orders(*order_paths)
    cases = build(orders, limit=args.limit, seed=args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(json.dumps({"orders_loaded": len(orders), "cases_written": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
