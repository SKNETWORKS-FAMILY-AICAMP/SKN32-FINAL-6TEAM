# -*- coding: utf-8 -*-
"""계획 읽기가 읽은 성향 · 조건이 **등록된 여행의 담당 열쇠**까지 가나 — 접수 → 확인 화면 → 등록. `[2026-10-16 D-025 후속]`

☆왜: 이해 에이전트가 「웬만하면 택시」 · 「천천히」 · 「비 오면 실내」 · 「9시까지 숙소」 · 「맛집 위주」를 읽어도 등록된 여행의 설문 열쇠는 비어 있었다 —
  이동 판정 · 일정 짜기 · 식당 고르기 · 활동 대안은 그 값을 하나도 못 봤다(값은 `reading.agent` 값 줄에만 있었다).

★지키려는 것
 ①확인 화면(`check.handoff`)에 무엇을 누구에게 넘기는지가 원문 조각과 함께 온다 — 「우리가 채움」(filled)
 ②등록된 여행의 `constraints` 에 담당이 읽는 열쇠가 채워지고 `filled_by_reading` 에 기록이 남는다 · 「직접 답한 문항」에는 안 들어간다
 ③고객이 로딩 중 질문에 직접 답한 이동 수단은 읽은 값이 덮지 않는다(확인 화면에도 「고객 답 먼저」)

모델은 시험이 정한 답을 내는 대역이다(`structured` 하나) — 모델 품질이 아니라 **넘기는 길**을 본다.

재현:

    python -m pytest tests/e2e/test_intake_reading_prefs.py -v
"""
from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.intake import agent_read, pipeline
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.entry.trip_api import build_trip_router
from app.infrastructure.db.session import get_connection
from app.presentation.api.app import create_app

from .test_intake_review import Kakao, Tour, _key, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_15 = reldate.day("2026-10-15")

PLAN = (f"{D_2026_10_15}\n"
        "10시 경복궁\n"
        "13:30 광장시장\n"
        "웬만하면 택시로 다니고 천천히 다닐래요. 비 오면 실내로 가고 9시까지는 숙소 들어가요. 맛집 위주로요")

ANSWER = {
    "guard": {"off_topic": False, "prompt_injection": False, "out_of_scope": False, "quote": None},
    "pieces": [{"kind": "plan_item", "quote": "10시 경복궁"}, {"kind": "plan_item", "quote": "13:30 광장시장"}],
    "items": [
        {"place_quote": "경복궁", "day": 1, "date": D_2026_10_15, "date_quote": D_2026_10_15, "start": "10:00", "end": None,
         "time_quote": "10시", "kind": "activity"},
        {"place_quote": "광장시장", "day": 1, "date": D_2026_10_15, "date_quote": D_2026_10_15, "start": "13:30", "end": None,
         "time_quote": "13:30", "kind": "dining"}],
    "moves": [],
    "conditions": [{"code": "if_rain_indoor", "quote": "비 오면 실내로"}, {"code": "finish_by:21:00", "quote": "9시까지는 숙소 들어가요"}],
    "preferences": [{"code": "prefer_taxi", "quote": "웬만하면 택시로"}, {"code": "slow_pace", "quote": "천천히 다닐래요"},
                    {"code": "food_focus", "quote": "맛집 위주로요"}],
    "gaps": [], "missing": [], "trip": {"party_size": None, "days": None, "nights": None}}


class Reader:
    """읽기 에이전트 대역 — 계획 읽기 틀(`agent_read.SCHEMA`)로 부르면 정한 답, 그 밖의 부름은 모른다고 한다."""

    model = "test-reader"

    def structured(self, system, user, schema, *, num_predict=160):
        if schema is agent_read.SCHEMA:
            return ANSWER
        raise RuntimeError("이 시험은 계획 읽기 말고는 모델을 쓰지 않는다")

    def json(self, *args, **kwargs):              # 접수 입구는 `json` 이 있는 클라이언트만 읽기에 넘긴다(`trip_api` 계획 접수)
        raise RuntimeError("이 시험은 남은 줄 가리키기를 쓰지 않는다")


@pytest.fixture()
def reading(rv, monkeypatch):  # noqa: F811
    real = pipeline.agent_reader_config
    # 먼저 채우기는 따로 본다(`test_intake_prefill.py`) — 여기서는 읽은 성향이 담당 열쇠로 가는 길만
    monkeypatch.setattr(pipeline, "agent_reader_config", lambda tenant_id: {**real(tenant_id), "mode": "on", "prefill": "off"})
    yield rv


def _client():
    tour, kakao, reader = Tour(), Kakao(), Reader()
    return TestClient(create_app(
        classifier=lambda _m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_trip_router(place_factory=lambda: tour, kakao_factory=lambda: kakao, chat_factory=lambda: reader)]))


def _send(client, headers):
    response = client.post("/v1/web/trip-intakes", headers=headers, data={"text": PLAN})
    assert response.status_code == 202, response.text
    return response.json()["intake_id"]


def _view(client, headers, intake_id):
    return client.get(f"/v1/web/trip-intakes/{intake_id}", headers=headers).json()


def _confirm(client, headers, view):
    done = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/confirm", headers=headers, json={"revision": view["revision"]})
    assert done.status_code == 200, done.text
    with get_connection() as conn:
        trip = TripStore(view["_tenant"]).latest(conn, UUID(done.json()["trip"]["trip_id"]))[0]
    return trip["constraints"] if isinstance(trip, dict) else trip.constraints


def test_read_preferences_reach_the_registered_trip_as_owner_keys(reading):
    client = _client()
    headers = _key(client)
    view = _view(client, headers, _send(client, headers))
    assert view["status"] == "review", view.get("fatal")
    shown = {h["key"]: h for h in view["check"]["handoff"]}
    assert shown["survey.priority_details.mobility"]["status"] == "filled"                    # ①우리가 채움
    assert shown["survey.priority_details.mobility"]["quotes"] == ["웬만하면 택시로"]
    assert shown["constraints.day_hours.end"]["value"] == "21:00" and shown["constraints.day_hours.end"]["owner"]
    constraints = _confirm(client, headers, {**view, "_tenant": reading["tenant"]})
    survey = constraints["survey"]
    assert survey["priority_details"]["mobility"] == ["taxi"]                                  # ②이동 판정 · 일정 짜기
    assert survey["pace"] == "relaxed"                                                          #   일정 밀도
    assert survey["indoor_outdoor"] == {"activity": "indoor"}                                   #   활동 대안
    assert "맛집 위주로요" in constraints["meal_preference"]                                     #   식당 고르기
    assert constraints["day_hours"] == {"end": "21:00"}                                          #   하루 마감
    filled = {f["key"] for f in constraints["filled_by_reading"]}
    assert {"survey.priority_details.mobility", "survey.pace", "constraints.meal_preference", "constraints.day_hours.end"} <= filled
    assert "priority_details" not in (constraints.get("survey_answered") or [])                # 직접 답한 문항이 아니다
    assert "pace" not in (constraints.get("survey_answered") or [])


def test_a_customer_answer_wins_over_what_we_read(reading):
    client = _client()
    headers = _key(client)
    intake_id = _send(client, headers)
    saved = client.post(f"/v1/web/trip-intakes/{intake_id}/survey", headers=headers,
                        json={"answers": {"priority": {"areas": ["mobility"], "details": {"mobility": ["public"]}}}})
    assert saved.status_code == 200, saved.text
    view = _view(client, headers, intake_id)
    shown = {h["key"]: h for h in view["check"]["handoff"]}
    assert shown["survey.priority_details.mobility"]["status"] == "customer"                  # ③확인 화면도 「고객 답 먼저」
    constraints = _confirm(client, headers, {**view, "_tenant": reading["tenant"]})
    assert constraints["survey"]["priority_details"]["mobility"] == ["public"]                  # 고객이 고른 대중교통 그대로
    assert "survey.priority_details.mobility" not in {f["key"] for f in constraints["filled_by_reading"]}
    assert "priority_details" in constraints["survey_answered"]                                 # 고객 답은 직접 답한 문항이다
    assert constraints["survey"]["pace"] == "relaxed"                                            # 고객이 안 답한 자리는 채운다


# ── 로딩 중 질문 — 읽은 칸은 빼고 빈 칸만 `[2026-10-19 사용자 지시]` ─────────────────
def test_the_loading_questions_leave_out_what_the_plan_already_said(reading):
    """같은 계획서(「웬만하면 택시」 · 「천천히」 · 「비 오면 실내」 · 「맛집 위주」)를 실제 읽기 길로 읽으면 —
    여유는 묻지 않고, 우선순위는 분야 순서와 활동 세부만, 실내외는 식당 칸만 묻는다. 누구와는 계획서에서 읽지 않는다."""
    client = _client()
    headers = _key(client)
    view = _view(client, headers, _send(client, headers))
    assert view["status"] == "review", view.get("fatal")
    assert [q["id"] for q in view["questions"]] == ["party", "priority", "indoor_outdoor"]
    priority = {g["id"]: g for g in next(q for q in view["questions"] if q["id"] == "priority")["groups"]}
    assert priority["mobility"]["read"]["quotes"] == ["웬만하면 택시로"] and priority["mobility"]["read"]["text"] == "택시"
    assert priority["food"]["read"]["quotes"] == ["맛집 위주로요"] and priority["activity"]["read"] is None
    parts = {p["id"]: p for p in next(q for q in view["questions"] if q["id"] == "indoor_outdoor")["parts"]}
    assert parts["activity"]["read"]["quotes"] == ["비 오면 실내로"] and parts["dining"]["read"] is None
    skipped = {(s["question"], s["part"]) for s in view["skipped_by_reading"]}
    assert skipped == {("priority", "food"), ("priority", "mobility"), ("indoor_outdoor", "activity"), ("pace", None)}
    assert not {"mobility_ease", "day_hours"} & {q["id"] for q in view["questions"]}          # 덜 걷게 · 하루 시각은 묻지 않는다


def test_a_single_taxi_ride_read_as_the_whole_trip_does_not_skip_or_fill(reading, monkeypatch):
    """☆x600 서버 사례 — 이해 단계가 「택시로 이동」 한 구간을 여행 전체(scope all)로 읽었다. 「다 · 늘 · 주로 · 웬만하면」류가 없으니
    이동 세부를 묻고, 등록 때 설문에도 택시를 채우지 않는다."""
    monkeypatch.setitem(ANSWER, "moves", [{"mode": "taxi", "scope": "all", "quote": "택시로"}])
    monkeypatch.setitem(ANSWER, "preferences", [])
    monkeypatch.setitem(ANSWER, "conditions", [])
    client = _client()
    headers = _key(client)
    view = _view(client, headers, _send(client, headers))
    assert view["status"] == "review", view.get("fatal")
    priority = {g["id"]: g for g in next(q for q in view["questions"] if q["id"] == "priority")["groups"]}
    assert priority["mobility"]["read"] is None and view["skipped_by_reading"] == []
    constraints = _confirm(client, headers, {**view, "_tenant": reading["tenant"]})
    assert "mobility" not in ((constraints.get("survey") or {}).get("priority_details") or {})
