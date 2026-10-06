# -*- coding: utf-8 -*-
"""활동 판정 평가 실행기(D-CS-008 5단계) — 골든셋을 규칙 · LLM 으로 판정하고 지표를 낸다.

    python -m eval.activity_judge.build              # 골든셋(cases.jsonl) · 매니페스트
    python -m eval.activity_judge.run                # 60건 × 3회 · 실제 모델 · DB 프롬프트 · 감사 기록
    python -m eval.activity_judge.run --repeats 1 --only closure,operating_hours

★실제 경로를 탄다 — `LLMJudge(OpenAIResponsesJudgeLLM(connection_factory=get_connection))`. 지시문은 DB 에
  등록된 프롬프트이고, 호출마다 `llm_calls` 에 감사 기록이 남는다(`run_id` 는 없다 — 평가는 Case 가 아니다).
★관측마다 섀도 기록 표(`activity_judge_shadow`)에 `origin='eval'` 로 한 행을 쓴다 — 운영 섀도와 같은 쿼리로 본다.
★결과 원문은 `eval/reports/activity_judge/<eval_run>/` 에 남긴다(results.jsonl · summary.json).
★매니페스트 해시와 골든셋이 다르면 돌지 않는다 — 다른 데이터로 낸 수치를 같은 이름으로 싣지 않는다.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.settings import get_settings
from app.modules.travel_ops.activity.judge import JudgeContext, LLMJudge, RuleJudge, requests
from app.modules.travel_ops.activity.judge.modes import _record

from .build import DATASET, MANIFEST
from .metrics import summarize

REPORTS = Path(__file__).resolve().parents[1] / "reports" / "activity_judge"


def load_cases() -> list[dict]:
    text = DATASET.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != manifest["sha256"]:
        raise SystemExit(f"골든셋 해시가 매니페스트와 다르다({digest[:12]} ≠ {manifest['sha256'][:12]}) — build 를 다시 돌린다")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def to_request(case: dict):
    i = case["inputs"]
    starts = datetime.fromisoformat(i["starts_at"]) if i.get("starts_at") else None
    kind = case["kind"]
    if kind == "closure":
        return requests.closure(i["restdate_text"], starts)
    if kind == "operating_hours":
        return requests.operating_hours(i["usetime_text"], starts)
    if kind == "weather_sensitive":
        return requests.weather_sensitive(i["title"], i.get("lclssystm2"))
    if kind == "disaster_effect":
        return requests.disaster_effect(i["place_name"], i.get("place_kind"), i["messages"], starts)
    return requests.live_status(i["place_name"], i.get("place_kind"), i.get("address"), starts)


async def run(cases: list[dict], *, repeats: int, concurrency: int, eval_run: str, write_db: bool) -> list[dict]:
    from app.composition import build_activity_judge_shadow_sink
    from app.infrastructure.db.session import get_connection
    from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM

    llm = LLMJudge(OpenAIResponsesJudgeLLM(connection_factory=get_connection))
    rule = RuleJudge()
    sink = build_activity_judge_shadow_sink() if write_db else None
    gate = asyncio.Semaphore(concurrency)
    rows: list[dict] = []

    async def one(case: dict, repeat: int) -> None:
        request = to_request(case)
        ctx = JudgeContext(capability="eval.activity_judge")
        rule_verdict = rule.judge(ctx, request)
        async with gate:
            verdict = await llm.judge(ctx, request)
        record = _record(ctx, request, event="activity_judge_shadow", rule=rule_verdict, llm=verdict)
        record.update(origin="eval", eval_run=eval_run, eval_case=case["case_id"], eval_repeat=repeat)
        if sink is not None:
            await asyncio.to_thread(sink, record)
        rows.append({
            "case_id": case["case_id"], "kind": case["kind"], "repeat": repeat,
            "labeled": case["expected"] is not None, "expected": case["expected"], "acceptable": case["acceptable"],
            "rule": rule_verdict.value, "rule_basis": rule_verdict.basis, "llm": verdict.value,
            "failure_code": verdict.failure_code, "confidence": verdict.confidence,
            "quotes": verdict.quotes, "citations": len(verdict.citations),
            "citation_urls": [c.get("url") for c in verdict.citations], "dropped": verdict.dropped,
            "reason": verdict.basis,
            **{k: verdict.metrics.get(k) for k in ("latency_ms", "search_calls", "input_tokens", "output_tokens",
                                                    "reasoning_tokens", "undated_citations", "model")},
        })
        print(f"  {case['case_id']:<12} r{repeat} rule={rule_verdict.value:<10} llm={verdict.value:<10} "
              f"{verdict.failure_code or ''}", flush=True)

    await asyncio.gather(*(one(case, r) for r in range(1, repeats + 1) for case in cases))
    return sorted(rows, key=lambda r: (r["case_id"], r["repeat"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--only", default="", help="판정 종류를 쉼표로 (closure,operating_hours,…)")
    parser.add_argument("--no-db", action="store_true", help="섀도 기록 표에 쓰지 않는다")
    args = parser.parse_args()

    cases = load_cases()
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["kind"] in wanted]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    settings = get_settings()
    eval_run = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    conditions = {
        "eval_run": eval_run, "dataset_sha256": manifest["sha256"], "labeler": manifest["labeler"],
        "cases": len(cases), "repeats": args.repeats,
        "model": settings.activity_judge_model, "reasoning_effort": settings.activity_judge_reasoning_effort,
        "web_search": settings.activity_judge_web_search,
        # ★gpt-5.4-nano 는 seed 를 받지 않고, effort≠none 이면 temperature 도 받지 않는다(스파이크 Q1)
        "temperature": None, "seed": None,
        "prompt_version": "activity_judge.*.v1", "bootstrap": {"n": 10000, "seed": 7, "unit": "case"},
    }
    print(json.dumps(conditions, ensure_ascii=False))
    started = datetime.now(UTC)
    rows = asyncio.run(run(cases, repeats=args.repeats, concurrency=args.concurrency, eval_run=eval_run,
                           write_db=not args.no_db))
    summary = {"conditions": conditions, "elapsed_s": round((datetime.now(UTC) - started).total_seconds(), 1),
               **summarize(rows)}
    out = REPORTS / eval_run
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                       encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n→ {out}")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
