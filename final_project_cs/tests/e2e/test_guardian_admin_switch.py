# -*- coding: utf-8 -*-
"""관리 콘솔의 「항로 지킴이」 스위치 — 끄면 화면에서 숨기고 서버의 자동 일정 변경도 멈춘다. `[2026-10-19 사용자 결정 — ST4F-613]`

관리 콘솔 화면은 `/admin/limits` 가 주는 목록을 그대로 그린다(참/거짓은 켜짐 · 꺼짐 고르기). 그래서 목록에 있고 저장이 먹으면 화면에도 스위치가 생긴다.
계약: `wiki/external/rest-endpoints/web-trips.md` 「항로 지킴이 운영 스위치」.

★지키려는 것
 ①끄면 공개 읽기 `GET /v1/web/features` 가 false, 여행 조회에 `guardian` 칸이 없고, 켜기 입구는 409 `guardian_disabled`(기록도 안 늘어난다).
 ②켠 여행도 끈 동안은 먼저 묻는다 — 판정 함수가 꺼짐으로 읽는다. 알림에는 항로 지킴이 몫이 붙지 않고, 이미 쌓인 알림의 몫도 목록에서 빠진다.
 ③저장값(`constraints` · `trip_guardian_changes`)은 그대로라 다시 켜면 원래대로 돌아온다.

재현:

    python -m pytest tests/e2e/test_guardian_admin_switch.py -v
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components import settings_hook
from app.domains.travel_ops.components.planning.pending import decide
from app.domains.travel_ops.components.planning.survey import on_disruption
from app.domains.travel_ops.modules.web_account import web_guard

from .test_ask_first import DUST, _item
from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_trip_guardian import ASK, AUTO_CHANGE, NO_SURVEY, _post, _rows, _sent, _stored, _trip
from .test_web_cookie_session import cookies  # noqa: F401
from .test_web_guard import _client

NAME = settings_hook.GUARDIAN


@pytest.fixture(autouse=True)
def _operator_values():
    web_guard.clear_cache()
    settings_hook.register(lambda tenant, name: web_guard.values(tenant).get(name))
    yield
    settings_hook.clear()
    web_guard.clear_cache()


def _switch(env, value):
    """관리 콘솔이 하는 것과 같다 — `/admin/limits` 를 읽고 그 판(revision)으로 바꾼다. `None` 은 기본값으로 되돌린다."""
    client = _client()
    read, write = env["auth"]("limits:read"), env["auth"]("limits:write")
    view = client.get("/admin/limits", headers=read).json()
    changed = client.patch("/admin/limits", headers=write, json={
        "expected_revision": view["revision"], "actor": "op-kim", "reason": "항로 지킴이 스위치 시험", "changes": {NAME: value}})
    assert changed.status_code == 200, changed.text
    return next(row for row in changed.json()["limits"] if row["name"] == NAME)


def _features(env) -> dict:
    response = env["client"].get("/v1/web/features")
    assert response.status_code == 200, response.text
    return response.json()


def _view(env, trip_id) -> dict:
    response = env["client"].get(f"/v1/web/trips/{trip_id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_console_lists_the_switch_off_by_default(cookies):
    """`[2026-10-23 사용자 지시]` 항로 지킴이는 테스트 기능이라 기본 꺼짐 — 켜려면 운영자가 스위치를 켠다."""
    view = _client().get("/admin/limits", headers=cookies["auth"]("limits:read")).json()
    row = next(r for r in view["limits"] if r["name"] == NAME)
    assert (row["type"], row["value"], row["source"]) == ("bool", False, "default")
    assert _features(cookies) == {"guardian": False, "risk_panel": False, "plan_input_extras": False}


def test_the_public_read_needs_no_session(cookies):
    """세션이 없는 등록 전 화면이 읽는다 — 키 · 쿠키 없이 열리고 개인 정보가 없다."""
    cookies["client"].cookies.clear()
    assert _features(cookies) == {"guardian": False, "risk_panel": False, "plan_input_extras": False}
    _switch(cookies, True)
    assert _features(cookies) == {"guardian": True, "risk_panel": False, "plan_input_extras": False}


def test_turning_it_off_hides_it_stops_automatic_changes_and_keeps_the_record(cookies):
    _switch(cookies, True)                                                  # 기본은 꺼짐 — 켠 상태에서 시작한다
    trip_id = _trip(cookies, constraints=NO_SURVEY)
    assert _post(cookies, trip_id, {"enabled": True, "via": "card"}).status_code == 200
    before, rows = _stored(trip_id), _rows(trip_id)
    assert _view(cookies, trip_id)["guardian"]["enabled"] is True
    assert decide(constraints=before, item=_item(), report=DUST).action == "apply"

    assert _switch(cookies, False)["value"] is False
    assert _features(cookies) == {"guardian": False, "risk_panel": False, "plan_input_extras": False}
    assert "guardian" not in _view(cookies, trip_id)                        # 화면이 아이콘 · 카드를 그리지 않는다
    refused = _post(cookies, trip_id, {"enabled": False, "via": "header"})
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "guardian_disabled"
    assert _rows(trip_id) == rows and _stored(trip_id) == before           # 아무것도 바꾸지 않았다
    stored = _stored(trip_id)
    assert on_disruption(stored) == "ask_first"                             # 켠 여행도 먼저 묻는다
    decision = decide(constraints=stored, item=_item(), report=DUST)
    assert (decision.action, decision.reason) == ("ask", "ask_first")

    assert _switch(cookies, True)["value"] is True                          # 다시 켜기
    assert _features(cookies) == {"guardian": True, "risk_panel": False, "plan_input_extras": False}
    assert _view(cookies, trip_id)["guardian"]["enabled"] is True           # 저장값대로 돌아온다
    assert decide(constraints=_stored(trip_id), item=_item(), report=DUST).action == "apply"


def test_a_missing_trip_is_refused_the_same_way_while_it_is_off(cookies):
    """본인 여행인지 보기 전에 거절한다 — 끈 동안은 어느 여행이든 같은 409."""
    _trip(cookies, constraints=NO_SURVEY)
    _switch(cookies, False)
    refused = _post(cookies, "00000000-0000-0000-0000-000000000000", {"enabled": True, "via": "header"})
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "guardian_disabled"


def _by_key(env, trip_id) -> dict:
    return {n["key"]: n for n in env["client"].get(f"/v1/web/trips/{trip_id}/notices").json()["notices"]}


def test_notices_carry_no_guardian_part_while_it_is_off(cookies):
    _switch(cookies, True)                                                  # 기본은 꺼짐 — 켠 상태에서 시작한다
    trip_id = _trip(cookies, constraints=NO_SURVEY)                         # 꺼 둔 여행(게스트는 여행 하나 — 한 여행으로 두 갈래를 본다)
    _sent(cookies, trip_id, "message", ASK, key="proposal:before")          # 끄기 전에 쌓인 「켜기」 알림
    assert cookies["client"].get(f"/v1/web/trips/{trip_id}/notices").json()["notices"][-1]["guardian"]["offer"]

    _switch(cookies, False)
    assert "guardian" not in _sent(cookies, trip_id, "message", ASK, key="proposal:after")   # 「항로 지킴이 켜기」 없음
    notices = _by_key(cookies, trip_id)
    assert {"proposal:before", "proposal:after"} <= set(notices)
    assert all(n["guardian"] is None for n in notices.values())                           # 이미 쌓인 알림의 몫도 빠진다

    _switch(cookies, True)
    notices = _by_key(cookies, trip_id)
    assert notices["proposal:before"]["guardian"]["offer"]                                 # 켜면 저장된 몫이 다시 보인다
    assert notices["proposal:after"]["guardian"] is None                                   # 끈 동안 만든 알림에는 처음부터 없다
    assert _post(cookies, trip_id, {"enabled": True, "via": "notice"}).status_code == 200

    _switch(cookies, False)
    assert "guardian" not in _sent(cookies, trip_id, "version", AUTO_CHANGE, version=2)       # 「항로 지킴이가 바꿨어요」 없음
    _switch(cookies, True)
    assert _sent(cookies, trip_id, "version", AUTO_CHANGE, version=3)["guardian"] == {"changed": True}   # 켜면 다시 붙는다
