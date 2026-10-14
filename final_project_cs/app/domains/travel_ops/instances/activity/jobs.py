# -*- coding: utf-8 -*-
"""활동 팀 **정기 작업** — 조립이 이 파일의 `JOBS` 를 찾아 등록하고(`team_hooks/scheduled_jobs`), 작업 실행기가 새벽 창에서 1분마다 부른다.

    activity_live_status   앞으로 72시간 안에 시작하는 활동 장소의 임시휴무 · 폐업을 웹 공지로 한 번 확인해 저장한다
                           (전에는 `scripts/activity/check_live_status.py` 를 손으로 돌려야 했다 — 활동 → 코어 전달 사항 10-13 2번)

★일일 정기점검 규칙(`watch/daily_check.py`, 2026-10-14 사용자 지시)을 따른다 — 03:00 시작 · 03:30 까지 끝나게 한 번에 하는 양을 맞추고 ·
  결과에 `remaining`(아직 확인하지 않은 곳의 수)을 싣는다. 실행기는 03:30 뒤 첫 회차에 `remaining > 0` 이면 「안 끝남」으로 보고한다.
  남은 건수는 팀에게 묻지 않고 **대상 목록에서 직접 센다**(최근 6시간 안에 본 곳은 뺀다 — `live_batch.pending`).
★연결 · 판정 LLM · 웹 예산은 조립이 `configure` 로 꽂는다 — 팀 폴더는 인프라를 직접 열지 않는다(DoD-22, `team.live_lookup` 과 같은 방식).
  꽂히지 않았으면 `not_wired` 를 싣는다(정기점검 판정에서는 「모름」으로 센다 — 조용히 「끝남」이 되지 않는다).
★꺼져 있으면(판정 종류 `live_status` 가 `rule` · 판정 LLM 없음 — 전역 판정 모드 `rule` 이거나 OpenAI 키 없음) 아무것도 부르지 않고
  `disabled` 를 싣는다 — 정기점검 판정에서 빠진다(안 끝난 것이 아니다).
★웹 예산(하루 50회)이 다 차면 `skipped` 를 싣는다 — 오늘 몫을 다 쓴 것이라 「안 끝남」으로 보고하지 않는다. 남은 곳은 `remaining` 에 그대로 남는다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from app.domains.travel_ops.components.team_hooks.scheduled_jobs import TeamJob

#: 한 회차(1분)에 확인하는 곳 — 웹 검색 한 번이 15~40초 걸린다(10-06 측정 p50 15.7초 · p95 40.7초).
#: 03:30 까지 끝나게 늘리되(`daily_check.paced`) 많아야 `PER_TICK_CAP` — 한 회차가 몇 분씩 늘어지지 않게. ★우리가 고른 값
PER_TICK_BASE = 2
PER_TICK_CAP = 4
#: 이 시간 안에 확인한 곳은 다시 보지 않는다(스크립트 기본값과 같다)
RECHECK_HOURS = 6.0

_wired: dict[str, Any] = {}


def configure(*, connection_factory: Callable[[], Any], judge_llm: Any | None,
              budget: Callable[[str], bool]) -> None:
    """조립이 부른다 — 연결 · 판정 LLM(없으면 `None`) · 웹 예산(종류 → 불러도 되나)."""
    _wired.clear()
    _wired.update(connection_factory=connection_factory, judge_llm=judge_llm, budget=budget)


def live_status_tick(tenant_id: str, now: datetime, *, parts=None, wired: dict[str, Any] | None = None) -> dict[str, int]:
    """한 회차. `parts` · `wired` 는 시험이 부품(대상 · 판정 · 예산 · 저장)과 연결을 바꿔 끼우는 자리다."""
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.watch import daily_check
    from app.domains.travel_ops.instances.activity import live_batch
    from app.domains.travel_ops.instances.activity.judge.modes import kind_mode

    parts = parts or live_batch
    wired = _wired if wired is None else wired
    if kind_mode("live_status") == "rule":
        return {"disabled": 1}
    if not wired:
        return {"not_wired": 1}
    judge = parts.judge_runner(wired["judge_llm"])
    if judge is None:
        return {"disabled": 1}
    guard = get_guardrails()
    within = float(guard.get("travel.activity_judge.live_status_within_hours"))
    connect = wired["connection_factory"]

    with connect() as conn:
        targets = parts.find_targets(conn, now, within, tenant_id=tenant_id)
    read_row = parts.row_reader(connect)
    left = parts.pending(targets, read_row=read_row, now=now, recheck_hours=RECHECK_HOURS)
    if left == 0:
        return {"targets": len(targets), "checked": 0, "remaining": 0}
    win = daily_check.from_guardrails(now, guard)
    limit = daily_check.paced(left, base=PER_TICK_BASE, cap=PER_TICK_CAP, win=win)
    result = parts.check_targets(targets, read_row=read_row, judge=judge, budget=wired["budget"],
                                 record=parts.recorder(connect), now=now, recheck_hours=RECHECK_HOURS, limit=limit)
    out = {key: int(value) for key, value in result.items()}
    out["remaining"] = max(0, left - result["checked"])          # 실패한 곳은 저장되지 않았으니 남은 일이다
    if result["budget_stop"]:
        out["skipped"] = 1                                       # 오늘 웹 예산을 다 썼다 — 늦은 것이 아니다
    return out


JOBS = [TeamJob(name="activity_live_status", tick=live_status_tick, window="dawn")]
