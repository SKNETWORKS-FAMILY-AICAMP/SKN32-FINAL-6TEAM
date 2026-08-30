"""Judge-score Proposed+FT predictions (eval/finetune/ft_predictions.jsonl)
against the same golden.jsonl cases and rubric used for the Proposed arm,
so the two are directly comparable.

Proposed+FT predictions come straight from the fine-tuned model with no
Context Broker / RAG evidence attached (predict.py never runs the Team
pipeline) -- so policy_evidence and citations are honestly empty for every
row, not omitted. Per judge_v1's rubric, empty citations.valid forces
policy_grounding=0. That is a real, expected result to report, not a
scoring bug.

Usage:
    python -m eval.finetune.score_ft --input eval/finetune/ft_predictions.jsonl --output eval/reports/2026-08-30_reeval_ProposedFT.jsonl
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "prompts/judge/judge_v1.txt"
RUBRIC = ROOT / "eval/judge/rubric.json"


def _cases() -> dict[str, dict]:
    result = {}
    for name in ("golden.jsonl", "holdout.jsonl"):
        path = ROOT / "eval/datasets" / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                result[row["case_id"]] = row
    return result


def _judge(prompt: str, api_key: str, model: str, timeout: float) -> dict:
    from openai import OpenAI
    response = OpenAI(api_key=api_key, timeout=timeout).chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Respond with a single valid JSON object and nothing else."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0, seed=7, response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content or "{}")


def score(input_path: Path, output_path: Path, *, model: str, timeout: float) -> int:
    cases = _cases()
    rows = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    from eval.runners.common import _settings
    settings = _settings()
    model = model or str(settings.llm_model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        for raw in rows:
            case = cases.get(raw["case_id"])
            if case is None:
                raise ValueError(f"case_id not found in golden/holdout: {raw['case_id']}")
            if not raw.get("parse_ok"):
                row = {"case_id": raw["case_id"], "arm": "Proposed+FT", "success": False, "score": 0,
                       "judge": None, "prediction": None,
                       "rescore": {"reason": "predict.py failed to parse a JSON object from the raw generation"}}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                continue
            candidate = raw.get("prediction") or {}
            record = {"case": case, "candidate_output": candidate,
                      "policy_evidence": [], "citations": {"claimed": [], "valid": [], "invalid": []}}
            prompt = (PROMPT.read_text(encoding="utf-8") + "\nRUBRIC:\n"
                      + RUBRIC.read_text(encoding="utf-8") + "\nINPUT_RECORD:\n"
                      + json.dumps(record, ensure_ascii=False, default=str))
            started = time.perf_counter()
            judge = _judge(prompt, settings.openai_api_key, model, timeout)
            required = {"correctness", "policy_grounding", "next_action", "safety", "personalization", "total", "pass"}
            if not required <= judge.keys():
                raise ValueError(f"judge response missing rubric fields: {sorted(required - set(judge))}")
            row = {"case_id": raw["case_id"], "arm": "Proposed+FT", "prediction": candidate,
                   "judge": judge, "score": int(judge["total"]), "success": bool(judge["pass"]),
                   "rescore": {"dataset_contract": "NextAction-v5", "judge_prompt_version": "judge-v1",
                               "source_raw": str(input_path),
                               "latency_ms": round((time.perf_counter() - started) * 1000, 3)}}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge-score Proposed+FT predictions")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    count = score(Path(args.input), Path(args.output), model=args.model, timeout=args.timeout)
    print(json.dumps({"input": args.input, "output": args.output, "rows": count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
