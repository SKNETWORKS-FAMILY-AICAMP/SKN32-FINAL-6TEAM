# -*- coding: utf-8 -*-
"""활동 정기 작업 4종이 코어 수정 없이 같은 자리에 올라간다 — `[2026-10-15]` 활동 → 코어 전달 사항 6번 (TeamFlow ST4F-538). DB 없이.

`instances/activity/jobs.py` 의 `JOBS` 가 `activity_live_status`(웹 확인, 이미 있던 것) 외에 손으로 돌리던 스크립트 셋
(`scripts/activity/{refresh_places,read_hours,decide_indoor}.py`)을 새벽 창(`dawn`)에 올린다. 한 회차의 일은 그 스크립트의 함수를 그대로 부른다.
  - 읽기 · 실내외는 규칙 단계만(모델을 부르지 않는다 — 유료). 결과에 `remaining: 0` 을 싣는다(정기점검에서 「모름」이 되지 않게).
  - 장소 원문 다시 받기는 기본 꺼짐(`travel.activity_batch.refresh_places_enabled`) · 하루 한 번 · 상한 안에서.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.team_hooks import scheduled_jobs
from app.domains.travel_ops.components.watch import daily_check
from app.domains.travel_ops.instances.activity import jobs

KST = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 15, 3, 5, tzinfo=KST)


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def transaction(self):
        return _Conn()


def _wired(claim=None):
    return {"connection_factory": _Conn, "judge_llm": None, "budget": lambda kind: True,
            "claim": claim or (lambda conn, **kw: pytest.fail("주기 문을 부르면 안 된다"))}


def test_the_activity_jobs_file_lists_all_four_on_the_dawn_window():
    by_name = {job.name: job for job in jobs.JOBS}
    assert set(by_name) == {"activity_live_status", "activity_refresh_places", "activity_read_hours", "activity_decide_indoor"}
    assert {job.window for job in jobs.JOBS} == {"dawn"} and all(callable(job.tick) for job in jobs.JOBS)


def test_the_assembly_registers_the_four_without_touching_the_runner(monkeypatch):
    from app import composition

    scheduled_jobs.clear()
    monkeypatch.setattr(jobs, "_wired", {})
    composition._wire_domain_providers(active_ids={"activity"})
    assert [job.name for job in scheduled_jobs.registered()] == [
        "activity_decide_indoor", "activity_live_status", "activity_read_hours", "activity_refresh_places"]
    scheduled_jobs.clear()


@pytest.mark.parametrize("tick", [jobs.read_hours_tick, jobs.decide_indoor_tick])
def test_the_database_only_jobs_run_the_script_function_and_report_remaining_zero(tick):
    seen = []

    def runner(conn):
        seen.append(conn)
        return {"asked": 3, "read": 2, "unknown": 1}

    result = tick("demo", NOW, wired=_wired(), runner=runner)
    assert result == {"asked": 3, "read": 2, "unknown": 1, "remaining": 0} and len(seen) == 1
    assert daily_check.unfinished({"team:x": result}) == ([], [])         # 「안 끝남」도 「모름」도 아니다


@pytest.mark.parametrize("tick", [jobs.read_hours_tick, jobs.decide_indoor_tick])
def test_not_wired_is_said_out_loud(tick):
    assert tick("demo", NOW, wired={}, runner=lambda conn: pytest.fail("연결이 없는데 불렀다")) == {"not_wired": 1}


def test_the_scripts_the_jobs_call_exist_with_the_expected_functions():
    """이름만 맞고 함수가 없으면 새벽에야 터진다 — 지금 확인한다."""
    assert callable(jobs._script("read_hours").run) and callable(jobs._script("decide_indoor").run)
    refresh = jobs._script("refresh_places")
    assert callable(refresh.refresh) and callable(refresh.mark_listing) and refresh.CATEGORIES


class _RefreshScript:
    CATEGORIES = ("EV", "HS")

    def __init__(self):
        self.refresh_args = None
        self.marked = None

    def refresh(self, conn, listed, fetch_intro, *, max_calls=None, dry_run=False):
        self.refresh_args = (list(listed), max_calls)
        return {"baseline": 1, "same": 2, "changed": 3, "refetched": 3, "text_changed": 1, "not_in_ledger": 0, "over_limit": 0}

    def mark_listing(self, conn, ids, *, dry_run=False):
        self.marked = set(ids)
        return {"delisted": 0, "relisted": 0, "delisted_total": 4}


def _guard(monkeypatch, enabled, calls=300):
    from app.core import settings as core_settings

    real = core_settings.get_guardrails()

    class _G:
        def get(self, key, *args):
            if key == "travel.activity_batch.refresh_places_enabled":
                return enabled
            if key == "travel.activity_batch.refresh_places_max_calls":
                return calls
            return real.get(key, *args)

    monkeypatch.setattr(core_settings, "get_guardrails", lambda: _G())


def test_refresh_places_is_off_by_default_and_calls_nothing():
    from app.core.settings import get_guardrails

    assert get_guardrails().get("travel.activity_batch.refresh_places_enabled") is False        # 정본 설정이 꺼짐
    assert get_guardrails().get("travel.activity_batch.refresh_places_max_calls") == 300
    script = _RefreshScript()
    result = jobs.refresh_places_tick("demo", NOW, wired=_wired(), script=script,
                                      fetch_listing=lambda k, c: pytest.fail("꺼졌는데 관광공사를 불렀다"))
    assert result == {"disabled": 1} and script.refresh_args is None
    assert daily_check.unfinished({"team:activity_refresh_places": result}) == ([], [])


def test_refresh_places_when_on_fetches_each_category_refreshes_with_the_cap_and_claims_once(monkeypatch):
    from app.core import settings as core_settings

    _guard(monkeypatch, True, calls=123)
    monkeypatch.setattr(core_settings, "get_settings", lambda: type("S", (), {"tour_api_key": "k"})())
    claims = iter([True, False])

    def claim(conn, **kw):
        assert kw["gate"] == jobs.REFRESH_GATE and kw["min_seconds"] == jobs.REFRESH_EVERY_SECONDS
        return next(claims)

    script, fetched = _RefreshScript(), []

    def listing(key, cat):
        fetched.append((key, cat))
        return [{"contentid": f"{cat}1"}]

    first = jobs.refresh_places_tick("demo", NOW, wired=_wired(claim), script=script, fetch_listing=listing, fetch_intro=lambda c, t: None)
    assert fetched == [("k", "EV"), ("k", "HS")] and script.refresh_args == ([{"contentid": "EV1"}, {"contentid": "HS1"}], 123)
    assert first["listed"] == 2 and first["changed"] == 3 and first["remaining"] == 0 and first["listing_delisted_total"] == 4
    assert script.marked == {"EV1", "HS1"}
    second = jobs.refresh_places_tick("demo", NOW, wired=_wired(claim), script=script, fetch_listing=listing, fetch_intro=lambda c, t: None)
    assert second == {"skipped_until_due": 1} and len(fetched) == 2                    # 하루 한 번 — 두 번째 회차는 부르지 않는다


def test_refresh_places_on_without_a_key_fails_loudly(monkeypatch):
    from app.core import settings as core_settings

    _guard(monkeypatch, True)
    monkeypatch.setattr(core_settings, "get_settings", lambda: type("S", (), {"tour_api_key": ""})())
    with pytest.raises(RuntimeError, match="ACOP_TOUR_API_KEY"):
        jobs.refresh_places_tick("demo", NOW, wired=_wired(), script=_RefreshScript())
