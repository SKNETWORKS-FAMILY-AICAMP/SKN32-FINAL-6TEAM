# -*- coding: utf-8 -*-
"""개인 AI 입구(MCP) — `mcp_server.py`, `/mcp/`. `[2026-10-02 사용자 지시]`

☆지키려는 것: ①**호출자는 사용자 키가 정한다** — 키 없음·틀림은 연결 단계에서 401, 남의 여행은 보이지도 않는다(`customer_id` 인자가 없다)
②**MCP 는 새 규칙을 만들지 않는다** — 웹 API 를 그대로 부르니 같은 입력의 결과가 같다 ③**쓰기 도구는 스위치가 켜졌을 때만 등록된다**(기본 꺼짐)
④`mcp` 모듈 토글을 끄면 404 ⑤오류 · 결과 어디에도 사용자 키 원문이 없다.

★MCP 프로토콜로 **실제로 접속**해 본다(SDK 클라이언트 + 앱을 네트워크 없이 부르는 전송) — 도구 이름 개수만 세던 옛 검사(DoD-13)가 못 보던 것이다.

재현:

    python -m pytest tests/e2e/test_mcp_server.py -v
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.domains.travel_ops.modules.mcp import mcp_server

from .test_trip_api import _report, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _fresh_limit_cache, _h, _session, _web_body  # noqa: F401

READ_TOOLS = {"tripilot_list_trips", "tripilot_get_trip", "tripilot_get_notices", "tripilot_get_proposals",
              "tripilot_get_itinerary_schema",
              "tripilot_check_trip_risks", "tripilot_judge_move"}                            # `[2026-10-06]` 읽기 도구 둘 더 — `test_mcp_read_tools.py`
WRITE_TOOLS = {"tripilot_ask", "tripilot_report_issue", "tripilot_swap_item", "tripilot_choose_proposal",
               "tripilot_rollback", "tripilot_submit_itinerary", "tripilot_plan_trip"}
MESSAGE = {"message": "식당이 휴무예요", "at": "2030-01-01T12:00:00+09:00"}


def _trip(api, me, request_id="mcp-1") -> str:
    made = api["client"].post("/v1/web/trips", json=_web_body(api, request_id=request_id), headers=_h(me["user_key"]))
    assert made.status_code == 201, made.text
    return made.json()["trip_id"]


def _surface(api, *, write: bool, enabled: bool = True) -> mcp_server.McpSurface:
    """시험용 표면 — 진짜 앱(`api["client"].app`)을 네트워크 없이 부르는 MCP. 쓰기 스위치를 시험이 정한다."""
    app = api["client"].app
    return mcp_server.build_surface(lambda: app, enabled=lambda: enabled, write_enabled=write)


def _run(surface: mcp_server.McpSurface, key: str | None, scenario, *, headers: dict[str, str] | None = None) -> Any:
    """MCP 세션을 열어 `scenario(session)` 을 돌린다 — 접속은 MCP 프로토콜(initialize → 도구 호출)이다."""
    sent = dict(headers or {})
    if key:
        sent.setdefault("Authorization", f"Bearer {key}")

    def factory(headers=None, timeout=None, auth=None):                      # noqa: ANN001
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=surface.asgi), base_url="http://testserver",
                                 headers=headers, timeout=timeout, auth=auth, follow_redirects=True)

    async def go():
        async with surface.lifespan():
            async with streamablehttp_client("http://testserver/", headers=sent, httpx_client_factory=factory) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    return await scenario(session)

    return asyncio.run(go())


def _data(result) -> dict[str, Any]:
    assert not result.isError, result.content
    if result.structuredContent is not None:
        return result.structuredContent.get("result", result.structuredContent)
    return json.loads(result.content[0].text)


def _error_text(result) -> str:
    assert result.isError
    return "".join(c.text for c in result.content if getattr(c, "text", None))


# ── 순수 도우미 ───────────────────────────────────────────────────

def test_the_key_comes_from_bearer_first_then_the_user_key_header():
    assert mcp_server.key_from_headers({"authorization": "Bearer abc", "x-user-key": "zzz"}) == "abc"
    assert mcp_server.key_from_headers({"x-user-key": " zzz "}) == "zzz"
    assert mcp_server.key_from_headers({"authorization": "Basic abc"}) is None
    assert mcp_server.key_from_headers({}) is None


def test_the_outline_reads_like_a_plan_and_trimming_drops_the_map_pins():
    items = [{"seq": 2, "kind": "activity", "kind_label": "활동", "meal": None, "title": "고궁",
              "starts_at": "2026-10-05T10:00:00+09:00", "ends_at": "2026-10-05T11:30:00+09:00", "booked": True},
             {"seq": 1, "kind": "dining", "kind_label": "식사", "meal": "아침", "title": "개화",
              "starts_at": "2026-10-05T08:00:00+09:00", "ends_at": "2026-10-05T09:00:00+09:00", "booked": False}]
    assert mcp_server.outline_of(items) == ["10-05 08:00–09:00 [식사·아침] 개화", "10-05 10:00–11:30 [활동] 고궁 (예약)"]
    trimmed = mcp_server.trim_trip({"trip_id": "t", "items": items, "map": {"pins": [1]}, "history": list(range(9)),
                                    "plan_url": "u"}, day="2026-10-05")
    assert "map" not in trimmed and trimmed["plan_url"] == "u" and len(trimmed["items"]) == 2
    assert trimmed["recent_changes"] == [4, 5, 6, 7, 8] and trimmed["outline"][0].endswith("개화")
    assert mcp_server.trim_trip({"items": items}, day="2026-10-06")["items"] == []


def test_a_missing_key_is_a_clear_tool_error_that_never_prints_a_key(monkeypatch):
    monkeypatch.delenv("TRIPILOT_USER_KEY", raising=False)
    with pytest.raises(Exception) as caught:
        mcp_server.caller_of(None)
    assert "사용자 키가 없어요" in str(caught.value)


# ── 연결 단계(문지기) ─────────────────────────────────────────────

# invariant: INV-CS-SEC-009
def test_without_a_key_or_with_a_wrong_key_the_connection_is_401_and_a_disabled_module_is_404(api):
    me = _session(api)
    gate = _surface(api, write=False).asgi

    def post(headers, *, surface_gate=gate):
        transport = httpx.ASGITransport(app=surface_gate)

        async def go():
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
                return await http.post("/", headers={"Accept": "application/json, text/event-stream", **headers},
                                       json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

        return asyncio.run(go())

    none = post({})
    assert none.status_code == 401 and none.headers["www-authenticate"].startswith("Bearer")
    assert none.json()["error"]["code"] == "unauthenticated"
    assert post({"Authorization": "Bearer not-a-real-key"}).status_code == 401
    assert post({"X-User-Key": "not-a-real-key"}).status_code == 401
    off = post({"Authorization": f"Bearer {me['user_key']}"}, surface_gate=_surface(api, write=False, enabled=False).asgi)
    assert off.status_code == 404                                      # 모듈이 꺼져 있으면 표면이 없는 것처럼 — 키가 맞아도


def test_the_mcp_surface_is_mounted_on_the_customer_app(api):
    """앱에 `/mcp/` 로 붙어 있다 — 키 없이 두드리면 401(404 가 아니다)."""
    refused = api["client"].post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                 headers={"Accept": "application/json, text/event-stream"})
    assert refused.status_code == 401 and refused.headers["www-authenticate"].startswith("Bearer")


# ── 읽기 도구 ─────────────────────────────────────────────────────

# invariant: INV-CS-SEC-010
def test_by_default_only_read_tools_exist_and_all_say_they_are_read_only(api):
    me = _session(api)

    async def scenario(session):
        return (await session.list_tools()).tools

    tools = _run(_surface(api, write=False), me["user_key"], scenario)
    assert {t.name for t in tools} == READ_TOOLS
    assert all(t.annotations and t.annotations.readOnlyHint is True for t in tools)
    # 도구 인자에 customer_id 가 없다 — 호출자는 키가 정한다
    assert not any("customer_id" in (t.inputSchema.get("properties") or {}) for t in tools)


def test_my_trips_are_listed_with_kind_labels_and_someone_elses_trip_does_not_exist(api):
    me, other = _session(api), _session(api)
    trip_id = _trip(api, me)

    async def mine(session):
        listed = _data(await session.call_tool("tripilot_list_trips", {}))
        whole = _data(await session.call_tool("tripilot_get_trip", {"trip_id": trip_id}))
        day = whole["items"][0]["starts_at"][:10]
        that_day = _data(await session.call_tool("tripilot_get_trip", {"trip_id": trip_id, "day": day}))
        empty_day = _data(await session.call_tool("tripilot_get_trip", {"trip_id": trip_id, "day": "1999-01-01"}))
        bad_day = await session.call_tool("tripilot_get_trip", {"trip_id": trip_id, "day": "내일"})
        return listed, whole, that_day, empty_day, bad_day

    listed, whole, that_day, empty_day, bad_day = _run(_surface(api, write=False), me["user_key"], mine)
    assert [t["trip_id"] for t in listed["trips"]] == [trip_id]
    assert {i["kind_label"] for i in whole["items"]} >= {"식사", "활동", "이동"}
    assert [i["meal"] for i in whole["items"] if i["kind"] == "dining"] == ["아침", "점심", "저녁"]
    assert "map" not in whole and whole["plan_url"] and any("[식사·아침]" in line for line in whole["outline"])
    assert 0 < len(that_day["items"]) <= len(whole["items"]) and empty_day["items"] == []
    assert bad_day.isError and "YYYY-MM-DD" in _error_text(bad_day)

    async def theirs(session):
        listed = _data(await session.call_tool("tripilot_list_trips", {}))
        peek = await session.call_tool("tripilot_get_trip", {"trip_id": trip_id})
        return listed, peek

    listed, peek = _run(_surface(api, write=False), other["user_key"], theirs)
    assert listed == {"trips": []}                                       # 남의 여행은 목록에도 없다
    assert peek.isError and "404" in _error_text(peek)                   # 있는지도 말하지 않는다(웹과 같은 404)
    assert other["user_key"] not in _error_text(peek) and me["user_key"] not in _error_text(peek)


def test_the_itinerary_schema_tool_hides_customer_id_and_notices_and_proposals_read(api):
    me = _session(api)
    trip_id = _trip(api, me)

    async def scenario(session):
        schema = _data(await session.call_tool("tripilot_get_itinerary_schema", {}))
        notices = _data(await session.call_tool("tripilot_get_notices", {"trip_id": trip_id}))
        proposals = _data(await session.call_tool("tripilot_get_proposals", {"trip_id": trip_id}))
        return schema, notices, proposals

    schema, notices, proposals = _run(_surface(api, write=False), me["user_key"], scenario)
    assert "customer_id" not in schema["properties"] and "customer_id" not in schema.get("required", [])
    assert {"places", "items"} <= set(schema["properties"])
    assert isinstance(notices["notices"], list) and "proposals" in proposals


# ── 쓰기 도구 ─────────────────────────────────────────────────────

def test_with_the_write_switch_on_the_write_tools_appear_with_honest_annotations(api):
    me = _session(api)

    async def scenario(session):
        return (await session.list_tools()).tools

    tools = _run(_surface(api, write=True), me["user_key"], scenario)
    by_name = {t.name: t for t in tools}
    assert set(by_name) == READ_TOOLS | WRITE_TOOLS
    for name in WRITE_TOOLS:
        ann = by_name[name].annotations
        assert ann.readOnlyHint is False and ann.destructiveHint is False       # 일정만 바꾼다 — 되돌리기 가능, 결제·예약 없음
    assert not any("customer_id" in (t.inputSchema.get("properties") or {}) for t in tools)


def test_asking_over_mcp_gives_the_same_answer_as_the_web_and_a_repeat_is_not_processed_twice(api):
    """②MCP 는 새 규칙이 없다 — 같은 문장은 웹과 같은 결과, 같은 request_id 는 두 번 처리되지 않는다."""
    me = _session(api)
    trip_id = _trip(api, me)
    via_web = api["client"].post(f"/v1/web/trips/{trip_id}/messages", headers=_h(me["user_key"]),
                                 json={"request_id": "web-ask", **MESSAGE}).json()

    async def scenario(session):
        args = {"trip_id": trip_id, "request_id": "mcp-ask", **MESSAGE}
        first = _data(await session.call_tool("tripilot_ask", args))
        again = _data(await session.call_tool("tripilot_ask", args))
        return first, again

    first, again = _run(_surface(api, write=True), me["user_key"], scenario)
    assert first["status"] == via_web["status"] == "no_meal" and first["answer"] == via_web["answer"]
    assert again["status"] == "duplicate"


def test_reporting_a_delay_over_mcp_matches_the_web_twin_and_a_stranger_cannot_report(api):
    me, other = _session(api), _session(api)
    trip_id = _trip(api, me)
    body = {"type": "delay", "message": "30분 늦을 것 같아요", "minutes": 30, "at": "2030-01-01T09:00:00+09:00"}
    via_rest = api["client"].post(f"/v1/web/trips/{trip_id}/reports", headers=_h(me["user_key"]),
                                  json={"request_id": "rest-delay", **body})
    assert via_rest.status_code == 200, via_rest.text
    # 웹 쌍둥이 — 남의 키는 404
    assert api["client"].post(f"/v1/web/trips/{trip_id}/reports", headers=_h(other["user_key"]),
                              json={"request_id": "x", **body}).status_code == 404

    async def scenario(session):
        ok = _data(await session.call_tool("tripilot_report_issue", {
            "trip_id": trip_id, "type": "delay", "message": body["message"], "minutes": 30, "request_id": "mcp-delay"}))
        missing = await session.call_tool("tripilot_report_issue", {
            "trip_id": trip_id, "type": "delay", "message": "늦어요", "request_id": "mcp-delay-2"})
        return ok, missing

    ok, missing = _run(_surface(api, write=True), me["user_key"], scenario)
    assert ok["status"] == via_rest.json()["status"]
    assert missing.isError and "delay needs minutes" in _error_text(missing)     # 분을 지어내지 않고 거절을 그대로 전한다

    async def stranger(session):
        return await session.call_tool("tripilot_report_issue", {
            "trip_id": trip_id, "type": "closed", "message": "닫았어요", "request_id": "mcp-x"})

    denied = _run(_surface(api, write=True), other["user_key"], stranger)
    assert denied.isError and "404" in _error_text(denied)


def test_swap_and_rollback_use_the_current_version_and_a_stranger_gets_404(api):
    """다른 안으로 바꾸고(판이 오른다) 그 앞 판으로 되돌린다 — 두 도구 모두 **현재 판 번호를 서버에서 읽어** 보내 낡은 판 거절이 나지 않는다."""
    me, other = _session(api), _session(api)
    trip_id = _trip(api, me)
    assert _report(api, trip_id, "delay").status_code == 200           # 지연 → 점심에 다른 안이 마련된다(판 2) — 에이전트 입구로 준비
    view = api["client"].get(f"/v1/web/trips/{trip_id}", headers=_h(me["user_key"])).json()
    lunch = next(i for i in view["items"] if i["seq"] == 5)
    [alt] = lunch["other_options"]

    async def scenario(session):
        swapped = _data(await session.call_tool("tripilot_swap_item", {
            "trip_id": trip_id, "item_id": lunch["item_id"], "choice": alt["key"], "request_id": "mcp-swap"}))
        after_swap = _data(await session.call_tool("tripilot_get_trip", {"trip_id": trip_id}))
        back = _data(await session.call_tool("tripilot_rollback", {
            "trip_id": trip_id, "to_version": view["version"], "request_id": "mcp-rb"}))
        after_back = _data(await session.call_tool("tripilot_get_trip", {"trip_id": trip_id}))
        return swapped, after_swap, back, after_back

    swapped, after_swap, back, after_back = _run(_surface(api, write=True), me["user_key"], scenario)
    assert swapped["version"] == view["version"] + 1 == after_swap["version"]
    assert next(i for i in after_swap["items"] if i["seq"] == 5)["place"] == alt["name"]
    assert back["version"] == after_swap["version"] + 1 == after_back["version"]    # 되돌린 것도 새 판으로 기록된다
    assert next(i for i in after_back["items"] if i["seq"] == 5)["place"] == lunch["place"]

    async def stranger(session):
        return await session.call_tool("tripilot_rollback", {"trip_id": trip_id, "to_version": 1})

    denied = _run(_surface(api, write=True), other["user_key"], stranger)
    assert denied.isError and "404" in _error_text(denied)


def test_submitting_a_bad_itinerary_returns_the_problems_and_a_good_one_is_registered_for_me_only(api):
    me = _session(api)
    good = _web_body(api, request_id="mcp-submit")

    async def scenario(session):
        broken = await session.call_tool("tripilot_submit_itinerary", {"itinerary": {"title": "깨진 일정"}})
        made = _data(await session.call_tool("tripilot_submit_itinerary", {"itinerary": {**good, "customer_id": "x"}}))
        return broken, made

    broken, made = _run(_surface(api, write=True), me["user_key"], scenario)
    assert broken.isError and "validation_error" in _error_text(broken)            # 무엇이 계약과 다른지 돌려준다
    assert made["created"] is True                                                  # 몸통의 customer_id 는 무시된다 — 키가 정한다
    listed = api["client"].get("/v1/web/trips", headers=_h(me["user_key"])).json()["trips"]
    assert [t["trip_id"] for t in listed] == [made["trip_id"]]


# ── 키 보호 ───────────────────────────────────────────────────────

def test_no_error_or_result_ever_contains_the_user_key(api):
    me = _session(api)
    bogus = "00000000-0000-0000-0000-000000000000"

    async def scenario(session):
        calls = [("tripilot_get_trip", {"trip_id": bogus}), ("tripilot_get_notices", {"trip_id": bogus}),
                 ("tripilot_ask", {"trip_id": bogus, "message": "안녕"}),
                 ("tripilot_get_trip", {"trip_id": "not-a-uuid"})]
        return [await session.call_tool(name, args) for name, args in calls]

    results = _run(_surface(api, write=True), me["user_key"], scenario)
    assert all(r.isError for r in results)
    assert not any(me["user_key"] in _error_text(r) for r in results)


def test_the_stdio_proxy_refuses_to_start_without_a_user_key(monkeypatch):
    monkeypatch.delenv("TRIPILOT_USER_KEY", raising=False)
    with pytest.raises(SystemExit):
        mcp_server.main(["--base-url", "http://127.0.0.1:1"])
