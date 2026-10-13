# -*- coding: utf-8 -*-
"""식당 대체 후보 구글 가격 비교 스위치 — 관리 콘솔 값이 먼저, 없으면 가드레일(기본 꺼짐). `[2026-10-13 사용자 지시]`"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard


@pytest.fixture(autouse=True)
def _no_reader():
    settings_hook.clear()
    yield
    settings_hook.clear()


def test_switch_is_listed_for_the_admin_console_and_off_by_default():
    spec = web_guard.specs()[settings_hook.GOOGLE_PRICE]
    assert spec.type == "bool"
    assert spec.default is False
    assert spec.check(True) is None and spec.check("on") == "wrong_type"


def test_without_console_value_the_guardrail_decides():
    assert settings_hook.google_price_enabled("t1") is False


@pytest.mark.parametrize("stored, expected", [(True, True), (False, False)])
def test_console_value_wins(stored, expected):
    settings_hook.register(lambda tenant, name: stored if name == settings_hook.GOOGLE_PRICE else None)
    assert settings_hook.google_price_enabled("t1") is expected


@pytest.mark.parametrize("stored", ["on", 1, None])
def test_non_boolean_value_is_not_treated_as_on(stored):
    settings_hook.register(lambda tenant, name: stored)
    assert settings_hook.google_price_enabled("t1") is False


def test_unreadable_table_falls_back_to_off():
    def broken(tenant, name):
        raise RuntimeError("db down")

    settings_hook.register(broken)
    assert settings_hook.google_price_enabled("t1") is False
