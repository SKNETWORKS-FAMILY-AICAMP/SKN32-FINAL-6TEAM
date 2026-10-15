# -*- coding: utf-8 -*-
"""관리 콘솔의 「활동 장소 임시휴무 · 폐업 웹 확인」 스위치 — 운영 API 로 켜고 끄면 새벽 웹 확인 작업이 따라간다. `[2026-10-14 사용자 지시]`

관리 콘솔 화면은 `/admin/limits` 가 주는 목록을 그대로 그린다(참/거짓은 켜짐 · 꺼짐 고르기, `text_ko` 는 이름 아래 설명).
그래서 목록에 있고 저장이 먹으면 화면에도 스위치와 설명이 생긴다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_guard import _client

NAME = settings_hook.ACTIVITY_LIVE_CHECK


@pytest.fixture(autouse=True)
def _operator_values():
    web_guard.clear_cache()
    settings_hook.register(lambda tenant, name: web_guard.values(tenant).get(name))
    yield
    settings_hook.clear()
    web_guard.clear_cache()


def test_the_console_lists_the_switch_off_with_an_explanation_and_turning_it_on_takes_effect(api):
    client = _client()
    read, write = api["auth"]("limits:read"), api["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == NAME)
    assert (row["type"], row["value"], row["source"]) == ("bool", False, "default")
    # 설명은 무엇이 켜지나 · 고객 답을 바꾸나 · 비용 상한 · 끄면 어떻게 되나 · 지금 이 서버에서 도는지를 말한다
    for words in ("임시휴무", "고객 답과 일정은 바꾸지 않습니다", "하루 50번", "1,000번", "끄면", "지금 상태"):
        assert words in row["text_ko"], words
    assert settings_hook.activity_live_check_enabled(api["tenant"]) is False

    on = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "임시휴무 확인 시험 운영", "changes": {NAME: True}})
    assert on.status_code == 200, on.text
    assert next(r for r in on.json()["limits"] if r["name"] == NAME)["value"] is True
    assert settings_hook.activity_live_check_enabled(api["tenant"]) is True

    off = client.patch("/admin/limits", headers=write, json={
        "expected_revision": on.json()["revision"], "actor": "op-kim", "reason": "되돌림", "changes": {NAME: None}})
    assert off.status_code == 200, off.text
    assert settings_hook.activity_live_check_enabled(api["tenant"]) is False


def test_other_switches_keep_their_shape_without_an_explanation(api):
    """설명 칸은 있는 항목에만 싣는다 — 다른 항목의 모양은 그대로다."""
    view = _client().get("/admin/limits", headers=api["auth"]("limits:read")).json()
    row = next(r for r in view["limits"] if r["name"] == settings_hook.TAXI_CALL_PRODUCT)
    assert "text_ko" not in row
