# -*- coding: utf-8 -*-
"""에이전트 팀의 **정기 작업**(새벽 점검 등)을 끼우는 자리. `[2026-10-13]` 활동 → 코어 전달 사항(10-13) 2번

전에는 작업 실행기(`scripts/run_sweepers.py`)에 작업 이름이 전부 코드로 박혀 있어, 팀이 배치를 하나 더하려면
매번 코어를 고쳐야 했다(활동의 웹 확인 배치 · 장소 갱신 스크립트가 수동 실행으로 남은 이유).

    팀      `instances/<팀>/jobs.py` 에 `JOBS = [TeamJob(...)]` 를 둔다        → 코어를 고치지 않는다
    조립    활성 팀의 `jobs.py` 를 찾아 `register()` (`composition.wire_optional_features`)
    실행기  1분마다 등록된 작업을 부른다. 시간대 밖이면 부르지 않는다(`outside_window`)

★시간대는 코어 설정이 정한다 — `guardrails.yaml travel.team_jobs.windows.<이름>`(서울 시각, 예: `dawn` 03:00~08:00 —
  관광공사 운영시간 새벽 읽기 · 식당 새벽 확인과 같은 새벽 정기 점검 시간대). 팀은 이름만 고른다.
★1분마다 불린다 — 한 번에 할 양(per_tick)과 「이미 한 곳은 건너뛰기」는 팀의 `tick` 이 지킨다. 실행기는 결과(건수 dict)를 그대로 싣는다.
★미등록이면 아무것도 안 돈다. 다른 팀 작업으로 **대신하지 않는다.**
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

from app.core.service_bindings import collect_registration, current_bindings, read_binding


@dataclass(frozen=True)
class TeamJob:
    """팀 정기 작업 하나.

    `name`   실행 결과 표의 키가 된다(`team:<name>`) — 팀 사이에 겹치지 않게 팀 이름을 앞에 붙인다(예: `activity_live_status`)
    `tick`   `(tenant_id, now) -> {건수}` — 한 회차. 서울 시각 `now` 를 받는다
    `window` `guardrails travel.team_jobs.windows` 의 키. 그 시간대 안에서만 불린다
    """
    name: str
    tick: Callable[[str, datetime], Mapping[str, int]]
    window: str = "dawn"


_jobs: dict[str, TeamJob] = {}


def register(team_id: str, job: TeamJob) -> None:
    """조립 때 작업마다 한 번. 같은 이름을 다시 등록하면 **교체**한다(재조립 대비)."""
    if not isinstance(job, TeamJob):
        raise TypeError(f"team '{team_id}' job must be TeamJob, got {type(job).__name__}")
    if collect_registration("scheduled_jobs", {job.name: job}):
        return
    _jobs[job.name] = job


def clear() -> None:
    _jobs.clear()


def registered() -> tuple[TeamJob, ...]:
    """지금 조립에 등록된 작업(이름 순)."""
    table = current_bindings()
    if table is not None:
        names = sorted(key for (group, key) in table.values if group == "scheduled_jobs")
        return tuple(job for job in (read_binding("scheduled_jobs", name, None) for name in names) if job is not None)
    return tuple(_jobs[name] for name in sorted(_jobs))
