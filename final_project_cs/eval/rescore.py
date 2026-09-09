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
#: 기본은 judge-v1 — **바꾸지 않는다.** 지금까지의 모든 수치가 v1 로 매겨져 있고,
#: 채점자를 바꾸면 비교가 끊긴다. `--judge-prompt` 는 **비교 측정용**이다.
#: 근거: wiki/records/reports/debugs/2026-09-06_judge의_policy_grounding이_상수다.md
#: ★2026-09-06 judge-v1 → **judge-v3** 로 교체했다(재기준선, D-014).
#:  v1 의 `policy_grounding` 은 **분산 0 인 상수**였다 — 인용이 붙었는지만 보고
#:  답변이 그 근거를 쓰는지 묻지 않았다. v3 는 같은 자리 문장에 0~4 눈금을 준다.
#:  ★채점자를 바꾸면 모든 점수가 같이 움직이므로 **v1 점수와 직접 비교하지 않는다.**
#:  갈아탈 수 있다고 판단한 근거는 **같은 채점자 안에서 군 순위가 보존됐기** 때문이다
#:  (B > Proposed > A, 양쪽 동일 — `eval/compare_baselines.py`).
#:  근거: wiki/records/reports/2026-09-06_S-JUDGE-GROUNDING-축_측정_리포트.md
PROMPT = ROOT / "prompts/judge/judge_v3.txt"
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


def rescore(input_path: Path, output_path: Path, *, model: str, timeout: float,
            judge_prompt: Path | None = None, repeat: int | None = None) -> int:
    cases = _cases()
    prompt_path = judge_prompt or PROMPT
    prompt_text = prompt_path.read_text(encoding="utf-8")
    # ★버전 문자열을 프롬프트 **파일에서 읽는다.** 손으로 적으면 파일과 어긋나고,
    #   그러면 산출물이 어느 채점자로 매겨졌는지 알 수 없게 된다.
    version = "unknown"
    for header in prompt_text.splitlines():
        if header.startswith("JUDGE_PROMPT_VERSION:"):
            version = header.split(":", 1)[1].strip()
            break
    lines = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if repeat is not None:
        # ★반복 회차 하나만 골라 비교한다. 채점자를 비교할 때 3회를 다 돌릴
        #   필요는 없다 — 회차가 다르면 **후보 답변 자체가 다르므로** 채점자
        #   차이와 답변 차이가 섞인다. 한 회차로 고정해야 채점자만 남는다.
        lines = [row for row in lines if row.get("repeat") == repeat]
        if not lines:
            raise ValueError(f"repeat={repeat} 인 행이 없다")
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
            prompt = (prompt_text + "\nRUBRIC:\n"
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
            row["rescore"] = {"dataset_contract": "NextAction-v5", "judge_prompt_version": version,
                              "source_raw": str(input_path), "latency_ms": round((time.perf_counter()-started)*1000, 3)}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rejudge raw predictions without rerunning model arms")
    parser.add_argument("--input", required=True, help="preserved eval/reports/raw_*.jsonl")
    parser.add_argument("--output", required=True, help="new rescored_*.jsonl")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--judge-prompt", default=None,
                        help="채점자 프롬프트 파일. 기본은 judge_v1 — 비교 측정할 때만 바꾼다")
    parser.add_argument("--repeat", type=int, default=None,
                        help="이 반복 회차만 채점한다. 채점자끼리 비교할 때 답변을 고정하려고")
    args = parser.parse_args()
    count = rescore(Path(args.input), Path(args.output), model=args.model, timeout=args.timeout,
                    judge_prompt=Path(args.judge_prompt) if args.judge_prompt else None,
                    repeat=args.repeat)
    print(json.dumps({"input": args.input, "output": args.output, "rows": count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
