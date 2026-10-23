# -*- coding: utf-8 -*-
"""등록 여행 식당 카드의 캐치테이블 시험 값 스위치 — 기본 꺼짐, 관리 콘솔 값이 먼저. `[2026-10-19 사용자 지시]`

켜짐이면 여행 조회 응답의 식당 항목에 `trial_live` 가 실리고(값이 있을 때만), 꺼짐이면 응답 모양이 전과 같다.
계획: `wiki/records/plans/2026-10-16_catchtable_trial_live_card.md`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core import settings as core_settings
from app.core.settings import ConfigError
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.instances.dining.ledger import trial_due
from app.domains.travel_ops.modules.web_account import web_guard


@pytest.fixture(autouse=True)
def _no_reader():
    settings_hook.clear()
    yield
    settings_hook.clear()


def _console(value):
    settings_hook.register(lambda tenant, name: value if name == settings_hook.DINING_TRIAL_LIVE_VIEW else None)


def test_switch_is_listed_for_the_admin_console_and_off_by_default():
    spec = web_guard.specs()[settings_hook.DINING_TRIAL_LIVE_VIEW]
    assert spec.type == "bool" and spec.default is False
    assert spec.check(True) is None and spec.check("on") == "wrong_type"


def test_without_console_value_the_guardrail_decides_and_it_is_off():
    assert settings_hook.dining_trial_live_view_enabled("t1") is False


@pytest.mark.parametrize("stored, expected", [(True, True), (False, False)])
def test_console_value_wins(stored, expected):
    _console(stored)
    assert settings_hook.dining_trial_live_view_enabled("t1") is expected


@pytest.mark.parametrize("stored", ["on", 1, None])
def test_non_boolean_value_is_not_treated_as_a_change(stored):
    _console(stored)
    assert settings_hook.dining_trial_live_view_enabled("t1") is False


def test_unreadable_table_falls_back_to_the_guardrail_off():
    def broken(tenant, name):
        raise RuntimeError("db down")

    settings_hook.register(broken)
    assert settings_hook.dining_trial_live_view_enabled("t1") is False


def test_unreadable_guardrail_stays_off(monkeypatch):
    class Broken:
        def get(self, key):
            raise ConfigError(f"guardrails 키 없음: '{key}'")

    monkeypatch.setattr(core_settings, "get_guardrails", lambda: Broken())
    assert core_settings.dining_trial_live_view_enabled() is False


# `[2026-10-19 사용자 결정]` 곧 갈 식사에만 — 시작 1시간 전부터 시작 시각 전까지. 사람은 1시간 전 · 30분 전에 한 번씩 읽는다.
KST = timezone(timedelta(hours=9))
LUNCH = datetime(2026, 10, 20, 12, 0, tzinfo=KST)


@pytest.mark.parametrize("minutes_before, due", [(61, False), (60, True), (30, True), (1, True), (0, False), (-10, False)])
def test_trial_line_shows_only_from_an_hour_before_the_meal_until_it_starts(minutes_before, due):
    assert trial_due(LUNCH, LUNCH - timedelta(minutes=minutes_before)) is due


def test_meal_days_away_or_without_a_time_does_not_show():
    assert trial_due(LUNCH + timedelta(days=3), LUNCH - timedelta(minutes=30)) is False
    assert trial_due(None, LUNCH) is False


def test_time_read_from_text_counts_in_seoul_time():
    assert trial_due("2026-10-20T12:00:00", LUNCH - timedelta(minutes=30)) is True
    assert trial_due("2026-10-20T03:00:00+00:00", LUNCH - timedelta(minutes=30)) is True
