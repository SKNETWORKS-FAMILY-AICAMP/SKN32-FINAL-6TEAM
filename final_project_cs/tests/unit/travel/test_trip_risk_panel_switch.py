# -*- coding: utf-8 -*-
"""여행 화면 · 계획 확인 화면 위험 점검 칸 스위치 — 기본 꺼짐, 관리 콘솔 값이 먼저. `[2026-10-22 사용자 지시]`

켜짐이면 여행 조회 · 공개 읽기 `GET /v1/web/features` 의 `risk_panel` 이 true 라 화면이 점검 칸을 보이고, 꺼짐이면 그 칸만 숨는다.
계약: `wiki/external/rest-endpoints/web-trips.md` 「여행 화면 위험 점검 칸」.
"""
from __future__ import annotations

import pytest

from app.core import settings as core_settings
from app.core.settings import ConfigError
from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard


@pytest.fixture(autouse=True)
def _no_reader():
    settings_hook.clear()
    yield
    settings_hook.clear()


def _console(value):
    settings_hook.register(lambda tenant, name: value if name == settings_hook.TRIP_RISK_PANEL else None)


def test_switch_is_listed_for_the_admin_console_and_off_by_default():
    spec = web_guard.specs()[settings_hook.TRIP_RISK_PANEL]
    assert spec.type == "bool" and spec.default is False
    assert spec.check(True) is None and spec.check("on") == "wrong_type"


def test_without_console_value_the_guardrail_decides_and_it_is_off():
    assert settings_hook.trip_risk_panel_enabled("t1") is False


@pytest.mark.parametrize("stored, expected", [(True, True), (False, False)])
def test_console_value_wins(stored, expected):
    _console(stored)
    assert settings_hook.trip_risk_panel_enabled("t1") is expected


@pytest.mark.parametrize("stored", ["on", 1, None])
def test_non_boolean_value_is_not_treated_as_a_change(stored):
    _console(stored)
    assert settings_hook.trip_risk_panel_enabled("t1") is False


def test_unreadable_table_falls_back_to_the_guardrail_off():
    def broken(tenant, name):
        raise RuntimeError("db down")

    settings_hook.register(broken)
    assert settings_hook.trip_risk_panel_enabled("t1") is False


def test_unreadable_guardrail_keeps_the_decided_default_off(monkeypatch):
    class Broken:
        def get(self, key):
            raise ConfigError(f"guardrails 키 없음: '{key}'")

    monkeypatch.setattr(core_settings, "get_guardrails", lambda: Broken())
    assert core_settings.trip_risk_panel_enabled() is False
