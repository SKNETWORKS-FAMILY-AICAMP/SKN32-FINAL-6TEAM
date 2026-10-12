"""Rejudge preserved raw predictions against the current dataset contract.

This intentionally performs judge calls only; it never reruns an arm or edits
the input raw report.  The command is expected to require network access when
run without ``--dry-run``.
"""
from __future__ import annotations

import argparse
import copy
import json
import time
from pathlib import Path

from eval.next_action_mapping import ACTION_MAP, NEXT_ACTIONS

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "prompts/judge/judge_v1.txt"
RUBRIC = ROOT / "eval/judge/rubric.json"


def _cases() -> dict[str, dict]:
    result = {}
    for name in ("golden.jsonl", "holdout.jsonl"):
        for line in (ROOT / "eval/datasets" / name).read_text(encoding="utf-8").splitlines():
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


def rescore(input_path: Path, output_path: Path, *, model: str, timeout: float) -> int:
    cases = _cases()
    lines = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    from eval.runners.common import _settings
    settings = _settings()
    model = model or str(settings.llm_model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        for raw in lines:
            case = cases.get(raw["case_id"])
            if case is None:
                raise ValueError(f"case_id not found in golden/holdout: {raw['case_id']}")
            candidate = copy.deepcopy(raw.get("prediction", {}))
            # Raw A/B predictions may intentionally contain the pre-fix labels;
            # they are candidates to score, never data to rewrite.  Proposed
            # rows already contain the v5 enum, and the judge decides how any
            # out-of-contract candidate should score against the new target.
            evidence = []
            for item in (raw.get("team_result") or {}).get("evidence", []):
                if item.get("source_type") == "policy":
                    evidence.append(item)
            record = {"case": case, "candidate_output": candidate,
                      "policy_evidence": evidence, "citations": raw.get("citations", {})}
            prompt = (PROMPT.read_text(encoding="utf-8") + "\nRUBRIC:\n"
                      + RUBRIC.read_text(encoding="utf-8") + "\nINPUT_RECORD:\n"
                      + json.dumps(record, ensure_ascii=False, default=str))
            started = time.perf_counter()
            judge = _judge(prompt, settings.openai_api_key, model, timeout)
            required = {"correctness", "policy_grounding", "next_action", "safety", "personalization", "total", "pass"}
            # set <= dict 는 TypeError 다. 키 집합과 비교해야 한다.
            if not required <= judge.keys():
                raise ValueError(f"judge response missing rubric fields: {sorted(required - set(judge))}")
            row = copy.deepcopy(raw)
            row["judge"] = judge
            row["score"] = int(judge["total"])
            row["success"] = bool(judge["pass"])
            row["rescore"] = {"dataset_contract": "NextAction-v5", "judge_prompt_version": "judge-v1",
                              "source_raw": str(input_path), "latency_ms": round((time.perf_counter()-started)*1000, 3)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rejudge raw predictions without rerunning model arms")
    parser.add_argument("--input", required=True, help="preserved eval/reports/raw_*.jsonl")
    parser.add_argument("--output", required=True, help="new rescored_*.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    count = rescore(Path(args.input), Path(args.output), model=args.model, timeout=args.timeout)
    print(json.dumps({"input": args.input, "output": args.output, "rows": count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
