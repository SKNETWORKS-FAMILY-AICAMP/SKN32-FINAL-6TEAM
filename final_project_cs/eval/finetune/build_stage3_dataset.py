"""Build a stage-3 SFT dataset for the RAG-integrated fine-tune target:
ResponseGenerationReviewTeam's post-generation review pass
(app/application/controller.py::_maybe_review -> response.generate).

Earlier stage-2 data (eval/finetune/build_datasets.py) trained the model on
"customer message -> classification+answer JSON", which is NOT the shape
this Team actually receives at runtime. golden.jsonl's 72 cases all route
to deterministic Teams (return_refund/procurement_order_payment/
fulfillment_logistics, confirmed by inspecting team_result.team_id in
2026-08-28_reeval_Proposed_v3.jsonl) -- zero cases exercise
response_generation_review, because it is a post-hoc review pass
(config/project.yaml: response_review.enabled=false) invoked with
input_text=<primary team's draft answer>, not the customer's message.

This script reconstructs that real invocation shape from the judge-PASS
rows of the golden Proposed run (their evidence was already judge-verified
as properly grounded) and calls the actual (now-fixed, see
docs/reports/2026-08-30_S-PROMPT-KEY-REGISTRATION-GAP_리포트.md)
response.generate prompt for real, live, via OpenAITeamLLM -- so every
training target is a genuine grounded completion, not a fabricated one.

Usage:
    python -m eval.finetune.build_stage3_dataset --input eval/reports/2026-08-28_reeval_Proposed_v3.jsonl --out eval/finetune/sft_stage3.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

from app.core.contracts import ContextPack, Evidence
from app.infrastructure.llm.openai import OpenAITeamLLM
from app.infrastructure.db.session import get_connection
from app.modules.customer_ops.response_review_policy import decide_tone

ROOT = Path(__file__).resolve().parents[2]


def _load_golden() -> dict[str, dict]:
    result = {}
    for line in (ROOT / "eval/datasets/golden.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[row["case_id"]] = row
    return result


async def _one(llm: OpenAITeamLLM, row: dict, case: dict) -> dict:
    team_result = row["team_result"]
    answer = team_result.get("answer")
    if not answer:
        # legitimate, not a bug: _maybe_review() only ever runs when the primary
        # team produced an answer (waiting/escalated outcomes never reach it).
        return {"case_id": row["case_id"], "skip": "no_answer"}
    evidence_dicts = team_result.get("evidence") or []
    try:
        evidence = [Evidence(**e) for e in evidence_dicts]
    except Exception as exc:
        return {"case_id": row["case_id"], "skip": f"evidence_invalid: {type(exc).__name__}"}
    tone_profile = decide_tone(case.get("expected_sentiment"))
    context = ContextPack(
        pack_id=uuid4(), case_id=UUID(int=0), team_id="response_generation_review",
        tenant_id="stage3-dataset-build", knowledge_scope=["response_review"],
        current_state={"answer": answer, "sentiment": case.get("expected_sentiment")},
        evidence=evidence, estimated_input_tokens=1,
    )
    input_dict = {
        "evidence": [e.model_dump(mode="json") for e in evidence],
        "context": context.model_dump(mode="json"),
        "retry_count": 0,
        "tone_profile": tone_profile,
    }
    try:
        response = await llm.complete("response.generate", answer, input_dict)
    except Exception as exc:
        return {"case_id": row["case_id"], "error": f"{type(exc).__name__}: {exc}"}
    if not isinstance(response, dict) or "final_response_text" not in response:
        return {"case_id": row["case_id"], "error": "malformed response, no final_response_text"}
    return {
        "case_id": row["case_id"],
        "input_text": answer,
        "context": input_dict,
        "response": response,
    }


async def build(input_path: Path, out_path: Path, *, limit: int | None) -> dict:
    golden = _load_golden()
    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    passed = [r for r in rows if r.get("success")]
    # de-dup by case_id (golden Proposed has repeats=3, keep the first pass per case)
    seen: set[str] = set()
    deduped = []
    for r in passed:
        if r["case_id"] not in seen:
            seen.add(r["case_id"])
            deduped.append(r)
    if limit:
        deduped = deduped[:limit]

    llm = OpenAITeamLLM(connection_factory=get_connection)
    examples = []
    errors = []
    skipped = []
    missing_case = []
    for row in deduped:
        case = golden.get(row["case_id"])
        if case is None:
            missing_case.append(row["case_id"])
            continue
        result = await _one(llm, row, case)
        if "skip" in result:
            skipped.append(result)
            continue
        if "error" in result:
            errors.append(result)
            continue
        examples.append(result)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for ex in examples:
            # exact wire format OpenAITeamLLM sends -- same shape LocalFTTeamLLM
            # will send at inference, so the model trains on what it will see.
            user_prompt = json.dumps({
                "prompt_key": "response.generate", "input_text": ex["input_text"],
                "context": ex["context"],
                "instructions": (ROOT / "prompts/response/generate.v2.md").read_text(encoding="utf-8"),
            }, ensure_ascii=False, default=str)
            assistant = json.dumps(ex["response"], ensure_ascii=False)
            out.write(json.dumps({
                "case_id": ex["case_id"],
                "messages": [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": assistant},
                ],
            }, ensure_ascii=False) + "\n")

    return {"candidates": len(deduped), "written": len(examples), "skipped": skipped,
             "errors": errors, "missing_case": missing_case}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="eval/reports/2026-08-28_reeval_Proposed_v3.jsonl")
    parser.add_argument("--out", default="eval/finetune/sft_stage3.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    summary = asyncio.run(build(Path(args.input), Path(args.out), limit=args.limit))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
