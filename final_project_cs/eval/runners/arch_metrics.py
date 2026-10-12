# -*- coding: utf-8 -*-
"""아키텍처 산출물 5절용 측정 — 여행 평가 시나리오(`travel_scenarios`)를 그대로 돌리며 세 가지를 센다. `[2026-10-06]`

1. 변경 초안 체크리스트 — 초안 고르기(`itinerary_fit.fit_change`)가 부를 때마다 **1순위가 바로 통과했나 · 몇 순위를 썼나 ·
   다 걸렸나**, 건너뛴 까닭(일정과 안 맞음 / 하루 밀도). 적용된 모든 일정 버전의 필수 조건 위반은 러너가 이미 센다.
2. 처리 시간 — 감시 회차(`tick`) · 고객 한 통(`say` · `swap` · `rollback`)의 벽시계 시간. 회차가 끝나면 알림이 바깥함(outbox)에 들어가 있다.
   ★바깥함 → 디스코드 발송(일꾼 주기 60초)은 여기 안 들어간다 — 따로 더한다.
3. 같은 회차를 한 번 더 돌렸을 때 새로 생긴 알림 · 일정 버전(중복 방지 확인).

★언어 모델은 흉내(분류 · 추출 — 러너와 같음), 외부 소스는 재생, DB 는 로컬 개발 DB. 제품 코드를 고치지 않고 함수만 감싼다.

    python -m eval.runners.arch_metrics --repeat 3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from eval.runners import travel_scenarios as ts

FITS: list[dict[str, Any]] = []
TIMES: list[dict[str, Any]] = []
RETICK: list[dict[str, Any]] = []


def _wrap_fit() -> None:
    from app.domains.travel_ops.components.itinerary import itinerary_fit
    from app.domains.travel_ops.components.watch import trip_watch_batch
    from app.domains.travel_ops.instances._shared import itinerary_team

    original = itinerary_fit.fit_change

    def counted(change, *, trip, items):
        fit = original(change, trip=trip, items=items)
        FITS.append({"case": CURRENT.get("case"), "rank": fit.rank, "chosen": fit.change is not None,
                     "options": 1 + len(getattr(change, "fallbacks", None) or []),
                     "skipped": [{"rank": s.rank, "why": s.why, "reasons": s.reasons} for s in fit.skipped]})
        return fit

    itinerary_fit.fit_change = counted
    trip_watch_batch.fit_change = counted
    itinerary_team.fit_change = counted


CURRENT: dict[str, Any] = {}


def _outbox_count(tenant: str) -> int:
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice'", (tenant,))
        return int(cur.fetchone()[0])


def _version(store, trip_id) -> int:
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn:
        trip, _ = store.latest(conn, trip_id)
    return int(trip["version"])


def _wrap_step() -> None:
    original = ts._step

    def timed(step, *, engine, store, trip_id, customer, clock, at, reports, counts):
        tenant = engine.tenant_id
        before = _outbox_count(tenant)
        start = time.perf_counter()
        result = original(step, engine=engine, store=store, trip_id=trip_id, customer=customer, clock=clock,
                          at=at, reports=reports, counts=counts)
        seconds = time.perf_counter() - start
        after = _outbox_count(tenant)
        kind = step.partition(":")[0]
        TIMES.append({"case": CURRENT.get("case"), "step": step, "kind": kind, "seconds": seconds,
                      "notices": after - before, "opened": result.get("opened")})
        if kind == "tick":
            version = _version(store, trip_id)
            engine.tick()                               # 같은 시각 · 같은 사건으로 한 번 더
            RETICK.append({"case": CURRENT.get("case"), "step": step,
                           "new_notices": _outbox_count(tenant) - after,
                           "new_versions": _version(store, trip_id) - version})
        return result

    ts._step = timed


def _pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    k = max(0, min(len(ordered) - 1, round(q * (len(ordered) - 1))))
    return ordered[k]


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    _wrap_fit()
    _wrap_step()
    specs = [json.loads(line) for line in Path(ts.DATASET).read_text(encoding="utf-8").splitlines() if line.strip()]
    outcomes = []
    for round_no in range(1, args.repeat + 1):
        for spec in specs:
            CURRENT["case"] = f"{spec['case_id']}#{round_no}"
            outcome = ts.run_case(spec)
            outcomes.append({"case": CURRENT["case"], "passed": outcome["verdict"]["passed"],
                             "failures": outcome["verdict"]["failures"],
                             "violations": len(outcome["violations"]), "versions": outcome["versions"],
                             "notices": outcome["notices"], "cases": outcome["cases"]})
            print(f"  {CURRENT['case']:<20} {'통과' if outcome['verdict']['passed'] else '실패'} · 위반 {len(outcome['violations'])}")

    first = [f for f in FITS if f["chosen"] and f["rank"] == 1]
    later = [f for f in FITS if f["chosen"] and f["rank"] > 1]
    none = [f for f in FITS if not f["chosen"]]
    skips = [s for f in FITS for s in f["skipped"]]
    ticks = [t["seconds"] for t in TIMES if t["kind"] == "tick" and t["notices"] > 0]
    quiet = [t["seconds"] for t in TIMES if t["kind"] == "tick" and t["notices"] == 0]
    talks = [t["seconds"] for t in TIMES if t["kind"] != "tick"]
    summary = {
        "scenario_runs": len(outcomes), "scenario_passed": sum(o["passed"] for o in outcomes),
        "violations": sum(o["violations"] for o in outcomes),
        "fit_calls": len(FITS), "first_rank_pass": len(first), "later_rank_pass": len(later), "all_failed": len(none),
        "skip_why": {why: sum(1 for s in skips if s["why"] == why) for why in ("schedule", "density")},
        "tick_with_notice_s": {"n": len(ticks), "p50": _pct(ticks, .5), "p95": _pct(ticks, .95), "max": max(ticks, default=0)},
        "tick_quiet_s": {"n": len(quiet), "p50": _pct(quiet, .5), "p95": _pct(quiet, .95)},
        "message_s": {"n": len(talks), "p50": _pct(talks, .5), "p95": _pct(talks, .95), "max": max(talks, default=0)},
        "retick": {"n": len(RETICK), "new_notices": sum(r["new_notices"] for r in RETICK),
                   "new_versions": sum(r["new_versions"] for r in RETICK)},
        "rollback_steps": [t for t in TIMES if t["kind"] == "rollback"],
    }
    run_id = datetime.now(ts.KST).strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else ts.REPORTS / f"arch_metrics_{run_id}.json"
    out.write_text(json.dumps({"run_id": run_id, "repeat": args.repeat, "llm": "흉내(분류·추출)", "sources": "재생",
                               "summary": summary, "outcomes": outcomes, "fits": FITS, "times": TIMES, "retick": RETICK},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
