"""Build INTENTIONALLY-MISMATCHED review-task training examples.

docs/plans/2026-08-30_DoD28-FT-RAG통합_설계.md §7.5 found the actual failure
mode of stage3 v1-v7: the model learned "usually echo the draft" rather
than "check the draft against evidence," because every training example so
far had a draft that was ALREADY consistent with its evidence (the primary
Team generated both from the same DB state, so of course they agree). The
one holdout case that happened to be inconsistent (draft said "delivered",
evidence said "not yet handed to courier") is exactly what exposed this --
local_ft echoed and scored grounded=0; OpenAI caught the contradiction and
scored grounded=4.

This script manufactures that exact training signal on purpose: take a
completed shipment.status case (whose team_result.evidence contains a
"tool:fulfillment_logistics:read.shipment" item with a real status), and
for a majority of cases, SWAP that evidence's status to a DIFFERENT real
status than what the draft claims -- creating a genuine draft/evidence
contradiction -- before calling the real (fixed) response.generate. The
resulting target is OpenAI's actual correction, grounded in the (now
corrupted-on-purpose) evidence, not fabricated by this script. A minority
of cases are left untouched as consistent controls, so the model also
keeps seeing legitimate "echo is correct" examples -- without both kinds
present, the model can just flip its shortcut from "always echo" to
"always rewrite", which is equally not real judgment.

Usage:
    python -m eval.finetune.build_stage3_mismatch_dataset --input eval/reports/2026-08-31_synth_shipment_proposed.jsonl --out eval/finetune/sft_stage3_mismatch.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import random
from pathlib import Path
from uuid import UUID, uuid4

from app.core.contracts import ContextPack, Evidence
from app.infrastructure.llm.openai import OpenAITeamLLM
from app.infrastructure.db.session import get_connection
from app.modules.customer_ops.response_review_policy import decide_tone
from eval.finetune.build_stage3_dataset import _shrink_evidence

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ["delivered", "delayed", "in_transit"]
STATUS_KO = {"delivered": "delivered", "delayed": "delayed", "in_transit": "in_transit"}


def _swap_shipment_status(evidence_dicts: list[dict], new_status: str) -> tuple[list[dict], str | None]:
    """Return (mutated evidence, original_status). Mutates a deep copy only."""
    out = copy.deepcopy(evidence_dicts)
    original = None
    for e in out:
        if e.get("evidence_id", "").startswith("tool:fulfillment_logistics:read.shipment"):
            value = e.get("value")
            if isinstance(value, list):
                for shipment in value:
                    if isinstance(shipment, dict) and "status" in shipment:
                        original = shipment["status"]
                        shipment["status"] = new_status
    return out, original


async def _one(llm: OpenAITeamLLM, row: dict, *, mismatch_rate: float, rng: random.Random) -> dict:
    team_result = row["team_result"]
    answer = team_result.get("answer")
    if not answer:
        return {"case_id": row["case_id"], "skip": "no_answer"}
    evidence_dicts = team_result.get("evidence") or []

    corrupted = rng.random() < mismatch_rate
    injected_status = None
    if corrupted:
        other_statuses = [s for s in STATUSES if s not in answer]
        if not other_statuses:
            corrupted = False
        else:
            injected_status = rng.choice(other_statuses)
            evidence_dicts, original = _swap_shipment_status(evidence_dicts, injected_status)
            if original is None:
                corrupted = False  # no shipment evidence found to corrupt; fall back to a clean example

    try:
        evidence = [Evidence(**e) for e in evidence_dicts]
    except Exception as exc:
        return {"case_id": row["case_id"], "skip": f"evidence_invalid: {type(exc).__name__}"}
    # ★_shrink_evidence() always keeps its first item, then budget-caps the
    #   rest in list order -- shipment cases list 8 policy chunks BEFORE the
    #   tool:fulfillment_logistics:read.shipment fact, so the actual status
    #   (the one thing this script deliberately corrupts) was getting cut by
    #   the budget before OpenAI ever saw it, corrupted or not (2026-08-31
    #   finding: every "mismatch" sample just re-asserted the draft's
    #   original status, because it never received contradicting evidence).
    #   Move the fact evidence to the front so the "always keep first" rule
    #   guarantees it survives.
    evidence.sort(key=lambda e: 0 if e.evidence_id.startswith("tool:") else 1)
    evidence = _shrink_evidence(evidence)

    tone_profile = decide_tone(None)
    context = ContextPack(
        pack_id=uuid4(), case_id=UUID(int=0), team_id="response_generation_review",
        tenant_id="stage3-mismatch-build", knowledge_scope=["response_review"],
        current_state={"answer": answer}, evidence=evidence, estimated_input_tokens=1,
    )
    input_dict = {
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "context": context.model_dump(mode="json"),
        "retry_count": 0, "tone_profile": tone_profile,
    }
    try:
        response = await llm.complete("response.generate", answer, input_dict)
    except Exception as exc:
        return {"case_id": row["case_id"], "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(response, dict) or "final_response_text" not in response:
        return {"case_id": row["case_id"], "error": "malformed response, no final_response_text"}
    return {
        "case_id": row["case_id"] + ("-mismatch" if corrupted else "-consistent"),
        "input_text": answer, "context": input_dict, "response": response,
        "corrupted": corrupted, "injected_status": injected_status,
    }


async def build(input_path: Path, out_path: Path, *, mismatch_rate: float, seed: int) -> dict:
    rng = random.Random(seed)
    rows = [json.loads(l) for l in input_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    completed = [r for r in rows if (r.get("team_result") or {}).get("answer")]

    llm = OpenAITeamLLM(connection_factory=get_connection)
    examples, errors, skipped = [], [], []
    n_corrupted = 0
    for row in completed:
        result = await _one(llm, row, mismatch_rate=mismatch_rate, rng=rng)
        if "skip" in result:
            skipped.append(result); continue
        if "error" in result:
            errors.append(result); continue
        if result["corrupted"]:
            n_corrupted += 1
        examples.append(result)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    instructions = (ROOT / "prompts/response/generate.v2.md").read_text(encoding="utf-8")
    with out_path.open("w", encoding="utf-8") as out:
        for ex in examples:
            user_prompt = json.dumps({
                "prompt_key": "response.generate", "input_text": ex["input_text"],
                "context": ex["context"], "instructions": instructions,
            }, ensure_ascii=False, default=str)
            assistant = json.dumps(ex["response"], ensure_ascii=False)
            out.write(json.dumps({
                "case_id": ex["case_id"],
                "messages": [{"role": "user", "content": user_prompt}, {"role": "assistant", "content": assistant}],
            }, ensure_ascii=False) + "\n")

    return {"candidates": len(completed), "written": len(examples), "corrupted": n_corrupted,
            "consistent": len(examples) - n_corrupted, "errors": errors, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="eval/finetune/sft_stage3_mismatch.jsonl")
    parser.add_argument("--mismatch-rate", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    summary = asyncio.run(build(Path(args.input), Path(args.out), mismatch_rate=args.mismatch_rate, seed=args.seed))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
