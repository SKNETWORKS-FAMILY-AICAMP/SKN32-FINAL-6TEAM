# -*- coding: utf-8 -*-
"""요식 판정 에이전트 평가 — 체크리스트(설계 §7)가 기준이다. 같은 자료로 세 구성을 잰다. `[2026-10-13]`

    python -m eval.runners.dining_agent --config agent --model openai:gpt-4o-mini --repeats 3 --label b-4omini
    python -m eval.runners.dining_agent --config direct --model gemma:gemma4:e4b ...
    python -m eval.runners.dining_agent --config rule --label c-rule

구성
    rule    C. 지금 코드 — 시각이 있는 식사는 찾기 · 영업 판정을 규칙으로. 고객 **자유 문장**의 조건(할랄 · 아이 · 카드)은 읽지 않는다
            (지금 코드는 설문의 정해진 칸만 읽는다 — `dining/survey.conds_from_survey`). 판정 값은 규칙 그대로라 맞는다.
    agent   B. 에이전트 + 규칙 도구(추천 기본안) — LLM이 체크를 고르고 규칙 도구의 판정을 인용한다
    direct  A. 에이전트 + 자료 도구만 — LLM이 영업 구간 · 휴무 원문을 읽고 직접 계산한다

지표(식사 항목 × 체크)
    must_accuracy   골라야 할 체크 중 기대 판정과 같게 낸 비율(안 냈으면 틀림) — 주 지표
    missing         골라야 할 체크를 안 냄 · unnecessary 고르면 안 될 체크를 냄(설계 §7 「체크 고르기」)
    validation      근거 검증 실패 · failure 판정 전체 실패(턴 · 시간 상한 · 모델 오류 · 최종 답 못 읽음)
    시간 · 도구 호출 · 모델 턴 · 토큰
★DB 는 원장 DB 하나(`--dsn`, 기본 로컬 `dining_rebuild`). 기대 판정은 자료를 만든 날 규칙으로 얼린 값이다(`scripts/dining/make_agent_eval.py`).
★키 · 주소 — OpenAI 는 `.env` 의 `ACOP_OPENAI_API_KEY`(개인 키 — 개발 평가용), gemma 는 `--ollama`(기본 http://localhost:11434). 값은 찍지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from math import comb
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "datasets" / "dining_agent_v1.jsonl"
KST = ZoneInfo("Asia/Seoul")
#: gpt-4o-mini 단가(USD / 1M 토큰) — 비용 어림. 다른 모델은 비용을 적지 않는다
PRICE = {"gpt-4o-mini": (0.15, 0.60), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1": (2.0, 8.0)}


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def make_chat(spec: str, ollama: str) -> tuple[Any, str]:
    kind, _, model = spec.partition(":")
    if kind == "openai":
        from app.core.settings import get_settings
        from app.infrastructure.llm.tool_chat import OpenAIToolChat

        model = model or "gpt-4o-mini"
        return OpenAIToolChat(api_key=get_settings().openai_api_key, model=model), model
    if kind == "gemma":
        from app.infrastructure.llm.tool_chat import OllamaToolChat

        model = model or "gemma4:e4b"
        return OllamaToolChat(base_url=ollama, model=model, timeout=600), model
    raise SystemExit(f"모르는 모델: {spec}")


def score(case: dict[str, Any], reported: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """식사 항목마다 — 골라야 할 체크의 정답 여부 · 빠뜨림 · 쓸데없는 체크."""
    rows = []
    for item_id, expect in case["expect"].items():
        got = reported.get(item_id, {})
        for check in expect["must"]:
            rows.append({"case": case["id"], "item": item_id, "check": check, "kind": "must",
                         "expected": expect["verdicts"][check], "got": got.get(check),
                         "correct": got.get(check) == expect["verdicts"][check]})
        for check in expect["must_not"]:
            if check in got:
                rows.append({"case": case["id"], "item": item_id, "check": check, "kind": "unnecessary", "got": got[check]})
    return rows


def run_rule(case: dict[str, Any]) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """C — 지금 코드: 찾기 · 영업만(규칙 값 그대로). 자유 문장 조건은 안 본다."""
    return ({item_id: {c: e["verdicts"][c] for c in ("found", "open_at")} for item_id, e in case["expect"].items()},
            {"seconds": 0.0, "tool_calls": 0, "turns": 0})


def run_agent(case: dict[str, Any], *, chat: Any, connect: Any, mode: str) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    from app.domains.travel_ops.instances.dining.agent import judge_day
    from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

    tools = DiningTools(connect)
    result = judge_day(case["plan"], tools=tools, chat=chat, mode=mode, deadline_s=900)
    reported: dict[str, dict[str, str]] = {}
    for item in result.items:
        for check in item["checks"]:
            reported.setdefault(str(item.get("item_id")), {})[check.get("check")] = check.get("verdict")
    failures = Counter(c.get("failure") for item in result.items for c in item["checks"] if c.get("failure"))
    return reported, {**result.stats, "failure": result.failure, "validation": dict(failures),
                      "tools_used": dict(Counter(c["tool"] for c in result.tool_calls))}


def mcnemar(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    """(기준 맞음, 비교 맞음) 쌍 — 정확검정(이항)."""
    b = sum(1 for base, other in pairs if not base and other)
    c = sum(1 for base, other in pairs if base and not other)
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n)
    return {"only_new_correct": b, "only_base_correct": c, "p": round(p, 4)}


def summarize(rows: list[dict[str, Any]], runs: list[dict[str, Any]], model: str | None) -> dict[str, Any]:
    def ratio(num: int, den: int) -> dict[str, Any]:
        return {"num": num, "den": den, "rate": round(num / den, 3) if den else None}

    must = [r for r in rows if r["kind"] == "must"]
    seconds = sorted(r["seconds"] for r in runs)
    prompt, completion = sum(r.get("prompt_tokens", 0) for r in runs), sum(r.get("completion_tokens", 0) for r in runs)
    out = {
        "must_accuracy": ratio(sum(r["correct"] for r in must), len(must)),
        "missing": ratio(sum(r["got"] is None for r in must), len(must)),
        "wrong_verdict": ratio(sum(r["got"] is not None and not r["correct"] for r in must), len(must)),
        "unnecessary": len([r for r in rows if r["kind"] == "unnecessary"]),
        "by_check": {c: ratio(sum(r["correct"] for r in must if r["check"] == c), sum(r["check"] == c for r in must))
                     for c in sorted({r["check"] for r in must})},
        "by_expected": {v: ratio(sum(r["correct"] for r in must if r["expected"] == v), sum(r["expected"] == v for r in must))
                        for v in sorted({r["expected"] for r in must})},
        "runs": len(runs), "run_failures": dict(Counter(r.get("failure") for r in runs if r.get("failure"))),
        "validation_failures": sum(sum((r.get("validation") or {}).values()) for r in runs),
        "seconds_mean": round(sum(seconds) / len(seconds), 2) if seconds else None,
        "seconds_p95": seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))] if seconds else None,
        "tool_calls_mean": round(sum(r.get("tool_calls", 0) for r in runs) / len(runs), 1) if runs else None,
        "turns_mean": round(sum(r.get("turns", 0) for r in runs) / len(runs), 1) if runs else None,
        "tokens": {"prompt": prompt, "completion": completion},
    }
    if model in PRICE:
        price_in, price_out = PRICE[model]
        out["usd"] = round(prompt * price_in / 1e6 + completion * price_out / 1e6, 4)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", required=True)
    parser.add_argument("--config", choices=("rule", "agent", "direct"), required=True)
    parser.add_argument("--model", default="openai:gpt-4o-mini", help="openai:<모델> · gemma:<모델>")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--dsn", default="postgresql://postgres@127.0.0.1:5433/dining_rebuild")
    parser.add_argument("--ollama", default="http://localhost:11434")
    parser.add_argument("--baseline", type=Path, help="비교할 앞 리포트(JSON) — 첫 판끼리 McNemar")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    import psycopg

    @contextmanager
    def connect():
        with psycopg.connect(args.dsn, autocommit=True) as conn:
            yield conn

    cases = load(args.dataset)
    chat, model = (None, None) if args.config == "rule" else make_chat(args.model, args.ollama)
    repeats = 1 if args.config == "rule" else args.repeats
    rows, runs, first = [], [], []
    partial = args.out.with_suffix(".partial.jsonl") if args.out else None
    if partial is not None and partial.exists():
        partial.unlink()
    for repeat in range(repeats):
        for case in cases:
            try:
                if args.config == "rule":
                    reported, stats = run_rule(case)
                else:
                    reported, stats = run_agent(case, chat=chat, connect=connect,
                                                mode="rule_tools" if args.config == "agent" else "llm_direct")
            except Exception as exc:                      # noqa: BLE001 — 한 시나리오가 죽어도 나머지는 잰다(세어 남긴다)
                reported, stats = {}, {"seconds": 0.0, "failure": f"runner_error:{type(exc).__name__}: {str(exc)[:120]}"}
            got = score(case, reported)
            for row in got:
                row["repeat"] = repeat
            rows += got
            runs.append({"case": case["id"], "repeat": repeat, **stats, "reported": reported})
            if partial is not None:                       # ☆`[2026-10-13]` 판마다 바로 쓴다 — 로컬 gemma 를 중간에 멈췄을 때 결과를 다 잃었다
                with partial.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"run": runs[-1], "rows": got}, ensure_ascii=False) + "\n")
            if repeat == 0:
                first += [r for r in got if r["kind"] == "must"]
            ok = sum(r["correct"] for r in got if r["kind"] == "must")
            total = sum(r["kind"] == "must" for r in got)
            extra = [r["check"] for r in got if r["kind"] == "unnecessary"]
            print(f"[{repeat}] {case['id']} {ok}/{total} {('+' + ','.join(extra)) if extra else ''} "
                  f"{stats.get('failure') or ''} {stats.get('validation') or ''} {stats.get('seconds')}s", file=sys.stderr)
    report = {"eval": "dining_agent", "label": args.label, "config": args.config, "model": model,
              "dataset": args.dataset.name, "dataset_sha": hashlib.sha256(args.dataset.read_bytes()).hexdigest()[:16],
              "repeats": repeats, "run_at": datetime.now(KST).isoformat(timespec="seconds"),
              "summary": summarize(rows, runs, model), "rows": rows, "runs": runs}
    if args.baseline:
        base = json.loads(args.baseline.read_text(encoding="utf-8"))
        key = lambda r: (r["case"], r["item"], r["check"])          # noqa: E731
        base_first = {key(r): r["correct"] for r in base["rows"] if r["kind"] == "must" and r.get("repeat", 0) == 0}
        report["vs_baseline"] = {"baseline": base["label"],
                                 **mcnemar([(base_first[key(r)], r["correct"]) for r in first if key(r) in base_first])}
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"summary": report["summary"], **({"vs_baseline": report["vs_baseline"]} if args.baseline else {})},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
