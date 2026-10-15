"""앞으로 곧 시작하는 활동 장소의 **실시간 운영 상태(임시휴무 · 폐업)** 를 웹 공지로 한 번 확인해 저장한다 — `activity.ac_live_status`. `[2026-10-13]`

★왜. 관광공사 운영 정보는 「매주 화요일 휴무」 같은 정기 규칙이라 수요일 당일 사고(임시휴무 · 공사 · 폐업)를 담지 못한다.
  그렇다고 고객 요청마다 웹을 부르면 비용이 요청 수에 비례하고 응답이 느리다(p95 40.7초 · 429). 그래서 **장소 · 날짜당 한 번**
  이 배치가 확인해 저장하고, 고객 요청(`team._live_status_check`)은 저장된 값만 읽는다. 경복궁을 100명이 가도 한 번이다.

★대상. 지금부터 `travel.activity_judge.live_status_within_hours`(기본 72시간) 안에 시작하는 **일정 항목 과 예약**의 (장소, 날짜).
  `[2026-10-14]` 예약을 더했다 — 예약 성립 판정(`read.booking`)은 일정이 아니라 예약을 읽는데, 일정에 걸리지 않은 예약은
  배치가 안 봐서 늘 「미확인」이었다(코어 회신 10-13). 활동 원장에 있는 장소만 걸린다.
★시간대. 코어 정기 점검 창(03:00~08:00 KST — `travel.activity_judge.live_status_window`) **밖이면 돌지 않는다**
  (`run_once` 가 `{"skipped": "outside_window"}` 를 돌려준다). 수동 실행은 `--force` 로 창을 건너뛴다.
★호출 수. 한 (장소, 날짜)는 시작까지 `live_status_near_hours`(기본 24) 보다 **멀면 한 번**, **임박하면 `--recheck-hours`(기본 6)
  마다 한 번** 부른다 — 하루 한 번 도는 창 기준 최대 2회(72시간 앞 + 임박 재확인). 전에는 6시간 재확인 하나라 같은 곳을 3번까지 불렀다.
  모름(`unknown`)도 줄로 남겨 같은 곳을 계속 다시 부르지 않는다.
★예산. 호출마다 `activity_judge_web` 예산(`CallBudget` — DB)을 확인한다. 넘으면 거기서 멈추고 남은 곳을 보고한다.
★켜는 법. 전역 `ACOP_ACTIVITY_JUDGE_MODE` 가 `rule` 이면(기본) 판정 LLM 이 없어 아무것도 하지 않는다 — `shadow` 로 두고 돌린다.
  `kind_modes.live_status` 가 `rule` 이면 이 배치도 돌지 않는다. 저장 결과를 고객 답에 쓰는 것은 `llm` 일 때만이다(`shadow` 는 기록만).

코어 작업 실행기는 `run_once()` 를 부른다(인자 없음 = 창 안일 때만, 기본 시각 · 기본 한도).

사용법
    python scripts/activity/check_live_status.py --dry-run    대상만 센다(웹을 부르지 않는다)
    python scripts/activity/check_live_status.py              확인해 저장(창 밖이면 아무것도 안 한다)
    python scripts/activity/check_live_status.py --force      창 밖에서도 수동으로
    python scripts/activity/check_live_status.py --limit 20   20곳만
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#: 지금부터 N시간 안에 시작하는 (장소, 날짜) — 한 날짜에 같은 장소가 여럿이면 가장 이른 시각 하나.
#: ★일정은 버전으로 쌓이므로 `trips.latest_version` 의 항목만 본다(지난 버전을 세지 않는다).
#: ★`[2026-10-14]` 일정 항목에 더해 **예약**(취소 아님)도 본다 — 일정에 안 걸린 예약이 「미확인」으로 남지 않게.
_TARGETS_SQL = """
SELECT content_id, name_ko, address, visit_date, min(starts_at) AS starts_at
FROM (
    SELECT a.content_id, a.name_ko, concat_ws(' ', a.addr1, a.addr2) AS address,
           (i.starts_at AT TIME ZONE 'Asia/Seoul')::date AS visit_date, i.starts_at
    FROM trips t
    JOIN itinerary_items i ON i.trip_id = t.trip_id AND i.version = t.latest_version
    JOIN places p ON p.place_id = i.place_id
    JOIN activity.ac_place a ON a.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id')
    WHERE t.status = 'active' AND i.kind = 'activity'
      AND i.starts_at >= %(now)s AND i.starts_at < %(now)s + (%(hours)s || ' hours')::interval
  UNION ALL
    SELECT a.content_id, a.name_ko, concat_ws(' ', a.addr1, a.addr2) AS address,
           (b.starts_at AT TIME ZONE 'Asia/Seoul')::date AS visit_date, b.starts_at
    FROM bookings b
    JOIN places p ON p.place_id = b.place_id
    JOIN activity.ac_place a ON a.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id')
    WHERE b.status <> 'cancelled'
      AND b.starts_at >= %(now)s AND b.starts_at < %(now)s + (%(hours)s || ' hours')::interval
) targets
GROUP BY 1, 2, 3, 4
ORDER BY min(starts_at), content_id
"""


@dataclass
class Target:
    content_id: str
    name: str
    address: str | None
    visit_date: date
    starts_at: datetime


def find_targets(conn, now: datetime, within_hours: float) -> list[Target]:
    with conn.cursor() as cur:
        cur.execute(_TARGETS_SQL, {"now": now, "hours": str(within_hours)})
        rows = cur.fetchall()
    return [Target(str(c), n, (addr or "").strip() or None, d, s) for c, n, addr, d, s in rows]


def check_targets(targets: list[Target], *, read_row: Callable[[Target], dict | None],
                  judge: Callable[[Target], Any], budget: Callable[[str], bool],
                  record: Callable[[Target, Any], None], now: datetime, recheck_hours: float = 6.0,
                  limit: int | None = None, near_hours: float | None = None) -> dict[str, int]:
    """대상을 하나씩 확인해 저장한다. 한 곳이 실패해도 멈추지 않고 세어 보고한다(분모를 줄이지 않는다).

    `near_hours` — 시작까지 이보다 **먼** 대상은 줄이 있으면(언제 확인했든) 다시 부르지 않는다. 임박하면 `recheck_hours` 로 본다.
    `None` 이면 모든 대상을 `recheck_hours` 로 본다."""
    from app.domains.travel_ops.instances.activity import live_store

    out = {"targets": len(targets), "fresh": 0, "checked": 0, "closed": 0, "open": 0, "unknown": 0, "failed": 0,
           "budget_stop": 0, "left": 0}
    asked = 0
    for index, target in enumerate(targets):
        row = read_row(target)
        far = near_hours is not None and (target.starts_at - now) > timedelta(hours=near_hours)
        if (row is not None and far) or live_store.fresh(row, now, recheck=timedelta(hours=recheck_hours)):
            out["fresh"] += 1
            continue
        if limit is not None and asked >= limit:
            out["left"] += 1
            continue
        try:
            if not budget("live_status"):
                out["budget_stop"] = 1
                out["left"] += len(targets) - index        # 이 곳부터 남은 곳(이미 센 fresh 는 뺐다)
                break
        except Exception:  # noqa: BLE001 — 세지 못하면 부르지 않는다(판정 계층과 같다)
            out["budget_stop"] = 1
            out["left"] += len(targets) - index
            break
        asked += 1
        try:
            verdict = judge(target)
            record(target, verdict)
        except Exception as exc:  # noqa: BLE001 — 한 곳의 실패가 배치를 멈추지 않는다. 세어서 보고한다
            out["failed"] += 1
            print(f"  ! {target.name}({target.content_id}) {target.visit_date}: {type(exc).__name__}")
            continue
        out["checked"] += 1
        out[verdict.value if verdict.known else "unknown"] += 1
    return out


def _judge_factory():
    """실제 웹 검색 판정 — 코어 조립과 같은 어댑터 · 같은 검증(`LLMJudge`). 판정 LLM 이 없으면 `None`."""
    from app.composition import build_activity_judge_llm
    from app.domains.travel_ops.instances.activity.judge import requests as judge_requests
    from app.domains.travel_ops.instances.activity.judge.llm import LLMJudge
    from app.domains.travel_ops.instances.activity.judge.types import JudgeContext

    llm = build_activity_judge_llm()
    if llm is None:
        return None
    judge = LLMJudge(llm)

    def run(target: Target):
        request = judge_requests.live_status(target.name, "activity", target.address, target.starts_at)
        return asyncio.run(judge.judge(JudgeContext(capability="activity.live_status_batch"), request))

    return run


def _budget():
    """웹 검색 호출 예산 — 판정 종류 → 「불러도 되나」. `external_call_budget` 의 줄(`activity_judge_web`)을 DB 로 센다.

    ★조립(`app.composition.build_activity_judge_budget`)은 코어 파일이라 develop 에 없을 수 있어 쓰지 않는다 — 같은 부품(`CallBudget` ·
      `budget_caps` · `budget_meter`)을 직접 쓴다. 상한은 `guardrails.yaml travel.activity_judge.budget`. 넘거나 세지 못하면 부르지 않는다."""
    from app.domains.travel_ops.instances.activity.judge.modes import budget_caps, budget_meter
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
    from app.infrastructure.db.session import get_connection

    budget = CallBudget(connection_factory=get_connection, caps=budget_caps())
    return lambda kind: budget.try_reserve(budget_meter(kind))


def in_window(now: datetime, start_hour: int, end_hour: int) -> bool:
    """`now`(시간대 있는 시각)가 한국 시간 `[start_hour, end_hour)` 안인가."""
    from zoneinfo import ZoneInfo

    return start_hour <= now.astimezone(ZoneInfo("Asia/Seoul")).hour < end_hour


def run_once(now: datetime | None = None, *, dry_run: bool = False, limit: int | None = None,
             within_hours: float | None = None, recheck_hours: float = 6.0, near_hours: float | None = None,
             enforce_window: bool = True, report: Callable[[str], None] = print) -> dict[str, Any]:
    """한 회차 — 코어 작업 실행기가 부르는 입구. `[2026-10-14]`

    꺼져 있으면(`rule`) `{"skipped": "mode_rule"}`, 창(`live_status_window`) 밖이면 `{"skipped": "outside_window"}` — DB 도 웹도
    건드리지 않는다. 판정 LLM 이 없으면 `{"skipped": "no_judge_llm"}`. 조용히 끝내지 않고 부른 쪽이 이유를 본다."""
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.instances.activity import live_store
    from app.domains.travel_ops.instances.activity.judge.modes import kind_mode
    from app.infrastructure.db.session import get_connection

    guard = get_guardrails()
    now = now or datetime.now(timezone.utc)
    if kind_mode("live_status") == "rule":
        return {"skipped": "mode_rule"}
    if enforce_window:
        window = guard.get("travel.activity_judge.live_status_window")
        if not in_window(now, int(window["start_hour"]), int(window["end_hour"])):
            return {"skipped": "outside_window"}
    within = within_hours or float(guard.get("travel.activity_judge.live_status_within_hours"))
    near = near_hours if near_hours is not None else float(guard.get("travel.activity_judge.live_status_near_hours"))

    with get_connection() as conn:
        targets = find_targets(conn, now, within)
    report(f"앞으로 {within:g}시간 안에 시작하는 활동 (장소 · 날짜) {len(targets):,}곳")
    if dry_run:
        for t in targets[:20]:
            report(f"  {t.visit_date} {t.name} ({t.content_id})")
        return {"targets": len(targets), "dry_run": True}
    judge = _judge_factory()
    if judge is None:
        return {"skipped": "no_judge_llm", "targets": len(targets)}
    model = os.environ.get("ACOP_ACTIVITY_JUDGE_MODEL") or None

    def read_row(target: Target):
        with get_connection() as conn:
            return live_store.read(conn, target.content_id, target.visit_date)

    def record(target: Target, verdict) -> None:
        citations = [{"url": c.get("url"), "quote": c.get("quote"), "published_at": c.get("published_at")}
                     for c in verdict.citations if isinstance(c, dict)]
        value = verdict.value if verdict.known else "unknown"
        if value == "closed" and not citations:        # 근거 없는 「닫혔다」는 저장하지 않는다
            value = "unknown"
        with get_connection() as conn, conn.transaction():
            live_store.record(conn, target.content_id, target.visit_date, value, citations=citations,
                              basis=verdict.basis or verdict.failure_code, model=model)

    result = check_targets(targets, read_row=read_row, judge=judge, budget=_budget(), record=record, now=now,
                           recheck_hours=recheck_hours, limit=limit, near_hours=near)
    report(f"확인 {result['checked']:,}곳 (닫힘 {result['closed']:,} · 열림 {result['open']:,} · 모름 {result['unknown']:,})"
           f" · 최근에 확인해 건너뜀 {result['fresh']:,} · 실패 {result['failed']:,} · 남음 {result['left']:,}")
    if result["budget_stop"]:
        report("★웹 검색 예산이 다 찼다 — 남은 곳은 다음 실행에서 확인한다(travel.activity_judge.budget.web)")
    return result


_SKIP_REASONS = {
    "outside_window": "정기 점검 창(travel.activity_judge.live_status_window) 밖이다 — 수동이면 --force",
    "mode_rule": "kind_modes.live_status 가 rule 이다 — 실시간 운영 확인이 꺼져 있다",
    "no_judge_llm": "판정 LLM 이 없다 — ACOP_ACTIVITY_JUDGE_MODE 를 shadow 로 두고 OpenAI 키를 확인한다",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="대상만 센다 — 웹을 부르지 않고 저장도 하지 않는다")
    parser.add_argument("--limit", type=int, default=None, help="이번에 확인할 최대 곳 수")
    parser.add_argument("--within-hours", type=float, default=None,
                        help="지금부터 N시간 안에 시작하는 일정(기본: guardrails travel.activity_judge.live_status_within_hours)")
    parser.add_argument("--recheck-hours", type=float, default=6.0, help="임박한 대상은 이 시간 안에 확인했으면 건너뛴다")
    parser.add_argument("--near-hours", type=float, default=None,
                        help="시작까지 이보다 먼 대상은 한 번 확인했으면 다시 안 부른다(기본: guardrails live_status_near_hours)")
    parser.add_argument("--force", action="store_true", help="정기 점검 창(03:00~08:00) 밖에서도 돈다 — 수동 실행용")
    args = parser.parse_args()

    result = run_once(dry_run=args.dry_run, limit=args.limit, within_hours=args.within_hours,
                      recheck_hours=args.recheck_hours, near_hours=args.near_hours, enforce_window=not args.force)
    if "skipped" in result:
        raise SystemExit(_SKIP_REASONS[result["skipped"]])


if __name__ == "__main__":
    main()
