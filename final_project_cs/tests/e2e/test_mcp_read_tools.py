# -*- coding: utf-8 -*-
"""개인 AI 입구(MCP)의 읽기 도구 둘 — 「일정 위험 점검」 · 「이동 판정」. `[2026-10-06 사용자 요청]`

웹 입구: `GET /v1/web/trips/{id}/risks` · `POST /v1/web/moves/judge` — MCP 도구 `tripilot_check_trip_risks` · `tripilot_judge_move` 는 그것을 그대로 부르는 얇은 어댑터다.
구현: `components/watch/risk_report.py` · `components/itinerary/move_judge.py` · `ports/data_sources/{ratelimit,source_budget,base}.py`(캐시만 읽기 · 낮은 우선순위 몫) · `entry/trip_api.py` · `modules/mcp/mcp_server.py`

★지키려는 것
 ①본인 여행만 — 남의 여행 · 없는 여행 · 없는 항목은 같은 404, 키가 없으면 401. 읽기라 쓰기 스위치와 상관없이 등록된다(도구 7개).
 ②기본(`fresh=false`)은 **캐시만 읽는 점검기**만 부른다 — 바깥에 새로 묻는 점검기는 안 부르고, 횟수도 안 센다(하루 한도를 깎지 않는다).
 ③`fresh=true` 는 새로 묻는 점검기를 부르되 한 번에 `fresh_max_items` 개까지 · `risk_check` 로 센다(제한이 켜져 있으면 429). 점검기가 조립 안 된 서버는 503.
 ④확인 불가는 확인 불가로(`unknown`) · 문제는 원인과 함께(`problem`) — 지어내지 않는다. 확인 시각이 있다.
 ⑤이동 판정: 좌표 또는 일정 항목 · 서울 밖 `out_of_scope` · 판정기가 꺼져 있으면 `unavailable`(직선 어림만) · 두 시각을 같이 주면 422 · 횟수는 `move_judge` 로 센다.
 ⑥MCP 로 실제 접속해 같은 결과가 나오고, 남의 여행은 도구 오류다.

재현:

    python -m pytest tests/e2e/test_mcp_read_tools.py -v
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.entry.trip_api import build_trip_router
from app.domains.travel_ops.modules.mcp import mcp_server
from app.infrastructure.db.session import get_connection
from app.presentation.api.app import create_app

from .test_mcp_server import _data, _error_text, _run
from .test_trip_api import _iso, api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _fresh_limit_cache, _h, _override, _session, _web_body  # noqa: F401

NAMES = ("forecast", "weather_warning", "disaster_msg", "traffic_control", "air_quality", "earthquake")
AT = _iso("08:00")


def _report(*, problem: dict[str, Any] | None = None, failed: tuple[str, ...] = ()) -> dict[str, Any]:
    rows = [{"category": n, "status": "failed" if n in failed else "ok", "source": f"{n}-src", "confirmed_at": "2026-10-05T07:55:00+09:00",
             **({"reason": "값을 못 냈다"} if n in failed else {})} for n in NAMES]
    return {"verdict": "x", "disruptions": [problem] if problem else [], "advisories": [], "checks": rows, "checked_at": "2026-10-05T08:00:01+00:00"}


class FakeCheck:
    """점검 흉내 — 부른 장소를 남긴다. `first_problem` 이면 첫 호출만 문제를 낸다."""

    def __init__(self, *, first_problem=False, failed=()):
        self.calls, self.first_problem, self.failed = [], first_problem, failed

    def __call__(self, *, place, starts_at, region="서울"):
        self.calls.append(place["name"])
        problem = {"category": "traffic_control", "kind": "집회", "source": "경찰청"} if self.first_problem and len(self.calls) == 1 else None
        return _report(problem=problem, failed=self.failed)


def _client(cached: FakeCheck | None, fresh: FakeCheck | None) -> TestClient:
    router = build_trip_router(check_factory=(lambda: fresh) if fresh else None, cached_check_factory=(lambda: cached) if cached else None,
                               fresh_check_factory=(lambda: fresh) if fresh else None,
                               classifier_factory=lambda: (lambda m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"}))
    return TestClient(create_app(classifier=lambda m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"}, domain_routers=[router]))


def _trip(api, client, me, request_id="risk-1") -> dict[str, Any]:
    made = client.post("/v1/web/trips", json=_web_body(api, request_id=request_id), headers=_h(me["user_key"]))
    assert made.status_code == 201, made.text
    return client.get(f"/v1/web/trips/{made.json()['trip_id']}", headers=_h(me["user_key"])).json()


def _usage(api, action) -> int:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COALESCE(sum(used), 0) FROM web_usage WHERE tenant_id=%s AND action=%s AND who_kind='all'", (api["tenant"], action))
        return int(cur.fetchone()[0])


def _hook_state():
    return legs._leg_planner, legs._disruptions_from_events, legs._walk_limit_m, legs._basis


@pytest.fixture()
def no_legs():
    """이동 판정기 끼움 자리를 비워 두고 시작한다 — 끝나면 **원래 상태로** 되돌린다(전역이라 다른 시험에 새지 않게)."""
    saved = _hook_state()
    legs.clear()
    yield
    legs._leg_planner, legs._disruptions_from_events, legs._walk_limit_m, legs._basis = saved


# ── 일정 위험 점검 ────────────────────────────────────────────────
def test_the_default_reads_only_the_cached_checker_and_is_never_counted(api):
    cached, fresh = FakeCheck(first_problem=True), FakeCheck()
    client = _client(cached, fresh)
    me = _session(api)
    trip = _trip(api, client, me)
    body = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"at": AT}, headers=_h(me["user_key"]))
    assert body.status_code == 200, body.text
    report = body.json()
    assert report["mode"] == "cached" and report["scope"] == "upcoming" and report["trip_id"] == trip["trip_id"]
    assert cached.calls and fresh.calls == []                                                   # ② 새로 묻는 점검기는 안 불렀다
    assert _usage(api, "risk_check") == 0                                                       # 「새로 확인」으로는 센 것이 없다 — 하루 한도를 안 깎는다
    assert _usage(api, "risk_read") == 1                                                        # 캐시 읽기는 따로 센다(서버 조회 부하 — 코덱스 검토)
    first = report["items"][0]
    assert first["status"] == "problem" and first["problems"][0]["kind"] == "집회" and first["problems"][0]["label"] == "교통 통제"        # ④ 원인
    assert report["summary"]["problem"] == 1 and report["summary"]["clear"] == report["summary"]["checked"] - 1
    assert all(r["checked_at"] for r in report["items"]) and first["oldest_confirmed_at"] == "2026-10-05T07:55:00+09:00"


def test_fresh_calls_the_other_checker_with_fewer_items_and_counts(api):
    cached, fresh = FakeCheck(), FakeCheck()
    client = _client(cached, fresh)
    me = _session(api)
    trip = _trip(api, client, me)
    body = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"at": AT, "fresh": "true", "within_hours": 12}, headers=_h(me["user_key"])).json()
    assert body["mode"] == "fresh" and cached.calls == [] and len(fresh.calls) == len(body["items"]) == 3      # ③ 새로 확인은 3개까지
    assert any(s["reason"] == "over_limit" for s in body["skipped"])
    assert _usage(api, "risk_check") == 1


def test_a_fresh_check_is_refused_when_the_limit_is_on_but_cached_reads_keep_working(api):
    client = _client(FakeCheck(), FakeCheck())
    me = _session(api)
    trip = _trip(api, client, me)
    _override(api, "web.limits_enabled", True)
    _override(api, "web.risk_check.per_key_day", 1)
    url, headers = f"/v1/web/trips/{trip['trip_id']}/risks", _h(me["user_key"])
    assert client.get(url, params={"at": AT, "fresh": "true"}, headers=headers).status_code == 200
    refused = client.get(url, params={"at": AT, "fresh": "true"}, headers=headers)
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "usage_limit" and "Retry-After" in refused.headers
    assert client.get(url, params={"at": AT}, headers=headers).status_code == 200                # 캐시만 읽는 호출은 막히지 않는다


def test_cached_reads_have_their_own_daily_cap_when_the_limit_is_on(api):
    client = _client(FakeCheck(), FakeCheck())
    me = _session(api)
    trip = _trip(api, client, me)
    _override(api, "web.limits_enabled", True)
    _override(api, "web.risk_read.per_key_day", 2)
    url, headers = f"/v1/web/trips/{trip['trip_id']}/risks", _h(me["user_key"])
    assert [client.get(url, params={"at": AT}, headers=headers).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get(url, params={"at": AT, "fresh": "true"}, headers=headers).status_code == 200      # 새로 확인은 따로 센다


def test_unknown_stays_unknown_and_one_item_can_be_asked_outside_the_window(api):
    client = _client(FakeCheck(failed=("traffic_control",)), FakeCheck())
    me = _session(api)
    trip = _trip(api, client, me)
    target = next(i for i in trip["items"] if i["kind"] != "mobility" and i.get("place"))
    one = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"item_id": target["item_id"]}, headers=_h(me["user_key"]))   # at 없음 = 지금 — 범위 밖이어도 그 항목은 본다
    assert one.status_code == 200 and one.json()["scope"] == "item" and len(one.json()["items"]) == 1
    row = one.json()["items"][0]
    assert row["status"] == "unknown" and row["unknown_categories"][0]["category"] == "traffic_control"      # ④ 확인 불가를 문제 없음으로 말하지 않는다
    assert row["unknown_categories"][0]["reason"] == "값을 못 냈다" or "fresh" in row["unknown_categories"][0]["reason"]


def test_someone_elses_or_missing_trips_and_items_are_the_same_404_and_a_missing_key_is_401(api):
    client = _client(FakeCheck(), FakeCheck())
    mine, other = _session(api), _session(api)
    trip = _trip(api, client, mine)
    theirs = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", headers=_h(other["user_key"]))
    missing = client.get(f"/v1/web/trips/{uuid4()}/risks", headers=_h(other["user_key"]))
    assert theirs.status_code == missing.status_code == 404 and theirs.json() == missing.json()               # ①
    assert client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"item_id": str(uuid4())}, headers=_h(mine["user_key"])).status_code == 404
    assert client.get(f"/v1/web/trips/{trip['trip_id']}/risks").status_code == 401
    assert client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"within_hours": 0}, headers=_h(mine["user_key"])).status_code == 422
    assert client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"within_hours": 100}, headers=_h(mine["user_key"])).status_code == 422


def test_a_fresh_request_without_the_low_priority_checker_is_503_not_a_silent_swap(api):
    """`[검토 반영]` 낮은 우선순위 점검기가 없는 서버가 몫 없는 점검기로 조용히 대신하지 않는다."""
    client = _client(FakeCheck(), None)
    me = _session(api)
    trip = _trip(api, client, me)
    assert client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"at": AT}, headers=_h(me["user_key"])).status_code == 200
    refused = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"at": AT, "fresh": "true"}, headers=_h(me["user_key"]))
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "risk_check_unavailable"


def test_a_crowd_of_simultaneous_reads_is_turned_away_with_busy_and_the_slot_is_released(api, monkeypatch):
    """`[검토 반영]` 하루 횟수 제한과 별개로 동시에 처리하는 수에 상한이 있다 — 연결 · 스레드를 다 쓰지 못한다."""
    import threading

    from app.core import settings as settings_module

    guard = settings_module.get_guardrails()
    real_get = guard.get
    monkeypatch.setattr(guard, "get", lambda key, *a, **kw: 1 if key == "travel.mcp.max_concurrent.risk_check" else real_get(key, *a, **kw), raising=False)
    started, release = threading.Event(), threading.Event()

    class Blocking(FakeCheck):
        def __call__(self, **kw):
            started.set()
            release.wait(10)
            return super().__call__(**kw)

    client = _client(Blocking(), FakeCheck())
    me = _session(api)
    trip = _trip(api, client, me)
    url, headers = f"/v1/web/trips/{trip['trip_id']}/risks", _h(me["user_key"])
    first: dict[str, Any] = {}
    worker = threading.Thread(target=lambda: first.update(code=client.get(url, params={"at": AT}, headers=headers).status_code))
    worker.start()
    assert started.wait(10)
    busy = client.get(url, params={"at": AT}, headers=headers)
    assert busy.status_code == 503 and busy.json()["error"]["code"] == "busy" and busy.headers["Retry-After"] == "5"
    release.set()
    worker.join(20)
    assert first["code"] == 200
    assert client.get(url, params={"at": AT}, headers=headers).status_code == 200                # 자리가 돌아왔다


def test_absurd_times_are_422_not_a_server_error(api, no_legs):
    client = _client(FakeCheck(), FakeCheck())
    me = _session(api)
    trip = _trip(api, client, me)
    headers = _h(me["user_key"])
    assert client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"at": "9999-12-31T23:59:59+09:00"}, headers=headers).status_code == 422
    assert client.post("/v1/web/moves/judge", json={**COORDS, "arrive_by": "0001-01-01T00:00:00+09:00"}, headers=headers).status_code == 422


def test_a_server_without_the_checker_says_so_instead_of_pretending(api):
    client = _client(None, None)
    me = _session(api)
    trip = _trip(api, client, me)
    for params in ({}, {"fresh": "true"}):
        response = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params=params, headers=_h(me["user_key"]))
        assert response.status_code == 503 and response.json()["error"]["code"] == "risk_check_unavailable"
    assert _usage(api, "risk_check") == 0                                                       # 못 한 것을 센 횟수에 넣지 않는다


# ── 이동 판정 ─────────────────────────────────────────────────────
class FakeLeg:
    def __init__(self):
        self.calls = []

    def __call__(self, a, b, arrive_dt, not_before_dt=None):
        from datetime import timedelta
        self.calls.append((a["name"], b["name"], arrive_dt, not_before_dt))
        route = {"from": a["name"], "to": b["name"], "planned": "subway",
                 "options": [{"id": "subway", "label": "지하철 3호선", "eta_min": 12, "walk_m": 300, "fare_krw": 1550, "uses": [{"line": "3호선"}]}]}
        return {"route": route, "starts_at": arrive_dt - timedelta(minutes=15), "ends_at": arrive_dt - timedelta(minutes=3), "eta_min": 12, "left_out": []}, None


def _register(leg):
    legs.register(leg_planner=lambda *a, **kw: leg, disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: 1500.0,
                  basis=lambda: {"mode": "enabled", "rules_version": "v-test", "timetable_stale": False, "timetable_built_at": "2026-10-01T00:00:00+09:00"})


COORDS = {"origin": {"name": "경복궁", "lat": 37.5796, "lon": 126.9770}, "destination": {"name": "시청", "lat": 37.5663, "lon": 126.9779}}


def test_a_move_by_coordinates_is_judged_and_counted(api, no_legs):
    leg = FakeLeg()
    client = _client(FakeCheck(), FakeCheck())
    _register(leg)                                                                              # ★앱을 만든 **뒤**에 꽂는다 — 앱 조립이 끼움 자리를 비우기도 한다
    me = _session(api)
    body = client.post("/v1/web/moves/judge", json={**COORDS, "arrive_by": "2026-10-07T10:00:00"}, headers=_h(me["user_key"]))
    assert body.status_code == 200, body.text
    out = body.json()
    assert out["status"] == "judged" and out["grade"] == "timetable" and out["eta_min"] == 12 and out["route"]["label"] == "지하철 3호선"
    assert out["depart_at"].startswith("2026-10-07T09:45:00+09:00")                             # 시간대 없는 도착 시각은 서울 시각으로 읽는다
    assert out["basis"]["rules_version"] == "v-test" and out["checked_at"]
    assert _usage(api, "move_judge") == 1 and leg.calls[0][2].utcoffset().total_seconds() == 9 * 3600


def test_a_move_by_trip_items_uses_that_trips_places_and_only_my_trip(api, no_legs):
    leg = FakeLeg()
    client = _client(FakeCheck(), FakeCheck())
    _register(leg)                                                                              # ★앱을 만든 **뒤**에 꽂는다 — 앱 조립이 끼움 자리를 비우기도 한다
    mine, other = _session(api), _session(api)
    trip = _trip(api, client, mine)
    placed = [i for i in trip["items"] if i["kind"] != "mobility" and i.get("place")]
    body = {"trip_id": trip["trip_id"], "origin": {"item_id": placed[0]["item_id"]}, "destination": {"item_id": placed[1]["item_id"]}}
    done = client.post("/v1/web/moves/judge", json=body, headers=_h(mine["user_key"]))
    assert done.status_code == 200 and done.json()["status"] in ("judged", "out_of_scope"), done.text
    stranger = client.post("/v1/web/moves/judge", json=body, headers=_h(other["user_key"]))
    missing = client.post("/v1/web/moves/judge", json={**body, "trip_id": str(uuid4())}, headers=_h(other["user_key"]))
    assert stranger.status_code == missing.status_code == 404 and stranger.json() == missing.json()           # ①
    no_trip = client.post("/v1/web/moves/judge", json={"origin": {"item_id": placed[0]["item_id"]}, "destination": COORDS["destination"]}, headers=_h(mine["user_key"]))
    assert no_trip.status_code == 422 and no_trip.json()["error"]["code"] == "trip_id_required"
    ghost = client.post("/v1/web/moves/judge", json={**body, "origin": {"item_id": str(uuid4())}}, headers=_h(mine["user_key"]))
    assert ghost.status_code == 404


def test_bad_move_requests_are_422_and_outside_seoul_is_not_judged(api, no_legs):
    leg = FakeLeg()
    client = _client(FakeCheck(), FakeCheck())
    _register(leg)                                                                              # ★앱을 만든 **뒤**에 꽂는다 — 앱 조립이 끼움 자리를 비우기도 한다
    me = _session(api)
    headers = _h(me["user_key"])
    both = client.post("/v1/web/moves/judge", json={**COORDS, "depart_at": "2026-10-07T09:00:00+09:00", "arrive_by": "2026-10-07T10:00:00+09:00"}, headers=headers)
    assert both.status_code == 422 and both.json()["error"]["code"] == "invalid_request"
    nameless = client.post("/v1/web/moves/judge", json={"origin": {"name": "어딘가"}, "destination": COORDS["destination"]}, headers=headers)
    assert nameless.status_code == 422 and nameless.json()["error"]["code"] == "invalid_place"             # 좌표 없는 장소
    assert client.post("/v1/web/moves/judge", json={**COORDS, "extra": 1}, headers=headers).status_code == 422
    assert client.post("/v1/web/moves/judge", json=COORDS).status_code == 401
    far = client.post("/v1/web/moves/judge", json={"origin": COORDS["origin"], "destination": {"name": "수원", "lat": 37.2636, "lon": 127.0286}}, headers=headers)
    assert far.status_code == 200 and far.json()["status"] == "out_of_scope" and far.json()["grade"] == "none" and leg.calls == []
    assert _usage(api, "move_judge") == 1                                                       # 422 는 세지 않고 서울 밖 판정 요청은 센다


def test_a_server_without_the_judge_returns_a_straight_line_estimate_and_says_it(api, no_legs):
    client = _client(FakeCheck(), FakeCheck())
    me = _session(api)
    out = client.post("/v1/web/moves/judge", json=COORDS, headers=_h(me["user_key"])).json()
    assert out["status"] == "unavailable" and out["grade"] == "estimate" and out["estimate"]["straight_line_m"] > 0 and "route" not in out


# ── MCP 로 실제 접속 ──────────────────────────────────────────────
def _surface(client):
    return mcp_server.build_surface(lambda: client.app, enabled=lambda: True, write_enabled=False)


def test_both_tools_are_read_only_and_exist_even_with_the_write_switch_off(api, no_legs):
    client = _client(FakeCheck(), FakeCheck())
    me = _session(api)

    async def scenario(session):
        return {t.name: t for t in (await session.list_tools()).tools}

    tools = _run(_surface(client), me["user_key"], scenario)
    assert len(tools) == 8                                                                       # 읽기 5 + 새 둘 + 재난 뒤 꾸러미 하나 — 쓰기 7개는 없다
    for name in ("tripilot_check_trip_risks", "tripilot_judge_move", "tripilot_get_recovery_brief"):
        assert name in tools and tools[name].annotations.readOnlyHint is True and tools[name].annotations.destructiveHint is False


def test_the_risk_tool_over_mcp_matches_the_web_and_a_stranger_gets_a_tool_error(api, no_legs):
    client = _client(FakeCheck(first_problem=True), FakeCheck())
    mine, other = _session(api), _session(api)
    trip = _trip(api, client, mine)
    target = next(i for i in trip["items"] if i["kind"] != "mobility" and i.get("place"))

    async def ask(session):
        return await session.call_tool("tripilot_check_trip_risks", {"trip_id": trip["trip_id"], "item_id": target["item_id"]})

    got = _data(_run(_surface(client), mine["user_key"], ask))
    web = client.get(f"/v1/web/trips/{trip['trip_id']}/risks", params={"item_id": target["item_id"]}, headers=_h(mine["user_key"])).json()
    assert got["items"][0]["status"] == "problem" and got["items"][0]["item_id"] == web["items"][0]["item_id"] and got["mode"] == "cached"      # 같은 규칙 · 같은 입구
    assert "404" in _error_text(_run(_surface(client), other["user_key"], ask))                  # ① 남의 여행


def test_the_move_tool_over_mcp_reports_the_grade_and_never_leaks_the_key(api, no_legs):
    leg = FakeLeg()
    client = _client(FakeCheck(), FakeCheck())
    _register(leg)                                                                              # ★앱을 만든 **뒤**에 꽂는다 — 앱 조립이 끼움 자리를 비우기도 한다
    me = _session(api)

    async def go(session):
        return await session.call_tool("tripilot_judge_move", {"origin_name": "경복궁", "origin_lat": 37.5796, "origin_lon": 126.977,
                                                                "destination_name": "시청", "destination_lat": 37.5663, "destination_lon": 126.9779,
                                                                "arrive_by": "2026-10-07T10:00:00+09:00"})

    result = _run(_surface(client), me["user_key"], go)
    out = _data(result)
    assert out["status"] == "judged" and out["grade"] == "timetable" and out["route"]["label"] == "지하철 3호선"
    assert me["user_key"] not in str(result)

    async def bad(session):
        return await session.call_tool("tripilot_judge_move", {"origin_name": "어딘가", "destination_lat": 37.5, "destination_lon": 127.0})

    assert "invalid_place" in _error_text(_run(_surface(client), me["user_key"], bad))
