# -*- coding: utf-8 -*-
"""확정 시나리오를 **HTTP 로** 흘린다 — 등록 · 감시 · 신고 · 재요청 · 계획서 링크.

★`tests/scenario/test_confirmed_scenario.py` 는 도메인 함수를 직접 부른다. 이 파일은
  같은 하루를 **제품 입구**(`/v1/trips/*` · `/plan/*`)로 통과시킨다. 감시 루프만 직접
  돌린다 — 스위퍼는 시계로 도는 일이라 시험에서는 재생 시계로 한 틱씩 부른다.

★경로 정의를 밖에서 주지 않는다(`routes=None`). 등록 API 가 이동 항목에 넣은
  `route_def` 만으로 이동-B1·A6 이 돌아야 한다 — 스위퍼가 실제로 그렇게 돈다.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.infrastructure.travel.base import TravelSources
from app.infrastructure.travel.disruptions import DisruptionCheck
from app.infrastructure.travel.replay import (ReplayAir, ReplayRouteEvents, ReplayTimeline,
                                              ReplayWarning, ReplayWeather)
from app.modules.travel_ops.itinerary import TripStore
from app.modules.travel_ops.trip_api import build_trip_router, plan_token
from app.modules.travel_ops.trip_watch import TripWatcher
from app.presentation import security
from app.presentation.api.app import create_app

KST = ZoneInfo("Asia/Seoul")
SCENARIO = json.loads((Path(__file__).resolve().parents[2] / "app" / "modules" / "travel_ops"
                       / "scenarios" / "seoul_day_taiwan_friends.json").read_text(encoding="utf-8"))
DAY = SCENARIO["trip"]["date"]
REPORTS = {report["type"]: report for report in SCENARIO["customer_reports"]}


def _iso(hhmm: str) -> str:
    return f"{DAY}T{hhmm}:00+09:00"


def _at(hhmm: str) -> datetime:
    return datetime.fromisoformat(_iso(hhmm))


class Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


def _body(customer, request_id="create-1", **override):
    trip = SCENARIO["trip"]
    body = {
        "request_id": request_id, "customer_id": str(customer), "title": trip["title"],
        "locale": trip["locale"], "party_size": trip["party_size"],
        "constraints": trip["constraints"],
        "places": [{k: p[k] for k in ("key", "name", "kind", "lat", "lon", "weather_sensitive",
                                      "attributes")} for p in SCENARIO["places"]],
        "items": [{"seq": it["seq"], "kind": it["kind"], "title": it["title"],
                   "place": it.get("place"), "route": it.get("route"),
                   "starts_at": _iso(it["start"]), "ends_at": _iso(it["end"]),
                   "detail": it.get("detail", {})} for it in SCENARIO["items"]],
        "routes": SCENARIO["routes"],
    }
    body.update(override)
    return body


@pytest.fixture()
def api(monkeypatch):
    original = settings_module.get_settings()
    tenant = "trip_api_" + uuid4().hex[:12]
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)
    customer = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "trip api"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)",
                    (customer, tenant, "taiwan-friends"))

    clock = Clock(_at("08:00"))
    timeline = ReplayTimeline(SCENARIO["timeline"], clock)
    check = DisruptionCheck(TravelSources(weather=ReplayWeather(timeline),
                                          warning=ReplayWarning(timeline),
                                          air=ReplayAir(timeline)),
                            limits=lambda: (60, 30)).check
    store = TripStore(tenant)
    watcher = TripWatcher(store=store, check=check, connection_factory=get_connection,
                          clock=clock, routes=None, route_events=ReplayRouteEvents(timeline))
    # ★`[2026-10-02 결함 인계 #2]` 제안 고르기는 그 일정이 **끝났으면** 못 고른다(`pending.choose`) — 대본 날짜는 지난 날이라 실시간으로 보면 전부 끝난 것이 된다. 시계를 대본의 것으로
    from app.modules.travel_ops import pending as pending_module

    monkeypatch.setattr(pending_module, "wall_clock", lambda: clock.now)

    def classifier(_message):
        return {"intent": "other", "issue_code": "other", "sentiment": "neutral"}

    def trip_classifier(message):
        # ★분류기 흉내 — 실제 제공자(Gemma 4)는 라이브 확인에서 본다
        if "모르는" in message:
            return {"intent": "other", "issue_code": "other", "sentiment": "neutral"}
        code = "dining_hours" if ("늦" in message or "휴무" in message) else "activity_other"
        return {"intent": "incident_report", "issue_code": code, "sentiment": "negative"}

    class ScenarioChat:
        """추출기 흉내 — 시나리오 세 문장에 모델이 낼 법한 값을 준다."""

        def json(self, system, message):
            if "늦을" in message:
                return {"type": "delay", "minutes": 70, "products": []}
            if "휴무" in message:
                return {"type": "closed", "minutes": None, "products": []}
            if "품절" in message:
                return {"type": "stock_out", "products": ["라면 선물세트", "스팸 선물세트"]}
            if "되돌려" in message:
                import re
                numbers = re.findall(r"\d+", message)
                return {"type": "rollback", "to_version": int(numbers[0]) if numbers else None}
            return {"type": "other"}

    client = TestClient(create_app(classifier=classifier, domain_routers=[build_trip_router(
        check_factory=lambda: check, classifier_factory=lambda: trip_classifier,
        chat_factory=ScenarioChat)]))

    def auth(scope):
        return {"Authorization": "Bearer " + security._development_key(scope, original.secret_key)}

    def tick(hhmm):
        clock.now = _at(hhmm)
        return watcher.tick()

    def notices():
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s "
                        "AND topic='trip.notice' ORDER BY available_at, dedupe_key", (tenant,))
            return cur.fetchall()

    yield {"client": client, "auth": auth, "tenant": tenant, "customer": customer,
           "tick": tick, "notices": notices, "store": store}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        # ★자유 문장 경로가 Case 를 만든다 — FK 순서대로 먼저 지운다
        cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM web_user_keys WHERE tenant_id=%s", (tenant,))     # 웹 사용자 키(025)
        for table in ("web_sessions", "web_social_links"):                          # 쿠키 세션(044) · 소셜 계정(043) — 사용자 행을 가리킨다
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))
        for table in ("web_usage", "runtime_limits", "runtime_limit_state"):   # 웹 남용 방어(031)
            cur.execute(f"DELETE FROM {table} WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM trip_intakes WHERE tenant_id=%s", (tenant,))     # 계획 읽기(028, 원본·값은 따라 지워진다)
        cur.execute("DELETE FROM place_aliases WHERE tenant_id=%s", (tenant,))    # 고객이 고친 장소 별칭(030)
        for sql in ("DELETE FROM outbox WHERE tenant_id=%s", "DELETE FROM trips WHERE tenant_id=%s",
                    "DELETE FROM places WHERE tenant_id=%s", "DELETE FROM customers WHERE tenant_id=%s",
                    "DELETE FROM tenants WHERE tenant_id=%s"):
            cur.execute(sql, (tenant,))


def _create(api, **override):
    response = api["client"].post("/v1/trips", json=_body(api["customer"], **override),
                                  headers=api["auth"]("trip:write"))
    assert response.status_code == 201, response.text
    return response.json()


def _report(api, trip_id, kind, request_id=None):
    report = REPORTS[kind]
    body = {"request_id": request_id or f"report-{kind}", "type": kind,
            "message": report["message"], "at": _iso(report["at"])}
    if "minutes" in report:
        body["minutes"] = report["minutes"]
    if "products" in report:
        body["products"] = report["products"]
    return api["client"].post(f"/v1/trips/{trip_id}/reports", json=body,
                              headers=api["auth"]("trip:write"))


def _slot(view, seq):
    return next(item for item in view["items"] if item["seq"] == seq)


def _detail(api, trip_id):
    response = api["client"].get(f"/v1/trips/{trip_id}", headers=api["auth"]("trip:read"))
    assert response.status_code == 200, response.text
    return response.json()


# ── 등록 ───────────────────────────────────────────────────────
def test_create_is_idempotent_and_the_first_notice_carries_the_plan_link(api):
    first = _create(api)
    again = _create(api)
    assert first["created"] is True and again["created"] is False
    assert first["trip_id"] == again["trip_id"] and first["version"] == 1
    assert len(first["items"]) == len(SCENARIO["items"])

    [(key, payload)] = api["notices"]()                       # ★두 번 받아도 통지는 하나
    assert key.endswith(":v1") and payload["plan_url"] == first["plan_url"]
    assert first["plan_url"] in payload["text"]

    reused = api["client"].post("/v1/trips", json=_body(api["customer"], title="다른 여행"),
                                headers=api["auth"]("trip:write"))
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "idempotency_key_reused"


@pytest.mark.parametrize("preference", [{"level": "normal"}, {"target_density": 0.6}])
def test_density_warning_survives_registration_duplicate_and_read(api, preference):
    body = _body(api["customer"])
    body["items"] = [{"seq": 1, "kind": "activity", "title": "긴 방문",
                      "starts_at": f"{DAY}T10:00:00+09:00", "ends_at": f"{DAY}T18:00:00+09:00"}]
    body["constraints"] = {"density": {**preference, "days": {DAY: {
        "starts_at": f"{DAY}T10:00:00+09:00", "ends_at": f"{DAY}T22:00:00+09:00", "buffer_minutes": 0}}}}
    first = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert first.status_code == 201, first.text
    view = first.json()
    assert view["warnings"][0]["code"] == "density_exceeded"
    assert view["density"][0]["policy_basis"] == ("research_calibrated" if "level" in preference else "user_preference")
    assert view["density"][0]["breakdown"]["scheduled_minutes"] == 480
    again = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write")).json()
    assert again["created"] is False and again["density"] == view["density"]
    assert _detail(api, view["trip_id"])["density"] == view["density"]


# invariant: INV-CS-ACT-008
def test_quality_warnings_ride_along_with_an_accepted_registration(api):
    """`[2026-10-03]` 같은 곳 두 번 · 점심 빠짐 · 왔다 갔다는 **거절이 아니라 경고**다 — 등록은 받고(201), 응답과 조회의 「살펴볼 점」(`warnings`)에 실린다.
    체크리스트 v2 T7·T8·T9 — 외부 에이전트가 만든 일정(등록 길)은 이것들을 아무도 말해 주지 않았다."""
    body = _body(api["customer"])
    spot = lambda key, name, lat, lon: {"key": key, "name": name, "kind": "activity", "lat": lat, "lon": lon,  # noqa: E731
                                        "weather_sensitive": False, "attributes": {}}
    body["places"] = [spot("palace", "테스트궁", 37.5796, 126.9770), spot("museum", "테스트박물관", 37.5300, 127.0000)]
    body["constraints"] = {}
    body["routes"] = {}
    body["items"] = [{"seq": 1, "kind": "activity", "title": "궁 구경", "place": "palace", "route": None,
                      "starts_at": _iso("10:00"), "ends_at": _iso("11:00"), "detail": {}},
                     {"seq": 2, "kind": "activity", "title": "박물관", "place": "museum", "route": None,
                      "starts_at": _iso("12:00"), "ends_at": _iso("13:30"), "detail": {}},      # 점심 창(11:30~14:00)을 틈 30분만 두고 채운다
                     {"seq": 3, "kind": "activity", "title": "궁 다시", "place": "palace", "route": None,
                      "starts_at": _iso("15:00"), "ends_at": _iso("16:00"), "detail": {}}]
    created = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert created.status_code == 201, created.text
    view = created.json()
    found = {w["code"]: w for w in view["warnings"]}
    assert {"same_place_twice", "meal_missing", "route_zigzag"} <= set(found)
    assert found["same_place_twice"]["items"] == [1, 3] and found["meal_missing"]["date"] == DAY
    assert all(w["reason"] and w["remedy"] for w in view["warnings"])
    assert {w["code"] for w in _detail(api, view["trip_id"])["warnings"]} == set(found)       # 조회도 같은 목록


def test_a_second_trip_reuses_known_places_without_overwriting_them(api):
    """☆2026-09-14 개발 서버에서 발견 — 같은 테넌트의 두 번째 여행이 이미 있는 장소를
    적자 UNIQUE(tenant_id, name, kind) 로 500 이 났다. 여행마다 테넌트를 새로 만드는
    시험은 이것을 못 잡았다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET attributes='{}'::jsonb WHERE tenant_id=%s", (api["tenant"],))
    first = _create(api)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET attributes = attributes || '{\"district\": \"카탈로그값\"}' "
                    "WHERE tenant_id=%s AND name='경복궁'", (api["tenant"],))
    second = _create(api, request_id="create-2")
    assert second["created"] is True and second["trip_id"] != first["trip_id"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM places WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == len(SCENARIO["places"])          # ★새로 안 늘었다
        cur.execute("SELECT attributes FROM places WHERE tenant_id=%s AND name='경복궁'",
                    (api["tenant"],))
        attributes = cur.fetchone()[0]
    assert attributes["district"] == "카탈로그값"                     # ★있던 값은 그대로
    submitted = next(p for p in SCENARIO["places"] if p["name"] == "경복궁")["attributes"]
    assert set(submitted) <= set(attributes)                          # 빈 칸은 채웠다


def test_places_from_outside_services_stay_with_their_own_trip(api):
    """★`[2026-09-27]` 관광공사·카카오에서 받은 장소는 공용 표에 쌓아 다른 고객에게 재사용하지 않는다
    (콘텐츠랩 「로컬서버 저장 금지」 · 카카오 운영정책 제5조 — 마이그레이션 029). 그 여행 전용 행이 되고,
    그 여행의 감시·대체 일정에서는 보이고, 공용 목록·다른 여행에서는 안 보인다."""
    from app.modules.travel_ops.itinerary import TripStore
    from app.modules.travel_ops.planner import load_candidates

    outside = {"key": "market", "name": "광장시장", "kind": "activity", "lat": 37.5700, "lon": 126.9996,
               "weather_sensitive": False,
               "attributes": {"source": "tour_api", "source_content_id": "264570", "district": "종로구"}}

    def body(request_id):
        base = _body(api["customer"], request_id=request_id)
        base["places"].append(outside)
        last = max(it["seq"] for it in base["items"])
        base["items"].append({"seq": last + 1, "kind": "activity", "title": "광장시장", "place": "market",
                              "starts_at": _iso("21:00"), "ends_at": _iso("21:40"), "detail": {}})
        return base

    trips = []
    for request_id in ("outside-1", "outside-2"):
        response = api["client"].post("/v1/trips", json=body(request_id), headers=api["auth"]("trip:write"))
        assert response.status_code == 201, response.text
        trips.append(response.json()["trip_id"])
    store = TripStore(api["tenant"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT trip_scope::text FROM places WHERE tenant_id=%s AND name='광장시장' "
                    "ORDER BY trip_scope", (api["tenant"],))
        assert sorted(r[0] for r in cur.fetchall()) == sorted(trips)   # ★여행마다 따로 — 재사용하지 않는다
        shared = [p["name"] for p in store.places(conn)]
        mine = [p["name"] for p in store.places(conn, UUID(trips[0]))]
        every = store.places(conn, every_trip=True)
        _, items = store.latest(conn, UUID(trips[0]))
        candidates = load_candidates(conn, tenant_id=api["tenant"], kinds=("activity",))
    assert "광장시장" not in shared and mine.count("광장시장") == 1
    assert len([p for p in every if p["name"] == "광장시장"]) == 2
    market = next(item for item in items if item.title == "광장시장")
    assert market.place is not None and market.place["latitude"] == 37.57        # ★감시가 좌표를 본다
    assert all(c.name != "광장시장" for c in candidates)                         # ★생성기 후보에도 없다
    # 공용 장소는 전처럼 하나를 같이 쓴다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM places WHERE tenant_id=%s AND trip_scope IS NULL", (api["tenant"],))
        assert cur.fetchone()[0] == len(SCENARIO["places"])


def test_create_rejects_unknown_references_and_needs_the_write_scope(api):
    bad = _body(api["customer"])
    bad["items"][1]["place"] = "no_such_place"
    response = api["client"].post("/v1/trips", json=bad, headers=api["auth"]("trip:write"))
    assert response.status_code == 422 and response.json()["error"]["code"] == "unknown_place"
    denied = api["client"].post("/v1/trips", json=_body(api["customer"]),
                                headers=api["auth"]("trip:read"))
    assert denied.status_code == 403


# ── 하루 전체 ──────────────────────────────────────────────────
def test_every_item_says_what_kind_it_is_and_which_meal(api):
    """☆`[2026-10-01 사용자 지적]` 화면이 「개화」만 보고는 식당인지 활동인지 알 수 없었다 — 종류의 사람 말과 끼니를 서버가 준다.
    끼니는 시작 시각(KST)으로 센다 — 10시 전 아침 · 16시 전 점심 · 그 뒤 저녁. 식사가 아니면 None."""
    view = _detail(api, _create(api)["trip_id"])
    by_kind = {}
    for item in view["items"]:
        by_kind.setdefault(item["kind"], []).append(item)
    assert {i["kind_label"] for i in by_kind["dining"]} == {"식사"}
    assert {i["kind_label"] for i in by_kind["activity"]} == {"활동"}
    assert {i["kind_label"] for i in by_kind["mobility"]} == {"이동"}
    assert [i["meal"] for i in by_kind["dining"]] == ["아침", "점심", "저녁"]          # 09:00 · 13:00 · 18:00
    assert all(i["meal"] is None for kind in ("activity", "mobility") for i in by_kind[kind])


def test_the_whole_day_through_the_api(api):
    trip_id = _create(api)["trip_id"]
    assert len(api["tick"]("09:00").adjusted) == 1                               # 액-02
    assert len(api["tick"]("10:45").adjusted) == 1                               # 이동-B1 (route_def)
    p3 = _report(api, trip_id, "delay")
    assert p3.status_code == 200 and p3.json()["to"] == "성수 브런치 식당(시나리오)"  # 요식-P3
    assert api["tick"]("14:50").adjusted == []
    assert len(api["tick"]("17:10").adjusted) == 1                               # 이동-A6
    p7 = _report(api, trip_id, "closed")
    assert p7.json()["to"] == "서울역 한식당(시나리오)"                               # 요식-P7
    a8 = _report(api, trip_id, "stock_out").json()
    assert a8["status"] == "answered" and "[미확인]" in a8["text"]                   # 액-08

    view = _detail(api, trip_id)
    assert view["version"] == 6
    assert [h["reason"] for h in view["history"]] == [
        "created", "auto_adjusted", "auto_adjusted", "customer_report", "auto_adjusted",
        "customer_report"]
    assert len(api["notices"]()) == 1 + 5                                        # 생성 + 변경 다섯
    assert _slot(view, 2)["place"] == "아쿠아리움" and _slot(view, 2)["changed"]
    assert _slot(view, 3)["other_options"][0]["name"].startswith("뚝섬역")

    # ★재시도 — 같은 신고를 다시 받아도 일정을 또 밀지 않는다
    again = _report(api, trip_id, "delay")
    assert again.json() == {"status": "duplicate", "version": 4}
    assert _detail(api, trip_id)["version"] == 6


# ── 재요청 ─────────────────────────────────────────────────────
def test_swap_to_the_other_option_and_back(api):
    trip_id = _create(api)["trip_id"]
    _report(api, trip_id, "delay")
    view = _detail(api, trip_id)
    lunch = _slot(view, 5)
    assert lunch["place"] == "성수 브런치 식당(시나리오)"
    [other] = lunch["other_options"]
    assert other["name"] == "성수 국수 식당(시나리오)"

    swapped = api["client"].post(
        f"/v1/trips/{trip_id}/items/{lunch['item_id']}/alternate",
        json={"request_id": "swap-1", "base_version": 2, "choice": other["key"]},
        headers=api["auth"]("trip:write"))
    assert swapped.status_code == 200, swapped.text
    assert swapped.json()["version"] == 3
    after = _slot(_detail(api, trip_id), 5)
    assert after["place"] == "성수 국수 식당(시나리오)"
    assert [o["name"] for o in after["other_options"]] == ["성수 브런치 식당(시나리오)"]  # ★되돌아갈 수 있다
    assert "요청하신 대로" in api["notices"]()[-1][1]["text"]

    # ★고객이 본 버전이 낡았으면 얹지 않는다
    stale = api["client"].post(
        f"/v1/trips/{trip_id}/items/{after['item_id']}/alternate",
        json={"request_id": "swap-2", "base_version": 2}, headers=api["auth"]("trip:write"))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_itinerary"
    assert stale.json()["error"]["version"] == 3


def test_rollback_restores_and_the_watcher_leaves_it_alone(api):
    trip_id = _create(api)["trip_id"]
    api["tick"]("09:00")                                               # 스카이 데크 → 아쿠아리움 (v2)
    back = api["client"].post(f"/v1/trips/{trip_id}/rollback",
                              json={"request_id": "rb-1", "base_version": 2, "to_version": 1,
                                    "message": "그래도 전망대에 갈래요"},
                              headers=api["auth"]("trip:write"))
    assert back.status_code == 200, back.text
    assert back.json()["version"] == 3
    view = _detail(api, trip_id)
    sky = _slot(view, 2)
    assert sky["place"] == "잠실 스카이타워" and sky["customer_pinned"] is True
    assert view["history"][-1]["reason"] == "rollback"

    again = api["tick"]("09:10")                                       # ★다시 자동으로 바꾸지 않는다
    assert again.adjusted == [] and len(again.pinned) == 1
    assert _detail(api, trip_id)["version"] == 3

    invalid = api["client"].post(f"/v1/trips/{trip_id}/rollback",
                                 json={"request_id": "rb-2", "base_version": 3, "to_version": 3},
                                 headers=api["auth"]("trip:write"))
    assert invalid.status_code == 409 and invalid.json()["error"]["code"] == "invalid_version"


# ── 고객 자유 문장 ─────────────────────────────────────────────
def _say(api, trip_id, kind, request_id=None, text=None):
    report = REPORTS.get(kind, {})
    return api["client"].post(f"/v1/trips/{trip_id}/messages", headers=api["auth"]("trip:write"),
                              json={"request_id": request_id or f"say-{kind}",
                                    "message": text or report["message"],
                                    "at": _iso(report.get("at", "13:00"))})


def _case_events(case_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY aggregate_version",
                    (case_id,))
        return [r[0] for r in cur.fetchall()]


def test_the_three_customer_sentences_go_case_classify_desk_and_close(api):
    """★구조화 신고와 **같은 결과**여야 한다 — 요식-P3 · 요식-P7 · 액-08."""
    trip_id = _create(api)["trip_id"]
    delay = _say(api, trip_id, "delay").json()
    assert delay["status"] == "adjusted" and delay["outcome"]["to"] == "성수 브런치 식당(시나리오)"
    assert delay["case_status"] == "resolved"
    assert delay["classification"]["issue_code"] == "dining_hours"
    assert _case_events(delay["case_id"]) == ["created", "classified", "routed", "completed"]

    closed = _say(api, trip_id, "closed").json()
    assert closed["outcome"]["to"] == "서울역 한식당(시나리오)" and closed["case_status"] == "resolved"

    stock = _say(api, trip_id, "stock_out").json()
    assert stock["status"] == "answered" and "[미확인]" in stock["outcome"]["text"]
    assert stock["report"]["products"] == ["라면 선물세트", "스팸 선물세트"]
    assert _detail(api, trip_id)["version"] == 3             # 생성 + 요식 둘


def test_a_repeated_message_does_not_open_a_second_case(api):
    trip_id = _create(api)["trip_id"]
    first = _say(api, trip_id, "delay").json()
    again = _say(api, trip_id, "delay").json()
    assert again["status"] == "duplicate" and again["case_id"] == first["case_id"]
    assert _detail(api, trip_id)["version"] == 2


def test_a_sentence_the_desk_cannot_use_is_escalated_not_guessed(api):
    trip_id = _create(api)["trip_id"]
    result = _say(api, trip_id, "other", request_id="say-x", text="그냥 궁금한 게 있어요").json()
    assert result["status"] == "escalated" and result["case_status"] == "escalated"
    assert _detail(api, trip_id)["version"] == 1             # ★일정은 그대로


# ── 계획서 링크 ────────────────────────────────────────────────
def test_the_plan_link_always_shows_the_latest_version(api):
    created = _create(api)
    trip_id = created["trip_id"]
    url = created["plan_url"].split("://", 1)[1].split("/", 1)[1]          # 경로 + 토큰만
    page = api["client"].get("/" + url)
    assert page.status_code == 200 and "일정 버전 1" in page.text

    api["tick"]("09:00")
    page = api["client"].get("/" + url)
    assert "일정 버전 2" in page.text and "아쿠아리움" in page.text and "변경됨" in page.text
    as_json = api["client"].get("/" + url + "&format=json").json()
    assert as_json["version"] == 2 and "customer_id" not in as_json

    wrong = api["client"].get(f"/plan/{trip_id}?t={'0' * 32}")
    assert wrong.status_code == 404
    other = api["client"].get(f"/plan/{uuid4()}?t={plan_token(api['tenant'], trip_id)}")
    assert other.status_code == 404                                    # ★다른 여행 토큰으로 못 연다


# ── 받을 때 판정 (2026-09-21, v11 DoD-2·3) ──────────────────────
def test_an_impossible_itinerary_is_refused_with_reasons_and_remedies(api):
    """★거절은 이유와 **완화 조건**을 같이 낸다. 받아 두고 나중에 고치지 않는다."""
    body = _body(api["customer"], request_id="bad-1")
    lunch = next(it for it in body["items"] if it["seq"] == 5)
    lunch["starts_at"] = _iso("12:30")                 # 앞 쇼핑(11:15~13:00)과 겹친다
    move = next(it for it in body["items"] if it["seq"] == 6)
    move["ends_at"] = _iso("15:05")                    # 20분 걸리는 경로를 5분으로 잡는다
    response = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "itinerary_infeasible"
    codes = {v["code"] for v in error["violations"]}
    assert codes == {"overlap", "move_too_short"}, error["violations"]
    assert all(v["reason"] and v["remedy"] for v in error["violations"])

    # ★일정은 저장되지 않았다 — 거절은 아무것도 남기지 않는다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trips WHERE tenant_id=%s", (api["tenant"],))
        assert cur.fetchone()[0] == 0


def test_the_confirmed_day_is_accepted_as_submitted(api):
    """판정이 운영을 막으면 안 된다 — 확정 시나리오 하루는 그대로 201."""
    assert _create(api, request_id="ok-1")["version"] == 1


def test_a_plan_link_opens_for_a_trip_in_another_tenant(api):
    """★시나리오 모드처럼 **다른 테넌트**의 여행도 링크로 열린다 — 통지에 실린 링크가 404 였다."""
    from app.modules.travel_ops.itinerary import Item, TripStore
    from app.modules.travel_ops.trip_api import plan_token

    other = "planlink_" + uuid4().hex[:10]
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (other, "plan link"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (other, "someone"))
            customer = cur.fetchone()[0]
        store = TripStore(other)
        with conn.transaction():
            trip_id, _ = store.create_trip(conn, customer_id=customer, title="다른 테넌트 여행",
                                           locale="ko", party_size=2,
                                           items=[Item(item_id=uuid4(), seq=1, kind="activity",
                                                       title="첫 일정", place_id=None,
                                                       starts_at=_at("09:00"), ends_at=_at("10:00"))],
                                           constraints={})
    try:
        page = api["client"].get(f"/plan/{trip_id}?t={plan_token(other, trip_id)}")
        assert page.status_code == 200 and "다른 테넌트 여행" in page.text
        wrong = api["client"].get(f"/plan/{trip_id}?t={plan_token(api['tenant'], trip_id)}")
        assert wrong.status_code == 404          # ★다른 테넌트 이름으로 만든 토큰은 안 통한다
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM itinerary_items WHERE tenant_id=%s", (other,))
            cur.execute("DELETE FROM itinerary_versions WHERE tenant_id=%s", (other,))
            cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (other,))
            cur.execute("DELETE FROM trips WHERE tenant_id=%s", (other,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (other,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (other,))


def test_a_question_shaped_closed_report_does_not_change_the_plan(api):
    """★`[2026-09-25]` 묻는 꼴이면 「닫혔다」로 받지 않는다 — 모델이 closed 로 뽑아도 질문이고,
    일정은 바꾸지 않는다. 전에는 대체안 계산으로 갈 수 있었다.
    ★`[2026-09-28]` 전에는 답 없이 escalated 로 끝났다 — 이제 **짚은 일정의 사실로 답하고**, 규정을 찾아볼 수
    없으면(이 앱은 규정 검색을 안 물렸다) 그렇다고 같이 말한다(`trip_replies.question_reply`)."""
    trip_id = _create(api)["trip_id"]
    said = _say(api, trip_id, "closed", request_id="say-q", text="오늘 저녁 식당 휴무 아니에요?").json()
    assert said["status"] == "answered" and said["reason"] == "question_answered", said
    assert said["report"] == {"type": "question"}
    assert "저녁" in said["answer"] and "규정을 찾아볼 수 없어서" in said["answer"], said["answer"]
    assert _detail(api, trip_id)["version"] == 1



def test_a_rollback_sentence_rolls_back_instead_of_swapping(api):
    """★`[2026-09-26]` 대화로 보낸 「N번 일정으로 되돌려 주세요」 — 전에는 분기가 delay·closed·stock_out·그 밖뿐이라
    그 밖(= 다른 안으로 바꾸기)으로 떨어졌다(triPilot : RAG 세션이 코드를 읽고 찾았다). 옛 버전으로 돌아가야 한다."""
    trip_id = _create(api)["trip_id"]
    assert len(api["tick"]("09:00").adjusted) == 1                   # v2 — 감시가 바꿨다
    before = [(s["seq"], s["place"]) for s in _detail(api, trip_id)["items"]]
    said = _say(api, trip_id, "rollback", request_id="say-back", text="1번 일정으로 되돌려 주세요").json()
    assert said["status"] == "rolled_back", said
    view = _detail(api, trip_id)
    assert view["version"] == 3 and view["history"][-1]["reason"] == "rollback"
    with get_connection() as conn:
        v1 = api["store"].items(conn, trip_id, 1)
    assert [(s["seq"], s["place"]) for s in view["items"]] == [(i.seq, (i.place or {}).get("name")) for i in v1]
    assert [(s["seq"], s["place"]) for s in view["items"]] != before


def test_a_rollback_without_a_number_undoes_the_latest_change(api):
    """`[2026-09-29 사용자 지적 · ui 세션 전달]` 「원래대로 되돌려」 · 「○○ 이전 식당으로 되돌려」 — 번호가 없으면 서버가
    그 항목(또는 가장 최근)의 변경 직전으로 정한다. 전에는 「알아듣지 못했어요」로 끝났다."""
    trip_id = _create(api)["trip_id"]
    assert len(api["tick"]("09:00").adjusted) == 1                   # v2 — 감시가 바꿨다
    said = _say(api, trip_id, "rollback", request_id="say-back-0", text="원래대로 되돌려 주세요").json()
    assert said["status"] == "rolled_back", said
    view = _detail(api, trip_id)
    with get_connection() as conn:
        v1 = api["store"].items(conn, trip_id, 1)
    assert view["version"] == 3
    assert [(s["seq"], s["place"]) for s in view["items"]] == [(i.seq, (i.place or {}).get("name")) for i in v1]


def test_a_rollback_of_an_unchanged_item_says_so_instead_of_undoing_something_else(api):
    trip_id = _create(api)["trip_id"]
    assert len(api["tick"]("09:00").adjusted) == 1
    first = _detail(api, trip_id)["items"][0]["place"]
    said = _say(api, trip_id, "rollback", request_id="say-back-1", text=f"{first} 되돌려 주세요").json()
    assert said["status"] == "ask_rollback" and "되돌릴 변경이 없어요" in said["answer"], said
    assert _detail(api, trip_id)["version"] == 2                      # 아무것도 되돌리지 않았다


def test_places_of_an_ended_trip_lose_outside_values_but_keep_their_name(api):
    """★`[2026-09-28]` 끝난 여행의 전용 장소 행(029)은 좌표·외부 식별자를 비운다(`trip_places.scrub_ended`).
    끝나기 전 · 공용 행은 그대로다. 다시 돌려도 같은 행을 두 번 비우지 않는다."""
    from datetime import timedelta

    from app.modules.travel_ops.trip_places import scrub_ended

    body = _body(api["customer"], request_id="scrub-1")
    body["places"].append({"key": "market", "name": "광장시장", "kind": "activity", "lat": 37.57, "lon": 126.9996,
                           "weather_sensitive": False,
                           "attributes": {"source": "tour_api", "source_content_id": "264570"}})
    last = max(it["seq"] for it in body["items"])
    body["items"].append({"seq": last + 1, "kind": "activity", "title": "광장시장", "place": "market",
                          "starts_at": _iso("21:00"), "ends_at": _iso("21:40"), "detail": {}})
    trip = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write")).json()
    ended = _at("21:40")
    with get_connection() as conn:
        early = scrub_ended(conn, tenant_id=api["tenant"], now=ended + timedelta(hours=1), retention_hours=24)
        late = scrub_ended(conn, tenant_id=api["tenant"], now=ended + timedelta(hours=25), retention_hours=24)
        again = scrub_ended(conn, tenant_id=api["tenant"], now=ended + timedelta(hours=26), retention_hours=24)
        with conn.cursor() as cur:
            cur.execute("SELECT name, latitude, longitude, attributes FROM places WHERE tenant_id=%s AND trip_scope=%s",
                        (api["tenant"], trip["trip_id"]))
            name, lat, lon, attributes = cur.fetchone()
            cur.execute("SELECT count(*) FROM places WHERE tenant_id=%s AND trip_scope IS NULL AND latitude IS NULL",
                        (api["tenant"],))
            shared_blanked = cur.fetchone()[0]
    assert (early["scrubbed"], late["scrubbed"], again["scrubbed"]) == (0, 1, 0)
    assert name == "광장시장" and lat is None and lon is None
    assert set(attributes) == {"source", "scrubbed_at"} and "source_content_id" not in attributes
    assert shared_blanked == 0                                             # ★공용 행은 그대로
