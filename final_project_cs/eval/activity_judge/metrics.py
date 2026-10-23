# -*- coding: utf-8 -*-
"""활동 판정 평가 지표 — 분자/분모와 함께 낸다(RULE §1.4).

★CI 는 **항목(case) 단위 군집 부트스트랩**이다. 같은 항목의 반복 3회는 서로 독립이 아니라서,
  관측 하나하나를 뽑으면 CI 가 실제보다 좁아진다. 항목을 뽑고 그 항목의 반복을 통째로 넣는다.
★비용은 **추정**이다 — 2026-10-06 OpenAI 가격 문서의 gpt-5.4-nano 요율(입력 $0.2 · 출력 $1.25 / 1M)과
  웹 검색 $10 / 1k calls 를 쓰고, `web_search_call` 항목 하나를 1회로 센다(과금 단위는 확인 필요 — 계획서 §3).
"""
from __future__ import annotations

import random
import statistics
from collections import defaultdict
from typing import Any

PRICE_INPUT_PER_TOKEN = 0.2 / 1_000_000
PRICE_OUTPUT_PER_TOKEN = 1.25 / 1_000_000
PRICE_PER_SEARCH = 10.0 / 1000
FAILURES = ("llm_timeout", "llm_schema_invalid", "llm_error")


def outcome(value: str, acceptable: list[str]) -> str:
    """`correct` · `dangerous`(확정 값인데 허용 밖) · `safe_unknown`(모름인데 모름이 허용 밖)."""
    if value in acceptable:
        return "correct"
    return "safe_unknown" if value == "unknown" else "dangerous"


def cluster_bootstrap(per_case: dict[str, list[float]], *, n: int = 10000, seed: int = 7) -> tuple[float, float, float]:
    """항목별 관측 목록 → (평균, 2.5%, 97.5%). 평균은 항목 평균의 평균이다."""
    case_means = [sum(v) / len(v) for v in per_case.values() if v]
    if not case_means:
        raise ValueError("no observations")
    rng = random.Random(seed)
    draws = sorted(sum(rng.choice(case_means) for _ in case_means) / len(case_means) for _ in range(n))
    pick = lambda p: draws[min(len(draws) - 1, int(p * len(draws)))]  # noqa: E731
    return sum(case_means) / len(case_means), pick(0.025), pick(0.975)


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p * (len(ordered) - 1))))]


def call_cost(row: dict[str, Any]) -> float:
    return ((row.get("input_tokens") or 0) * PRICE_INPUT_PER_TOKEN
            + (row.get("output_tokens") or 0) * PRICE_OUTPUT_PER_TOKEN
            + (row.get("search_calls") or 0) * PRICE_PER_SEARCH)


def summarize(rows: list[dict[str, Any]], *, n_boot: int = 10000, seed: int = 7) -> dict[str, Any]:
    """`rows` — 관측 하나(항목 × 반복)마다 `case_id`·`kind`·`acceptable`·`labeled`·`rule`·`llm`·계측."""
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_kind[row["kind"]].append(row)
    out: dict[str, Any] = {"kinds": {}}
    labeled_all = [r for r in rows if r["labeled"]]
    groups = {**{k: v for k, v in by_kind.items()}, "_labeled_all": labeled_all}
    for kind, items in groups.items():
        if not items:
            continue
        out["kinds"][kind] = _summarize_group(items, n_boot=n_boot, seed=seed)
    out["cost_usd_total"] = round(sum(call_cost(r) for r in rows), 6)
    out["observations"] = len(rows)
    return out


def _summarize_group(items: list[dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    cases = sorted({r["case_id"] for r in items})
    obs = len(items)
    group: dict[str, Any] = {"cases": len(cases), "observations": obs}
    labeled = [r for r in items if r["labeled"]]
    if labeled:
        llm_ok: dict[str, list[float]] = defaultdict(list)
        rule_ok: dict[str, list[float]] = defaultdict(list)
        delta: dict[str, list[float]] = defaultdict(list)
        counts = {"llm": defaultdict(int), "rule": defaultdict(int)}
        rule_seen: set[str] = set()
        for r in labeled:
            lo = outcome(r["llm"], r["acceptable"])
            ro = outcome(r["rule"], r["acceptable"])
            counts["llm"][lo] += 1
            if r["case_id"] not in rule_seen:      # 규칙은 결정적 — 항목당 한 번만 센다
                counts["rule"][ro] += 1
                rule_seen.add(r["case_id"])
            llm_ok[r["case_id"]].append(1.0 if lo == "correct" else 0.0)
            rule_ok[r["case_id"]].append(1.0 if ro == "correct" else 0.0)
            delta[r["case_id"]].append((1.0 if lo == "correct" else 0.0) - (1.0 if ro == "correct" else 0.0))
        lm, llo, lhi = cluster_bootstrap(llm_ok, n=n_boot, seed=seed)
        rm, rlo, rhi = cluster_bootstrap(rule_ok, n=n_boot, seed=seed)
        dm, dlo, dhi = cluster_bootstrap(delta, n=n_boot, seed=seed)
        n_lab_cases = len(rule_seen)
        group["llm_accuracy"] = {"value": lm, "ci95": [llo, lhi], "num": counts["llm"]["correct"], "den": len(labeled)}
        group["rule_accuracy"] = {"value": rm, "ci95": [rlo, rhi], "num": counts["rule"]["correct"], "den": n_lab_cases}
        group["llm_minus_rule"] = {"value": dm, "ci95": [dlo, dhi], "paired_cases": n_lab_cases}
        group["llm_dangerous"] = {"num": counts["llm"]["dangerous"], "den": len(labeled)}
        group["llm_safe_unknown"] = {"num": counts["llm"]["safe_unknown"], "den": len(labeled)}
        group["rule_dangerous"] = {"num": counts["rule"]["dangerous"], "den": n_lab_cases}
        group["rule_safe_unknown"] = {"num": counts["rule"]["safe_unknown"], "den": n_lab_cases}
    group["llm_unknown"] = {"num": sum(r["llm"] == "unknown" for r in items), "den": obs}
    group["llm_uncited"] = {"num": sum(r.get("failure_code") == "llm_uncited" for r in items), "den": obs}
    group["llm_call_failed"] = {"num": sum(r.get("failure_code") in FAILURES for r in items), "den": obs}
    comparable = [r for r in items if r["llm"] != "unknown" and r["rule"] != "unknown"]
    group["agree_with_rule"] = {"num": sum(r["llm"] == r["rule"] for r in comparable), "den": len(comparable)}
    by_case: dict[str, set[str]] = defaultdict(set)
    for r in items:
        by_case[r["case_id"]].add(r["llm"])
    group["consistent_cases"] = {"num": sum(len(v) == 1 for v in by_case.values()), "den": len(by_case)}
    latencies = [r["latency_ms"] for r in items if r.get("latency_ms") is not None]
    group["latency_ms"] = {"p50": _pct(latencies, 0.5), "p95": _pct(latencies, 0.95), "n": len(latencies)}
    group["search_calls_mean"] = (statistics.mean(r.get("search_calls") or 0 for r in items) if items else None)
    group["citations_kept"] = {"num": sum(r.get("citations") or 0 for r in items), "obs": obs}
    group["undated_citations"] = sum(r.get("undated_citations") or 0 for r in items)
    group["cost_usd_per_call_mean"] = round(statistics.mean(call_cost(r) for r in items), 6)
    return group
