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
from uuid import uuid4
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


def test_create_rejects_unknown_references_and_needs_the_write_scope(api):
    bad = _body(api["customer"])
    bad["items"][1]["place"] = "no_such_place"
    response = api["client"].post("/v1/trips", json=bad, headers=api["auth"]("trip:write"))
    assert response.status_code == 422 and response.json()["error"]["code"] == "unknown_place"
    denied = api["client"].post("/v1/trips", json=_body(api["customer"]),
                                headers=api["auth"]("trip:read"))
    assert denied.status_code == 403


# ── 하루 전체 ──────────────────────────────────────────────────
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
