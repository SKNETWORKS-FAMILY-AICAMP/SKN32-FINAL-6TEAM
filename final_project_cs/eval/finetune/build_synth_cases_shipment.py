"""Synthetic shipment.status cases -- unlike return.check_eligibility (a
fixed-string deterministic answer regardless of case specifics),
fulfillment_logistics.py's shipment.status branch embeds the actual status
into its answer (f"배송 상태는 {status}입니다."), so varying
expected_issue_code produces genuinely different draft text per case (see
docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md §7.2 -- every prior source
collapsed to 2 unique drafts because return_refund's answer never varies).

eval/runners/common.py::_seed_golden_fixtures maps expected_issue_code to
DB shipment.status:
    delivered_not_received                -> "delivered"
    dispatch_delay / carrier_reply_pending -> "delayed"
    (anything else)                        -> "in_transit"
This script rotates evenly across those three buckets, so the three
resulting drafts are ~evenly represented -- not just three examples buried
in a lopsided pile.

Usage:
    python -m eval.finetune.build_synth_cases_shipment --out eval/finetune/synth_cases_shipment.jsonl --limit 30
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORDER_FILES = [
    "datasets/commerce/naver_order_history/processed/orders.jsonl",
    "datasets/commerce/coupang_order_history/processed/orders.jsonl",
]

BUCKETS = [
    ("delivered_not_received", [
        "{product} 배송완료라고 뜨는데 아직 못 받았어요. 확인 좀 부탁드립니다.",
        "배송 상태가 완료로 바뀌었는데 실제로는 물건이 안 왔어요. {product} 주문 건이요.",
    ]),
    ("dispatch_delay", [
        "{product} 주문한 지 꽤 됐는데 아직도 배송이 시작 안 됐어요. 언제 발송되나요?",
        "배송이 너무 늦어지고 있어요. {product} 언제쯤 받을 수 있을까요?",
    ]),
    ("carrier_status_check", [
        "{product} 배송 상태가 궁금해서 문의드립니다.",
        "제가 주문한 {product}, 지금 어디쯤 왔는지 확인 가능할까요?",
    ]),
]


def _load_orders(*paths: str) -> list[dict]:
    rows = []
    for path in paths:
        p = ROOT.parent / path
        if p.exists():
            rows.extend(json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    return rows


def build(orders: list[dict], *, limit: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rng.shuffle(orders)
    per_bucket = max(1, limit // len(BUCKETS))
    cases = []
    idx = 0
    for issue_code, templates in BUCKETS:
        for _ in range(per_bucket):
            if idx >= len(orders):
                break
            order = orders[idx]
            idx += 1
            product_name = (order.get("product") or {}).get("name") or "주문 상품"
            message = rng.choice(templates).format(product=product_name)
            order_id_raw = str(order.get("order_id"))
            case_id = f"synth-shipment-{issue_code}-{order_id_raw}"
            cases.append({
                "case_id": case_id,
                "message": message,
                "channel": "chat",
                "expected_intent": "shipping",
                "expected_issue_code": issue_code,
                "expected_sentiment": "worried" if issue_code != "carrier_status_check" else "neutral",
                "expected_next_action": "respond",
                "expected_capability": "shipment.status",
                "notes": f"synthetic shipment.status case, issue_code={issue_code} "
                         f"-> distinct DB shipment.status via _seed_golden_fixtures",
                "_seed_order": {
                    "order_no_source": order_id_raw,
                    "total_cents": int((order.get("product") or {}).get("total_price") or 0),
                    "item_count": int((order.get("product") or {}).get("quantity") or 1),
                    "status": "delivered",
                    "ordered_at": None,
                    "product_name": product_name,
                },
            })
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="eval/finetune/synth_cases_shipment.jsonl")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    orders = _load_orders(*ORDER_FILES)
    cases = build(orders, limit=args.limit, seed=args.seed)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(json.dumps({"orders_loaded": len(orders), "cases_written": len(cases)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
