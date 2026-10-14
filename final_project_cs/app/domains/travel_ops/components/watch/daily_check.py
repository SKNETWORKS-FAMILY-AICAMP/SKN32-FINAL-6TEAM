# -*- coding: utf-8 -*-
"""**일일 정기점검**(새벽 작업)의 시각과 「다 끝났나」 판정 — 한 곳에 둔다. `[2026-10-14 사용자 지시]`

사용자 말: 「3시 시작, 가능하면 3시 30분까지 마감하게 하고 안 끝나고 있으면 관리자 웹앱에 보고 들어가게. 그리고 8시에는 모두 멈추게 — 지금처럼.」

    03:00  시작 (`travel.daily_check.start`)
    03:30  여기까지 끝내도록 한 번에 하는 양을 맞춘다(`finish_by`). 이 시각 뒤 첫 회차에 안 끝난 작업이 있으면 관리자 웹앱 「운영 진단」에 하루 한 건 보고한다
    08:00  모두 멈춘다(`stop`) — 새벽 식당 확인 · 관광공사 운영시간 읽기 · 일정에 넣은 장소 다시 읽기 · 팀 정기 작업

★여기는 순수 계산만 한다(DB · 외부 호출 없음). 보고를 실제로 남기는 것은 작업 실행기(`scripts/run_sweepers.py`)다.
★「안 끝났다」는 그 회차 결과로 판단한다 — 03:30 이 지난 회차에 아직 할 일이 남았거나(`remaining`) 일을 했거나 터진 작업이다.
  팀 정기 작업은 결과에 `remaining`(남은 건수)을 실어야 판정된다. 안 실으면 「모름」으로 세고 보고하지 않는다(지어내지 않는다).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Mapping


def _clock(text: str) -> time:
    hour, minute = str(text).split(":")
    return time(int(hour), int(minute))


@dataclass(frozen=True)
class Window:
    """`now` 가 속한 정기점검 회차. 회차는 그날 `start` 에 시작한다(그 전이면 어제 회차)."""

    started_at: datetime
    finish_by_at: datetime
    stop_at: datetime
    now: datetime

    @property
    def open(self) -> bool:
        """시작 ~ 멈춤 사이인가 — 정기점검 작업은 이때만 돈다."""
        return self.started_at <= self.now < self.stop_at

    @property
    def past_finish_by(self) -> bool:
        return self.finish_by_at <= self.now < self.stop_at

    @property
    def day(self) -> str:
        return self.started_at.date().isoformat()

    def minutes_to_finish(self) -> float:
        return (self.finish_by_at - self.now).total_seconds() / 60


def window(now: datetime, *, start: str, finish_by: str, stop: str) -> Window:
    begun = now.replace(hour=_clock(start).hour, minute=_clock(start).minute, second=0, microsecond=0)
    if now < begun:
        begun -= timedelta(days=1)

    def at(text: str) -> datetime:
        moment = begun.replace(hour=_clock(text).hour, minute=_clock(text).minute)
        return moment if moment >= begun else moment + timedelta(days=1)

    return Window(started_at=begun, finish_by_at=at(finish_by), stop_at=at(stop), now=now)


def from_guardrails(now: datetime, guard: Any) -> Window:
    return window(now, start=str(guard.get("travel.daily_check.start")),
                  finish_by=str(guard.get("travel.daily_check.finish_by")), stop=str(guard.get("travel.daily_check.stop")))


def paced(left: int, *, base: int, cap: int, win: Window) -> int:
    """이번 회차에 할 양 — 남은 일(`left`)을 `finish_by` 까지 끝내도록 늘린다. 적어도 `base`, 많아야 `cap`.
    `finish_by` 가 지났으면 `cap` 으로 마저 한다(멈춤 시각까지)."""
    if left <= 0:
        return base
    minutes = win.minutes_to_finish()
    need = cap if minutes <= 1 else math.ceil(left / minutes)
    return max(1, min(cap, max(base, need)))


def code_of(job: str) -> str:
    """보고에 싣는 작업 코드(대문자 · 숫자 · 밑줄) — 운영 진단은 원문 대신 코드만 받는다."""
    text = re.sub(r"[^A-Z0-9]+", "_", job.upper()).strip("_")
    return (text if text[:1].isalpha() else "JOB_" + text)[:64] or "JOB"


def unfinished(results: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    """`(안 끝난 작업, 모르는 작업)` — 정기점검에 드는 작업의 이번 회차 결과로 가른다.

    - `place_facts` · `catalog_hours`: `remaining` 이 0 보다 크면 안 끝남
    - `trip_dawn`: 창 안에서 이번 회차에 확인한 곳(`checked`)이나 다시 할 곳(`fatal`)이 있으면 안 끝남
    - `team:<이름>`: `remaining` 이 0 보다 크면 안 끝남, 없으면 모름
    - 어느 작업이든 터졌으면(`fatal` 표시만 있는 결과) 안 끝남
    """
    late, unknown = [], []
    for name, result in results.items():
        if not (name in ("place_facts", "catalog_hours", "trip_dawn") or name.startswith("team:")):
            continue
        result = dict(result or {})
        if result.get("fatal") and not any(key in result for key in ("remaining", "checked", "asked")):
            late.append(name)                       # 작업이 터졌다(실행기가 남긴 표시뿐) — 끝나지 않았다
        elif result.get("outside_window") or result.get("disabled") or result.get("skipped"):
            continue                                # 창 밖 · 꺼짐 · 오늘 몫을 다 씀 — 이번 판정과 무관
        elif "remaining" in result:
            if int(result.get("remaining") or 0) > 0:
                late.append(name)
        elif name == "trip_dawn":
            if int(result.get("checked") or 0) > 0 or int(result.get("fatal") or 0) > 0:
                late.append(name)
        elif name.startswith("team:"):
            unknown.append(name)
    return late, unknown


__all__ = ["Window", "code_of", "from_guardrails", "paced", "unfinished", "window"]
