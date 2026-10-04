# -*- coding: utf-8 -*-
"""이동 계산기를 **켠 채** 화면이 타는 길(계획 짜기 → 등록 → 조회)을 실제 시간표로 흘린다.

★왜 있는가. 이동 계산기는 서버 기동 때 설정 `mobility_data_dir` 로 켜지고, 일정 짜기·장소 교체·사고 뒤 재경로·채팅 답이 그것을 쓴다.
  그런데 시험 기본값은 「꺼짐」(`tests/conftest.py`)이라, 켰을 때 실제로 도는지 보는 시험이 없었다 — 자료를 켠 컴퓨터에서만 다른 시험이
  깨지는 식으로 뒤늦게 드러났다(밀도 어긋남 · 달력 밖 날짜에서 장소 교체가 터짐 · 근거 문구가 옛 값).
★서버를 **기동 절차 그대로** 켠다 — 설정 복사본에 `mobility_data_dir` 만 넣고 `create_app` 을 부르면 조립(`build_registry`)이 자료를 확인하고
  적재한다. 계산기 상태를 직접 만지지 않는다.
★실제 시간표(저장소 안 `datasets/mobility/processed`)가 없는 기기는 건너뛴다 — 이유를 달고(조용한 스킵이 아니다).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.composition as composition
import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.mobility import wiring
from app.modules.travel_ops.mobility.engine import paths
from app.modules.travel_ops.trip_api import build_trip_router
from app.presentation import security
from app.presentation.api.app import create_app

DATA = paths.REPO_ROOT / "datasets" / "mobility" / "processed"
pytestmark = pytest.mark.skipif(
    not (DATA / "mobility" / "timetable_v1.jsonl").exists(),
    reason="이동 자료(datasets/mobility/processed)가 없다 — 이동 담당이 develop 에 올린 자료를 받아야 돈다")

#: 서울 안에서 서로 **먼** 곳 — 도보 상한(1,200 m) 밖이라 지하철·버스 경로가 나온다
ACTIVITIES = [
    ("경복궁 관람지", 37.5796, 126.9770, {"district": "종로구", "indoor": False, "hours": ["09:00", "18:00"]}),
    ("국립박물관 관람지", 37.5240, 126.9803, {"district": "용산구", "indoor": True, "hours": ["09:00", "18:00"]}),
    ("성수 공방 관람지", 37.5445, 127.0560, {"district": "성동구", "indoor": True, "hours": ["09:00", "18:00"]}),
]
DINING = [
    ("종로 국수집", 37.5704, 126.9920, {"district": "종로구", "indoor": True, "hours": ["11:00", "21:00"]}),
    ("이태원 식당", 37.5345, 126.9946, {"district": "용산구", "indoor": True, "hours": ["11:00", "21:00"]}),
    ("성수 식당", 37.5433, 127.0557, {"district": "성동구", "indoor": True, "hours": ["11:00", "21:00"]}),
]


@pytest.fixture()
def flow(monkeypatch):
    before_paths = (paths.SOURCE, paths.DATA_DIR)
    before_state = dict(wiring._STATE)
    original = settings_module.get_settings()
    tenant = "mobflow_" + uuid4().hex[:12]
    # 계산기를 켜는 설정 — 기동(create_app → build_registry)이 자료를 확인·적재한다
    test_settings = original.model_copy(update={"tenant_id": tenant, "mobility_data_dir": str(DATA)})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)
    monkeypatch.setattr(composition, "get_settings", lambda: test_settings)      # 조립(build_registry)이 이름으로 미리 가져다 쓴다
    customer = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "mobflow"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)",
                    (customer, tenant, "mobflow-customer"))
        for kind, rows in (("activity", ACTIVITIES), ("dining", DINING)):
            for name, lat, lon, attributes in rows:
                cur.execute("INSERT INTO places (tenant_id,name,kind,latitude,longitude,attributes) VALUES (%s,%s,%s,%s,%s,%s)",
                            (tenant, name, kind, lat, lon, json.dumps(attributes, ensure_ascii=False)))
    client = TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(check_factory=lambda: (lambda **_k: {"verdict": "clear"}))]))
    assert wiring.mode() == "enabled", "기동이 이동 계산기를 켜지 못했다 — 설정 mobility_data_dir 가 조립에 닿지 않는다"

    def auth(scope):
        return {"Authorization": "Bearer " + security._development_key(scope, original.secret_key)}

    def ask(start: date, **override):
        body = {"request_id": override.pop("request_id", "mf-1"), "customer_id": str(customer), "city": "서울",
                "start_date": start.isoformat(), "days": 1, "party_size": 2, "locale": "ko"}
        body.update(override)
        return client.post("/v1/trips/plan", json=body, headers=auth("trip:write"))

    yield {"client": client, "auth": auth, "ask": ask, "customer": customer, "tenant": tenant}

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for sql in ("DELETE FROM web_usage WHERE tenant_id=%s", "DELETE FROM place_catalog WHERE tenant_id=%s",
                    "DELETE FROM itinerary_items WHERE tenant_id=%s", "DELETE FROM itinerary_versions WHERE tenant_id=%s",
                    "DELETE FROM outbox WHERE tenant_id=%s", "DELETE FROM trips WHERE tenant_id=%s",
                    "DELETE FROM places WHERE tenant_id=%s", "DELETE FROM customers WHERE tenant_id=%s",
                    "DELETE FROM tenants WHERE tenant_id=%s"):
            cur.execute(sql, (tenant,))
    paths._layout(before_paths[1], before_paths[0])          # 다른 시험이 자료 폴더 상태를 물려받지 않게
    wiring._STATE.clear()
    wiring._STATE.update(before_state)


def test_a_plan_is_moved_by_the_real_timetable_and_registers(flow):
    body = flow["ask"](date(2026, 10, 5)).json()
    assert body["status"] == "drafted" and body["checks"]["violations"] == [], body
    draft = body["draft"]
    moves = [it for it in draft["items"] if it["kind"] == "mobility"]
    assert moves, "하루 장소 사이에 이동이 들어간다"
    by_engine = [m for m in moves if m["detail"]["planner"]["transfer_basis"] == "시간표 판정(이동 계산기)"]
    assert by_engine, "적어도 한 이동은 계산기(시간표 판정)가 채웠다 — 전부 어림값이면 계산기가 안 닿은 것이다"
    real = [o for m in by_engine for o in draft["routes"][m["route"]]["options"] if o["uses"]]
    assert real, "먼 장소 사이는 지하철·버스 경로(uses)가 실려야 한다 — 앞 판은 늘 빈칸이었다"
    for option in real:
        assert option["eta_min"] >= 1 and option["id"].split("_")[0] in ("subway", "bus", "walk")
    # 이동은 앞 일정이 끝난 뒤 나서고, 다음 일정 시작 전에 닿는다
    items = draft["items"]
    for index, item in enumerate(items):
        if item["kind"] != "mobility" or item not in by_engine:
            continue
        leave, arrive = datetime.fromisoformat(item["starts_at"]), datetime.fromisoformat(item["ends_at"])
        assert leave >= datetime.fromisoformat(items[index - 1]["ends_at"])
        assert arrive <= datetime.fromisoformat(items[index + 1]["starts_at"])
    # 밀도 — 계획이 말한 값 = 등록이 재는 값(이동을 계산기로 채운 뒤 다시 잰다)
    created = flow["client"].post("/v1/trips", headers=flow["auth"]("trip:write"),
                                  json={"request_id": "mf-reg", "customer_id": str(flow["customer"]), **draft})
    assert created.status_code == 201, created.text
    read = flow["client"].get(f"/v1/trips/{created.json()['trip_id']}", headers=flow["auth"]("trip:read"))
    assert read.status_code == 200, read.text
    # 조회는 화면용 요약이다 — 경로 정의(route_def)는 안 나가고, 화면이 쓰는 출발 시각과 길찾기 링크가 나간다
    stored = [it for it in read.json()["items"] if it["kind"] == "mobility"]
    assert [it["starts_at"] for it in stored] == [m["starts_at"] for m in moves], "등록된 이동의 출발 시각 = 계획의 출발 시각"
    assert all(it["map_url"] for it in stored), "이동마다 지도 길찾기 링크가 있다"


def test_a_registered_plan_gets_route_lines_from_our_own_road_graph(flow):
    """★`[2026-10-04]` 화면이 이동 항목마다 지도에 경로선을 그릴 수 있게 — 외부 길찾기 API 없이 우리 도로 그래프·역 좌표로 만든 형상.
    계획 짜기 → 등록 → 저장된 항목에서 경로선을 뽑는다. 선은 두 장소 좌표에서 시작해 끝나고, 점이 둘 넘는 실제 길이어야 한다(직선 둘이 아니다)."""
    from app.modules.travel_ops.mobility.route_shape import shapes_for_items
    from app.modules.travel_ops.itinerary import TripStore

    body = flow["ask"](date(2026, 10, 5), request_id="mf-shape").json()
    assert body["status"] == "drafted", body
    created = flow["client"].post("/v1/trips", headers=flow["auth"]("trip:write"),
                                  json={"request_id": "mf-shape-reg", "customer_id": str(flow["customer"]), **body["draft"]})
    assert created.status_code == 201, created.text
    from uuid import UUID
    with get_connection() as conn:
        _trip, items = TripStore(flow["tenant"]).latest(conn, UUID(created.json()["trip_id"]))
    shapes = shapes_for_items(items)
    moves = [it for it in items if it.kind == "mobility"]
    assert shapes and len(shapes) <= len(moves)
    drawn = [s for s in shapes if s["source"] != "straight_line"]
    assert drawn, "적어도 한 이동은 도로 그래프·역 좌표로 그려진다 — 전부 직선이면 길찾기가 안 닿은 것이다"
    for s in drawn:
        coords = s["line"]["coordinates"]
        assert s["line"]["type"] == "LineString" and len(coords) > 2 and s["grade"] == "추정"
        assert 50 < s["distance_m"] < 40_000, "서울 안 이동 거리(걸어갈 만한 가까운 곳 사이도 있다)"
        assert all(126.7 < lng < 127.3 and 37.3 < lat < 37.8 for lng, lat in coords), "서울 범위 밖 좌표가 섞였다"


def test_a_date_the_holiday_table_does_not_cover_falls_back_to_estimates_not_a_crash(flow):
    """공휴일표(2026~2027) 밖의 해 — 계산기는 평일·휴일을 짐작하지 않고 멈춘다. 계획 짜기가 그 오류로 터지지 않고
    종전 어림값(추정)으로 짜야 한다(계산기가 못 채움 → 대체 값, 이유는 남는다)."""
    response = flow["ask"](date(2030, 1, 7), request_id="mf-2030")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "drafted", body
    moves = [it for it in body["draft"]["items"] if it["kind"] == "mobility"]
    assert moves
    for move in moves:
        assert move["detail"]["planner"]["transfer_basis"] != "시간표 판정(이동 계산기)", "달력 밖 날짜를 시간표로 판정했다고 하면 안 된다"
        assert all(o["uses"] == [] for o in body["draft"]["routes"][move["route"]]["options"])


def test_the_density_the_plan_reports_is_the_one_registration_measures(flow):
    """하루를 맞추는 반복은 이동을 어림값으로 넣고, 최종 이동은 계산기가 채운다 — 계획이 말한 밀도와 등록이 재는 밀도가 같아야 한다
    (앞 판은 0.487 ≠ 0.501 로 어긋났다). 어림값으로 잰 값은 estimated_density 로 남는다."""
    from app.modules.travel_ops.survey import SURVEY_VERSION

    body = flow["ask"](date(2026, 10, 5), request_id="mf-dens",
                       constraints={"survey": {"version": SURVEY_VERSION, "pace": "packed"}}).json()
    assert body["status"] == "drafted", body
    created = flow["client"].post("/v1/trips", headers=flow["auth"]("trip:write"),
                                  json={"request_id": "mf-dens-reg", "customer_id": str(flow["customer"]), **body["draft"]})
    assert created.status_code == 201, created.text
    read = flow["client"].get(f"/v1/trips/{created.json()['trip_id']}", headers=flow["auth"]("trip:read")).json()
    planned = {d["date"]: d["actual_density"] for d in body["planner"]["density"]["days"]}
    registered = {row["date"]: round(row["actual_density"], 3) for row in read["density"]}
    assert registered == planned, (planned, registered)


def test_swapping_a_registered_place_rejudges_the_moves_around_it_with_the_real_timetable(flow):
    """등록된 여행의 식당을 먼 곳(잠실)으로 바꾸면 앞뒤 이동이 실제 시간표로 다시 판정된다 — 새 이름 · 새 노선 · 근거 「시간표 판정」.
    (앞 판은 이동을 옛 장소 이름·옛 노선으로 둬 출발 알림이 옛 식당으로 나갔다.)"""
    from uuid import uuid4

    from app.infrastructure.db.session import get_connection
    from app.modules.travel_ops.itinerary import TripStore
    from app.modules.travel_ops.itinerary_changes import ItineraryChange

    draft = flow["ask"](date(2026, 10, 5), request_id="mf-swap").json()["draft"]
    created = flow["client"].post("/v1/trips", headers=flow["auth"]("trip:write"),
                                  json={"request_id": "mf-swap-reg", "customer_id": str(flow["customer"]), **draft})
    assert created.status_code == 201, created.text
    with get_connection() as conn:
        _, items = TripStore(flow["tenant"]).latest(conn, __import__("uuid").UUID(created.json()["trip_id"]))
    meal = next(i for i in items if i.kind == "dining")
    far = {"place_id": str(uuid4()), "name": "잠실 새 식당", "latitude": 37.5133, "longitude": 127.1028}
    swapped = meal.replaced_by(place=far, title="잠실 새 식당 식사")
    swapped.place = far
    after = ItineraryChange(reason="customer_report", causes=[], notice={},
                            replacements={meal.item_id: swapped}).new_items(items)
    by_seq = sorted(after, key=lambda i: i.seq)
    index = next(n for n, i in enumerate(by_seq) if i.item_id == swapped.item_id)
    around = [by_seq[j] for j in (index - 1, index + 1) if 0 <= j < len(by_seq) and by_seq[j].kind == "mobility"]
    assert around, "바뀐 식당 바로 앞뒤에 이동이 있다"
    for move in around:
        assert move.detail["route_basis"] == "rejudged", move.detail.get("route_basis")
        assert move.detail["planner"]["transfer_basis"] == "시간표 판정(이동 계산기)"
        assert "잠실 새 식당" in move.title or "잠실 새 식당" == move.detail["route_def"]["from"], move.title
    assert any(o["uses"] for m in around for o in m.detail["route_def"]["options"]), "먼 곳이라 지하철·버스 노선이 실린다"


def _registered_moves(flow, request_id):
    """계획 → 등록 → 저장소에서 다시 읽은 항목. 이동 항목은 경로 정의(route_def)를 들고 있다."""
    import uuid

    from app.modules.travel_ops.itinerary import TripStore

    draft = flow["ask"](date(2026, 10, 5), request_id=request_id).json()["draft"]
    created = flow["client"].post("/v1/trips", headers=flow["auth"]("trip:write"),
                                  json={"request_id": request_id + "-reg", "customer_id": str(flow["customer"]), **draft})
    assert created.status_code == 201, created.text
    with get_connection() as conn:
        _, items = TripStore(flow["tenant"]).latest(conn, uuid.UUID(created.json()["trip_id"]))
    return sorted(items, key=lambda i: i.seq)


def test_after_an_incident_a_blocked_route_is_replaced_from_the_real_timetable(flow):
    """저장된 대안이 다 막히면 이동 계산기가 사고를 반영해 새 경로를 찾는다(#38·#39) - 실제 시간표로.
    지하철 경로의 환승역이 무정차라는 사건을 넣고, 그 역을 빼고도 갈 수 있는 새 경로가 실려야 한다."""
    from datetime import timedelta

    from app.modules.travel_ops.itinerary_changes import (ItineraryChange, next_after, place_before,
                                                          plan_route_adjustment, route_of)

    items = _registered_moves(flow, "mf-inc")
    found = None
    for move in (i for i in items if i.kind == "mobility"):
        route = route_of(move)
        planned = next((o for o in route["options"] if o["id"] == route["planned"]), None)
        stations = [u for u in (planned or {}).get("uses", []) if not u.startswith("버스:") and ":" in u]
        if len(stations) >= 2:
            found = (move, route, planned, stations)
            break
    assert found, "지하철 경로가 한 구간은 있어야 한다"
    move, route, planned, stations = found
    blocked = stations[len(stations) // 2]                                   # 가운데 역 - 환승역이거나 지나는 역
    only_planned = {**route, "options": [planned]}                            # 대안이 하나뿐이라 막히면 저장된 후보가 모두 막힌다
    events = {blocked: {"effect": "skip_station", "summary": f"{blocked} 무정차"}}
    plan = plan_route_adjustment(item=move, following=next_after(items, move), route=only_planned, events=events,
                                 now=move.starts_at - timedelta(minutes=30), previous=place_before(items, move))
    assert isinstance(plan, ItineraryChange), (blocked, plan)
    assert plan.summary["rerouted_by"] == "mobility_engine"
    new = next(iter(plan.replacements.values()))
    new_route = new.detail["route_def"]
    new_planned = next(o for o in new_route["options"] if o["id"] == new_route["planned"])
    assert blocked not in new_planned["uses"], "막힌 역을 다시 지나가면 안 된다"
    assert new.detail["planner"]["transfer_basis"] == "시간표 판정(이동 계산기)"


def test_the_mobility_team_answers_a_structured_route_question_on_the_real_timetable(flow):
    """이동 에이전트(MobilityTeam)가 구조화 입력(current_state.mobility)을 받으면 실제 시간표로 답한다(#34·#35)."""
    import asyncio

    from app.modules.travel_ops.mobility.team import MobilityTeam
    from tests.unit.travel.helpers import FakeTools, pack, task

    allowed = list(MobilityTeam.manifest.allowed_tools)
    state = {"mobility": {"date": "2026-10-07", "depart_at": "10:00",
                          "legs": [{"line": "02호선", "from": "을지로입구", "to": "성수"}]}}
    tools = FakeTools({})
    result = asyncio.run(MobilityTeam(tools).execute(
        task("mobility", "mobility.check_route", pack("mobility", state=state), allowed, input_text="을지로입구에서 성수 가는 길")))
    assert result.outcome == "completed", (result.outcome, result.answer, result.failure_code)
    assert result.answer and result.evidence and all(e.observed_at is not None for e in result.evidence)
    assert tools.calls == [], "조회 도구(read.route - 비어 있음)를 거치지 않고 계산기로 답한다"
    # 계산기가 꺼져 있으면 지어낸 답이 아니라 오류로 올린다 - 같은 입력, 켜져 있을 때와 다른 결과
    from app.modules.travel_ops.mobility import wiring
    saved = dict(wiring._STATE)
    try:
        wiring._STATE["mode"] = "disabled"
        off = asyncio.run(MobilityTeam(FakeTools({})).execute(
            task("mobility", "mobility.check_route", pack("mobility", state=state), allowed, input_text="을지로입구에서 성수 가는 길")))
        assert off.outcome == "escalated" and off.failure_code == "mobility_engine_disabled"
    finally:
        wiring._STATE.clear()
        wiring._STATE.update(saved)
