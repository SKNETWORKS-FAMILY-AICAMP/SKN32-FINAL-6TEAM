# -*- coding: utf-8 -*-
"""활동 웹 운영 확인의 **새벽 정기 작업**(`instances/activity/jobs.py`) — 남은 건수를 팀에게 묻지 않고 대상 목록에서 직접 센다. `[2026-10-14]`

정기점검 규칙(`watch/daily_check.py`): 03:30 이 지난 회차에 결과의 `remaining` 이 0 보다 크면 「안 끝남」으로 운영 진단에 보고한다.
`remaining` 이 없으면 「모름」으로만 센다. 그래서 이 작업은 늘 `remaining` 을 싣거나, 꺼진 것(`disabled`) · 오늘 예산을 다 쓴 것(`skipped`)을 밝힌다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.watch import daily_check
from app.domains.travel_ops.instances.activity import jobs, live_batch

KST = ZoneInfo("Asia/Seoul")


@dataclass
class _V:
    value: str
    known: bool = True
    citations: tuple = ()
    basis: str | None = None
    failure_code: str | None = None


class _Parts:
    """`live_batch` 대신 끼우는 부품 — DB · 웹을 부르지 않는다. 확인한 곳은 「최근에 봤다」로 바뀐다."""

    def __init__(self, n: int, *, budget_left: int = 99, judge_ok: bool = True, judge=True):
        self.targets = [live_batch.Target(f"c{i}", f"장소{i}", None, date(2026, 10, 15), datetime(2026, 10, 15, 10, tzinfo=KST))
                        for i in range(n)]
        self.seen: set[str] = set()
        self.budget_left = budget_left
        self.judge_ok = judge_ok
        self._judge = judge
        self.now = None

    def judge_runner(self, llm):
        if llm is None:
            return None

        def run(target):
            if not self.judge_ok:
                raise RuntimeError("web down")
            return _V("open")
        return run

    def find_targets(self, conn, now, within, *, tenant_id=None):
        self.tenant = tenant_id
        return list(self.targets)

    def row_reader(self, connect):
        return lambda target: {"checked_at": self.now} if target.content_id in self.seen else None

    pending = staticmethod(live_batch.pending)
    check_targets = staticmethod(live_batch.check_targets)

    def take(self, kind):
        if self.budget_left <= 0:
            return False
        self.budget_left -= 1
        return True

    def recorder(self, connect, model=None):
        return lambda target, verdict: self.seen.add(target.content_id)

    def wired(self):
        return {"connection_factory": _Conn, "judge_llm": object() if self._judge else None, "budget": self.take}


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def on(monkeypatch):
    """판정 종류 `live_status` 를 켠 상태(shadow)."""
    from app.domains.travel_ops.instances.activity.judge import modes

    monkeypatch.setattr(modes, "kind_mode", lambda kind, modes=None: "shadow")


def _tick(parts, hour, minute):
    now = datetime(2026, 10, 15, hour, minute, tzinfo=KST)
    parts.now = now
    return jobs.live_status_tick("demo", now, parts=parts, wired=parts.wired())


def test_the_job_is_registered_for_the_dawn_window():
    assert [(job.name, job.window) for job in jobs.JOBS] == [("activity_live_status", "dawn")]


def test_remaining_is_counted_from_the_targets_not_asked_of_the_team(on):
    parts = _Parts(10)
    result = _tick(parts, 3, 0)
    assert parts.tenant == "demo"                                   # 회사마다 따로 센다
    assert result["checked"] == jobs.PER_TICK_BASE                  # 30분에 10곳 → 분당 1곳이면 되지만 적어도 기본 2
    assert result["remaining"] == 10 - result["checked"]


def test_after_the_finish_time_it_does_the_most_per_tick(on):
    assert _tick(_Parts(20), 3, 31)["checked"] == jobs.PER_TICK_CAP


def test_after_the_finish_time_leftovers_are_reported_as_unfinished(on):
    parts = _Parts(20)
    result = _tick(parts, 3, 31)
    late, unknown = daily_check.unfinished({"team:activity_live_status": result})
    assert result["remaining"] > 0 and late == ["team:activity_live_status"] and unknown == []


def test_nothing_left_means_finished_and_no_web_call(on):
    parts = _Parts(3)
    parts.seen = {"c0", "c1", "c2"}                                 # 최근 6시간 안에 다 봤다
    result = _tick(parts, 3, 40)
    assert result == {"targets": 3, "checked": 0, "remaining": 0}
    assert daily_check.unfinished({"team:activity_live_status": result}) == ([], [])


def test_a_failed_check_stays_in_the_remaining_count(on):
    parts = _Parts(3, judge_ok=False)
    result = _tick(parts, 3, 0)
    assert result["failed"] > 0 and result["remaining"] == 3


def test_an_exhausted_web_budget_is_not_reported_as_late(on):
    parts = _Parts(10, budget_left=1)
    result = _tick(parts, 3, 45)
    assert result["skipped"] == 1 and result["remaining"] == 9
    assert daily_check.unfinished({"team:activity_live_status": result}) == ([], [])


def test_switched_off_calls_nothing(monkeypatch):
    from app.domains.travel_ops.instances.activity.judge import modes

    monkeypatch.setattr(modes, "kind_mode", lambda kind, modes=None: "rule")
    parts = _Parts(5)
    assert jobs.live_status_tick("demo", datetime(2026, 10, 15, 3, 0, tzinfo=KST), parts=parts, wired=parts.wired()) == {"disabled": 1}


def test_no_judge_model_calls_nothing(on):
    assert _tick(_Parts(5, judge=False), 3, 0) == {"disabled": 1}


def test_not_wired_by_the_assembly_is_unknown_not_finished(on):
    """조립이 연결을 꽂지 않았으면 `not_wired` — 정기점검은 「모름」으로 센다(조용히 「끝남」이 되지 않는다)."""
    result = jobs.live_status_tick("demo", datetime(2026, 10, 15, 3, 40, tzinfo=KST), parts=_Parts(5), wired={})
    assert result == {"not_wired": 1}
    assert daily_check.unfinished({"team:activity_live_status": result}) == ([], ["team:activity_live_status"])


def test_the_assembly_wires_the_job(monkeypatch):
    """활동 팀이 켜져 있으면 조립이 작업을 등록하고 연결 · 판정 LLM · 예산을 꽂는다."""
    from app import composition
    from app.domains.travel_ops.components.team_hooks import scheduled_jobs

    scheduled_jobs.clear()
    monkeypatch.setattr(jobs, "_wired", {})
    composition._wire_domain_providers(active_ids={"activity"})
    assert [job.name for job in scheduled_jobs.registered()] == ["activity_live_status"]
    assert set(jobs._wired) == {"connection_factory", "judge_llm", "budget"}
    scheduled_jobs.clear()
