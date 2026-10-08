"""Bridge a live golden-set Proposed run into eval.defense_metrics's input shape.

golden.jsonl cases are all normal (non-adversarial) scenarios, so every row
here declares expect_block=false — this measures over_abstention only.
proper_abstention (does the defense actually block a bad proposal) is
already measured by eval/datasets/attack_fixtures.jsonl; this bridge does
not duplicate that.

    python -m eval.bridge_golden_to_defense --input eval/reports/2026-08-28_reeval_Proposed_v3.jsonl \
        --output eval/reports/2026-08-28_golden_defense_input.jsonl
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from app.infrastructure.db.session import get_connection
from app.core.settings import get_settings

FACT_QUERIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("orders",
     "SELECT order_id, order_no, total_cents, item_count, status FROM orders "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("order_id", "order_no", "total_cents", "item_count", "status")),
    ("shipments",
     "SELECT shipment_id, order_id, carrier, status FROM shipments "
     "WHERE tenant_id=%s AND customer_id=%s",
     ("shipment_id", "order_id", "carrier", "status")),
)


def _facts_for_customer(conn: Any, tenant_id: str, customer_id: str) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for name, sql, columns in FACT_QUERIES:
        with conn.cursor() as cur:
            cur.execute(sql, (tenant_id, customer_id))
            rows = cur.fetchall()
        keyed = {str(row[0]): dict(zip(columns, row)) for row in rows}
        for row in keyed.values():
            row["order_id"] = str(row.get("order_id")) if row.get("order_id") is not None else row.get("order_id")
        facts[name] = keyed
    return facts


def convert(input_path: str, output_path: str) -> dict[str, int]:
    from uuid import uuid5, NAMESPACE_URL

    with open(input_path, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]

    settings = get_settings()
    tenant_id = settings.tenant_id
    total_with_proposal = 0
    written = 0
    empty_facts = 0

    with get_connection() as conn, open(output_path, "w", encoding="utf-8") as out:
        for row in rows:
            team_result = row.get("team_result") or {}
            proposals = team_result.get("action_proposals") or []
            if not proposals:
                continue
            total_with_proposal += 1
            proposal = proposals[0]
            case_id = row["case_id"]
            customer_id = str(uuid5(NAMESPACE_URL, case_id))
            facts = _facts_for_customer(conn, tenant_id, customer_id)
            facts["evidence_ids"] = [e.get("evidence_id") for e in team_result.get("evidence", [])
                                     if e.get("evidence_id")]
            if not facts.get("orders") and not facts.get("shipments"):
                empty_facts += 1

            # NOTE: the runner's row-level "degraded" field also folds in
            # "team_result has any warnings", and return.request/
            # refund.calculate ALWAYS carry a mock-disclaimer warning by
            # design — so it reads true for ~100% of proposal rows
            # regardless of real ContextPack degradation. True
            # ContextPack.degraded isn't persisted in the run output, so we
            # deliberately do not reuse that field here; treat as False and
            # let verify_proposal()'s own findings drive escalation.
            out_row = {
                "case_id": f"{case_id}:{row.get('repeat')}",
                "expect_block": False,
                "parse_ok": True,
                "degraded": False,
                "proposal": {
                    "arguments": proposal.get("arguments") or {},
                    "rationale_evidence_ids": proposal.get("rationale_evidence_ids") or [],
                },
                "facts": facts,
            }
            out.write(json.dumps(out_row, ensure_ascii=False) + "\n")
            written += 1

    return {"rows_in": len(rows), "rows_with_proposal": total_with_proposal,
            "rows_written": written, "rows_with_empty_facts": empty_facts}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(json.dumps(convert(a.input, a.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
