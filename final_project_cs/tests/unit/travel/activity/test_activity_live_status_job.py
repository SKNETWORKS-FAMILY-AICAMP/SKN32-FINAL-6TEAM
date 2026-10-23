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
    monkeypatch.setattr(jobs, "_console_on", lambda tenant_id: True)


def _tick(parts, hour, minute):
    now = datetime(2026, 10, 15, hour, minute, tzinfo=KST)
    parts.now = now
    return jobs.live_status_tick("demo", now, parts=parts, wired=parts.wired())


def test_the_job_is_registered_for_the_dawn_window():
    # 웹 확인은 그대로, 활동 정기 작업 3종이 같은 자리에 더 올라갔다(ST4F-538, 2026-10-15 — test_activity_team_batch_jobs)
    assert ("activity_live_status", "dawn") in [(job.name, job.window) for job in jobs.JOBS]


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
    # 활동 정기 작업 4종(ST4F-538, 2026-10-15) — 웹 확인 + 장소 갱신 · 요일표 펴기 · 실내외 정하기
    assert [job.name for job in scheduled_jobs.registered()] == [
        "activity_decide_indoor", "activity_live_status", "activity_read_hours", "activity_refresh_places"]
    assert set(jobs._wired) == {"connection_factory", "judge_llm", "budget", "claim"}
    scheduled_jobs.clear()


def test_the_console_switch_is_off_by_default_and_calls_nothing(monkeypatch):
    """관리 콘솔 스위치가 꺼져 있으면(기본) 판정 모델이 있어도 아무것도 부르지 않는다 — 유료 웹 검색이라 운영자가 켤 때만. `[2026-10-14]`"""
    from app.domains.travel_ops.components import settings_hook
    from app.domains.travel_ops.instances.activity.judge import modes

    monkeypatch.setattr(modes, "kind_mode", lambda kind, modes=None: "shadow")
    settings_hook.clear()
    parts = _Parts(5)
    result = jobs.live_status_tick("demo", datetime(2026, 10, 15, 3, 0, tzinfo=KST), parts=parts, wired=parts.wired())
    assert result == {"disabled": 1, "console_off": 1} and parts.seen == set()
    assert daily_check.unfinished({"team:activity_live_status": result}) == ([], [])


def test_the_console_value_wins_over_the_default():
    from app.domains.travel_ops.components import settings_hook

    settings_hook.register(lambda tenant_id, name: True if name == settings_hook.ACTIVITY_LIVE_CHECK else None)
    try:
        assert settings_hook.activity_live_check_enabled("demo") is True
    finally:
        settings_hook.clear()
    settings_hook.register(lambda tenant_id, name: "yes")               # 참/거짓이 아닌 값은 켠 것으로 보지 않는다
    try:
        assert settings_hook.activity_live_check_enabled("demo") is False
    finally:
        settings_hook.clear()
