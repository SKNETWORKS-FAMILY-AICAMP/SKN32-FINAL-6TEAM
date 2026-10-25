# -*- coding: utf-8 -*-
"""관리 콘솔의 「계획 담기 화면 보조 칸」 스위치 — 기본 꺼짐, 운영 API 로 켜면 공개 읽기 `GET /v1/web/features` 의 `plan_input_extras` 가 true. `[2026-10-25 사용자 지시 — ST4F-739]`

관리 콘솔 화면은 `/admin/limits` 가 주는 목록을 그대로 그린다(참/거짓은 켜짐 · 꺼짐 고르기). 그래서 목록에 있고
저장이 먹으면 화면에도 스위치가 생긴다. 계약: `wiki/external/rest-endpoints/web-trips.md` 「계획 담기 화면 보조 칸」.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.modules.web_account import web_guard

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_cookie_session import cookies  # noqa: F401
from .test_web_guard import _client

NAME = settings_hook.PLAN_INPUT_EXTRAS


@pytest.fixture(autouse=True)
def _operator_values():
    web_guard.clear_cache()
    settings_hook.register(lambda tenant, name: web_guard.values(tenant).get(name))
    yield
    settings_hook.clear()
    web_guard.clear_cache()


def test_the_console_lists_it_off_and_the_plan_screen_reads_it_without_a_session(cookies):
    """계획 담기 화면은 세션이 없을 수 있다(새 고객의 첫 계획) — 키 · 쿠키 없이 읽고, 다른 스위치와 따로 움직인다."""
    cookies["client"].cookies.clear()

    def features():
        """이 스위치와 위험 점검 칸 값만 — 항로 지킴이 값은 공용 픽스처가 켜 둔다(`tests/conftest.py`)."""
        response = cookies["client"].get("/v1/web/features")
        assert response.status_code == 200, response.text
        return {name: response.json()[name] for name in ("risk_panel", "plan_input_extras")}

    client = _client()
    read, write = cookies["auth"]("limits:read"), cookies["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    row = next(r for r in view["limits"] if r["name"] == NAME)
    assert (row["type"], row["value"], row["source"]) == ("bool", False, "default")
    assert features() == {"risk_panel": False, "plan_input_extras": False}

    on = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "시험 — 보조 칸 켜기", "changes": {NAME: True}})
    assert on.status_code == 200, on.text
    assert next(r for r in on.json()["limits"] if r["name"] == NAME)["value"] is True
    assert features() == {"risk_panel": False, "plan_input_extras": True}

    back = client.patch("/admin/limits", headers=write, json={
        "expected_revision": on.json()["revision"], "actor": "op-kim", "reason": "되돌림", "changes": {NAME: None}})
    assert back.status_code == 200, back.text
    assert features()["plan_input_extras"] is False
