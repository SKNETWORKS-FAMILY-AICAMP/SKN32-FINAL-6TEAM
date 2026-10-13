# -*- coding: utf-8 -*-
"""관리 콘솔의 「식당 대체 후보 구글 가격 비교」 스위치 — 운영 API 로 켜면 가격 조회가 켜진다. `[2026-10-13 사용자 지시]`

관리 콘솔 화면은 `/admin/limits` 가 주는 목록을 그대로 그린다(참/거짓은 켜짐 · 꺼짐 고르기). 그래서 목록에 있고
저장이 먹으면 화면에도 스위치가 생긴다.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_guard import _client

NAME = settings_hook.GOOGLE_PRICE


@pytest.fixture(autouse=True)
def _operator_values():
    web_guard.clear_cache()
    settings_hook.register(lambda tenant, name: web_guard.values(tenant).get(name))
    yield
    settings_hook.clear()
    web_guard.clear_cache()


def test_the_console_lists_the_switch_off_and_turning_it_on_takes_effect(api):
    client = _client()
    read, write = api["auth"]("limits:read"), api["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == NAME)
    assert (row["type"], row["value"], row["source"]) == ("bool", False, "default")
    assert settings_hook.google_price_enabled(api["tenant"]) is False

    wrong = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "시험", "changes": {NAME: "on"}})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "wrong_type"

    on = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "구글 유료 결제 완료", "changes": {NAME: True}})
    assert on.status_code == 200, on.text
    assert next(r for r in on.json()["limits"] if r["name"] == NAME)["value"] is True
    assert settings_hook.google_price_enabled(api["tenant"]) is True

    off = client.patch("/admin/limits", headers=write, json={
        "expected_revision": on.json()["revision"], "actor": "op-kim", "reason": "되돌림", "changes": {NAME: None}})
    assert off.status_code == 200, off.text
    assert settings_hook.google_price_enabled(api["tenant"]) is False
