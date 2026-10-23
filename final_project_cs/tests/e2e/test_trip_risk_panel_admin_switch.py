# -*- coding: utf-8 -*-
"""관리 콘솔의 「여행 화면 · 계획 확인 화면 위험 점검 칸」 스위치 — 기본 꺼짐, 운영 API 로 켜면 여행 조회 · 공개 읽기 `GET /v1/web/features` 의 `risk_panel` 이 true. `[2026-10-22 사용자 지시]`

관리 콘솔 화면은 `/admin/limits` 가 주는 목록을 그대로 그린다(참/거짓은 켜짐 · 꺼짐 고르기). 그래서 목록에 있고
저장이 먹으면 화면에도 스위치가 생긴다. 계약: `wiki/external/rest-endpoints/web-trips.md` 「여행 화면 위험 점검 칸」.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard

from .test_trip_api import _create, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import cookies  # noqa: F401
from .test_web_guard import _client

NAME = settings_hook.TRIP_RISK_PANEL


@pytest.fixture(autouse=True)
def _operator_values():
    web_guard.clear_cache()
    settings_hook.register(lambda tenant, name: web_guard.values(tenant).get(name))
    yield
    settings_hook.clear()
    web_guard.clear_cache()


def _risk_panel(api, trip_id):
    response = api["client"].get(f"/v1/trips/{trip_id}", headers=api["auth"]("trip:read"))
    assert response.status_code == 200, response.text
    return response.json()["risk_panel"]


def test_the_console_lists_the_switch_off_and_turning_it_on_reaches_the_trip_view(api):
    trip_id = _create(api)["trip_id"]
    client = _client()
    read, write = api["auth"]("limits:read"), api["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == NAME)
    assert (row["type"], row["value"], row["source"]) == ("bool", False, "default")
    assert _risk_panel(api, trip_id) is False

    on = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "시험 — 점검 칸 켜기", "changes": {NAME: True}})
    assert on.status_code == 200, on.text
    assert next(r for r in on.json()["limits"] if r["name"] == NAME)["value"] is True
    assert _risk_panel(api, trip_id) is True

    back = client.patch("/admin/limits", headers=write, json={
        "expected_revision": on.json()["revision"], "actor": "op-kim", "reason": "되돌림", "changes": {NAME: None}})
    assert back.status_code == 200, back.text
    assert _risk_panel(api, trip_id) is False


def test_the_plan_check_screen_reads_it_without_a_session(cookies):
    """계획 확인 화면(등록 전 · 일정 수정)은 세션 없이도 공개 읽기 `GET /v1/web/features` 로 안다 — 항로 지킴이 값과 따로 움직인다."""
    cookies["client"].cookies.clear()

    def features():
        response = cookies["client"].get("/v1/web/features")
        assert response.status_code == 200, response.text
        return response.json()

    assert features() == {"guardian": True, "risk_panel": False}
    client = _client()
    read, write = cookies["auth"]("limits:read"), cookies["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    on = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "시험 — 점검 칸 켜기", "changes": {NAME: True}})
    assert on.status_code == 200, on.text
    assert features() == {"guardian": True, "risk_panel": True}
