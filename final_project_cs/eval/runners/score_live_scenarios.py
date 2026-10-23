# -*- coding: utf-8 -*-
"""실제 모델 종단 실행 채점 — `travel_scenarios --llm live` 결과를 흉내 실행(완벽한 분류 · 추출)과 정답에 대어 본다. `[2026-10-06]`

    python -m eval.runners.score_live_scenarios LIVE.json MOCK.json [--out SCORE.json]

★무엇을 재나(분자/분모)
    추출 종류 정확도   신고 종류가 정답과 같은 고객 문장 / 고객 문장
    분 값 정확도       분이 정답과 같은 늦음 문장 / 늦음 문장
    품목 재현율        뽑은 품목 중 정답 품목 / 정답 품목(품절 문장)
    값 지어냄          문장에 없는 숫자를 분 · 버전으로 낸 출력 / 숫자를 낸 출력
    분류 접두 일치     issue_code 접두가 담당 팀(늦음 · 휴무 → dining, 품절 → activity)과 같은 분류 / 분류
    결과 일치          상태(resolved · escalated)와 담당 팀이 흉내 실행과 같은 고객 단계 / 고객 단계
    반복 안정성        같은 시나리오 · 같은 단계에서 반복 실행의 추출 · 결과가 모두 같은 단계 / 단계
    시나리오 통과      필수 조건 위반 0 · 기대 버전 수 충족 / 실행
    지연               모델 호출 한 번의 ms (p50 · p95, 첫 호출은 모델 적재 포함)
★흉내 실행은 「모델이 완벽할 때 규칙이 내는 결과」다. 실제 모델과 다르면 그 차이는 모델 몫이다.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

TEAM_OF = {"delay": "dining", "closed": "dining", "stock_out": "activity"}


def _ratio(num: int, den: int) -> dict:
    return {"num": num, "den": den, "rate": round(num / den, 3) if den else None}


def score(live: dict, mock: dict) -> dict:
    mock_steps = {}
    for result in mock["results"]:
        for i, step in enumerate(result["steps"]):
            mock_steps[(result["case_id"], i)] = step

    kind_ok = minutes_ok = minutes_den = invented = numeric = 0
    prod_hit = prod_den = prefix_ok = classify_den = agree = agree_den = says = 0
    errors = []
    lat = defaultdict(list)
    by_slot = defaultdict(list)
    misses = []
    runs_passed = 0
    for result in live["results"]:
        runs_passed += bool(result["verdict"]["passed"])
        for i, step in enumerate(result["steps"]):
            calls = step.get("llm_calls") or []
            for call in calls:
                lat[call["fn"]].append(call["ms"])
                if "error" in call:
                    errors.append({"case": result["case_id"], "step": step["step"], **call})
            if not step["step"].startswith(("say", "swap", "rollback")):
                continue
            ref = mock_steps.get((result["case_id"], i))
            if ref is not None:
                agree_den += 1
                same = (step.get("status"), step.get("team")) == (ref.get("status"), ref.get("team"))
                agree += same
                if not same:
                    misses.append({"case": result["case_id"], "step": step["step"],
                                   "live": [step.get("status"), step.get("team")],
                                   "mock": [ref.get("status"), ref.get("team")]})
            extract = next((c for c in calls if c["fn"] == "extract"), None)
            out = (extract or {}).get("output") or {}
            by_slot[(result["case_id"], i)].append(
                json.dumps([out, step.get("status"), step.get("team")], ensure_ascii=False, sort_keys=True))
            truth = step.get("truth")
            if not truth:
                continue
            says += 1
            kind_ok += out.get("type") == truth["type"]
            if truth["type"] == "delay":
                minutes_den += 1
                minutes_ok += out.get("minutes") == truth["minutes"]
            if truth.get("products"):
                got = [str(p) for p in out.get("products") or []]
                prod_den += len(truth["products"])
                prod_hit += sum(any(t in g or g in t for g in got) for t in truth["products"])
            digits = set(re.findall(r"\d+", step.get("text", "")))
            for key in ("minutes", "to_version"):
                if out.get(key) is not None:
                    numeric += 1
                    invented += str(out[key]) not in digits
            classify = next((c for c in calls if c["fn"] == "classify"), None)
            if classify and classify.get("output"):
                classify_den += 1
                prefix_ok += str(classify["output"].get("issue_code", "")).startswith(TEAM_OF.get(truth["type"], "?"))

    stable = sum(len(set(v)) == 1 for v in by_slot.values())

    def pct(values, q):
        values = sorted(values)
        return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else None

    return {
        "model": live.get("model"), "runs": len(live["results"]),
        "extract_kind_accuracy": _ratio(kind_ok, says),
        "minutes_accuracy": _ratio(minutes_ok, minutes_den),
        "products_recall": _ratio(prod_hit, prod_den),
        "invented_values": _ratio(invented, numeric),
        "classify_prefix_match": _ratio(prefix_ok, classify_den),
        "outcome_agrees_with_mock": _ratio(agree, agree_den),
        "repeat_stability": _ratio(stable, len(by_slot)),
        "scenario_pass": _ratio(runs_passed, len(live["results"])),
        "violations": sum(len(r["violations"]) for r in live["results"]),
        "llm_errors": len(errors),
        "latency_ms": {fn: {"calls": len(v), "p50": pct(v, 0.5), "p95": pct(v, 0.95), "max": max(v),
                            "mean": round(statistics.mean(v))} for fn, v in lat.items()},
        "outcome_misses": misses, "errors": errors[:20],
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("live")
    parser.add_argument("mock")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    live = json.loads(Path(args.live).read_text(encoding="utf-8"))
    mock = json.loads(Path(args.mock).read_text(encoding="utf-8"))
    if args.model:
        live["model"] = args.model
    result = score(live, mock)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
