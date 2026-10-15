# -*- coding: utf-8 -*-
"""실시간 운영 상태(임시휴무 · 폐업) **웹 확인 배치의 부품** — 손으로 돌리는 스크립트와 새벽 정기 작업이 같이 쓴다. `[2026-10-14]`

    손으로     `scripts/activity/check_live_status.py`  (대상 세기 · 확인 · 저장, 출력은 글)
    정기 작업  `instances/activity/jobs.py`            (새벽 정기점검 창에서 1분마다 조금씩 · 남은 건수를 실행기에 알린다)

★전에는 이 부품이 스크립트 안에만 있어 정기 작업이 쓸 수 없었다(활동 → 코어 전달 사항 10-13 2번 「배치 등록」).
  내용은 스크립트에 있던 그대로다 — 대상 SQL · 「최근에 본 곳 건너뛰기」 · 예산 · 저장 규칙. 바뀐 것은 둘이다:
  ① 대상을 회사(`tenant_id`)로 좁힐 수 있다(정기 작업은 회사마다 불린다. 스크립트는 전부).
  ② `pending` — 아직 확인하지 않은 곳의 수(= 정기점검의 「오늘 남은 건수」). 실행기가 03:30 뒤 「안 끝남」을 판정하는 데 쓴다.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.domains.travel_ops.instances.activity import live_store

#: 지금부터 N시간 안에 시작하는 활동 항목의 (장소, 날짜) — 한 날짜에 같은 장소가 여럿이면 가장 이른 시각 하나.
#: ★일정은 버전으로 쌓이므로 `trips.latest_version` 의 항목만 본다(지난 버전을 세지 않는다).
_TARGETS_SQL = """
SELECT a.content_id, a.name_ko, concat_ws(' ', a.addr1, a.addr2) AS address,
       (i.starts_at AT TIME ZONE 'Asia/Seoul')::date AS visit_date, min(i.starts_at) AS starts_at
FROM trips t
JOIN itinerary_items i ON i.trip_id = t.trip_id AND i.version = t.latest_version
JOIN places p ON p.place_id = i.place_id
JOIN activity.ac_place a ON a.content_id = COALESCE(p.source_content_id, p.attributes->>'source_content_id')
WHERE t.status = 'active' AND i.kind = 'activity'
  AND i.starts_at >= %s AND i.starts_at < %s + (%s || ' hours')::interval
  AND (%s::text IS NULL OR t.tenant_id = %s::text)
GROUP BY 1, 2, 3, 4
ORDER BY min(i.starts_at), a.content_id
"""


@dataclass
class Target:
    content_id: str
    name: str
    address: str | None
    visit_date: date
    starts_at: datetime


def find_targets(conn, now: datetime, within_hours: float, *, tenant_id: str | None = None) -> list[Target]:
    """확인할 (장소, 날짜). `tenant_id` 를 주면 그 회사의 여행만, 안 주면 전부."""
    with conn.cursor() as cur:
        cur.execute(_TARGETS_SQL, (now, now, str(within_hours), tenant_id, tenant_id))
        rows = cur.fetchall()
    return [Target(str(c), n, (addr or "").strip() or None, d, s) for c, n, addr, d, s in rows]


def pending(targets: list[Target], *, read_row: Callable[[Target], dict | None], now: datetime,
            recheck_hours: float = 6.0) -> int:
    """아직 확인하지 않은 곳의 수 — 최근(`recheck_hours`) 안에 본 곳은 뺀다. 정기점검의 「남은 건수」다."""
    return sum(1 for target in targets
               if not live_store.fresh(read_row(target), now, recheck=timedelta(hours=recheck_hours)))


def check_targets(targets: list[Target], *, read_row: Callable[[Target], dict | None],
                  judge: Callable[[Target], Any], budget: Callable[[str], bool],
                  record: Callable[[Target, Any], None], now: datetime, recheck_hours: float = 6.0,
                  limit: int | None = None) -> dict[str, int]:
    """대상을 하나씩 확인해 저장한다. 한 곳이 실패해도 멈추지 않고 세어 보고한다(분모를 줄이지 않는다)."""
    out = {"targets": len(targets), "fresh": 0, "checked": 0, "closed": 0, "open": 0, "unknown": 0, "failed": 0,
           "budget_stop": 0, "left": 0}
    asked = 0
    for index, target in enumerate(targets):
        if live_store.fresh(read_row(target), now, recheck=timedelta(hours=recheck_hours)):
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


def judge_runner(llm: Any | None):
    """웹 검색 판정 함수 — 조립이 만든 판정 LLM(`build_activity_judge_llm`)을 받아 같은 검증(`LLMJudge`)으로 감싼다. 없으면 `None`.
    ★팀 폴더는 인프라를 직접 열지 않는다(DoD-22) — LLM · 연결 · 예산은 조립(또는 손으로 돌리는 스크립트)이 넘긴다."""
    if llm is None:
        return None
    from app.domains.travel_ops.instances.activity.judge import requests as judge_requests
    from app.domains.travel_ops.instances.activity.judge.llm import LLMJudge
    from app.domains.travel_ops.instances.activity.judge.types import JudgeContext

    judge = LLMJudge(llm)

    def run(target: Target):
        request = judge_requests.live_status(target.name, "activity", target.address, target.starts_at)
        return asyncio.run(judge.judge(JudgeContext(capability="activity.live_status_batch"), request))

    return run


def row_reader(connection_factory: Callable[[], Any]) -> Callable[[Target], dict | None]:
    """저장된 값 읽기 — 한 곳 · 한 날짜. 연결은 부르는 쪽이 넘긴다."""
    def read_row(target: Target) -> dict | None:
        with connection_factory() as conn:
            return live_store.read(conn, target.content_id, target.visit_date)

    return read_row


def recorder(connection_factory: Callable[[], Any], model: str | None = None) -> Callable[[Target, Any], None]:
    """판정 결과를 `activity.ac_live_status` 에 저장하는 함수. ★근거(인용) 없는 「닫혔다」는 모름으로 저장한다."""
    def record(target: Target, verdict) -> None:
        citations = [{"url": c.get("url"), "quote": c.get("quote"), "published_at": c.get("published_at")}
                     for c in verdict.citations if isinstance(c, dict)]
        value = verdict.value if verdict.known else "unknown"
        if value == "closed" and not citations:
            value = "unknown"
        with connection_factory() as conn, conn.transaction():
            live_store.record(conn, target.content_id, target.visit_date, value, citations=citations,
                              basis=verdict.basis or verdict.failure_code, model=model)

    return record


__all__ = ["Target", "check_targets", "find_targets", "judge_runner", "pending", "recorder", "row_reader"]
