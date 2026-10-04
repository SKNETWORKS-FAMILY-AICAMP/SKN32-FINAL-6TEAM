# -*- coding: utf-8 -*-
"""실내·야외를 **모르는** 활동에 날씨 사건 — 먼저 「바꿀까요?」만 묻고, 「바꿔 줘」면 그때 안을 계산한다. `[2026-09-29]`

사용자 결정(2026-09-29): 모르는 일정이면 우천 상황을 알리고 변경을 원하는지 묻는다. 대체안 계산은 후보마다 바깥 점검을
부르므로 **동의한 뒤에만** 한다. 코덱스와 1회차 합의(모름이면 묻는다) — 기록은
`wiki/records/reports/2026-09-28_1826_Activity_PR6_전수검수_리포트.md`.

확정 시나리오의 09:00 장면(송파 미세먼지 경보 → 잠실 스카이타워)을 쓴다. 기본이면 스카이타워는 「야외」라서
아쿠아리움으로 **바로 바뀐다**(`test_trip_api.py`). 여기서는 스카이타워의 실내·야외를 「모름」으로 등록한다.

재현:

    python -m pytest tests/e2e/test_indoor_unknown_consent.py -v
"""
from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.pending import (CONSENT_KEY, CONSENT_REASON, PendingStore, ProposalRefused, choose,
                                            needs_consent)

from .test_trip_api import SCENARIO, _body, _detail, _slot, api  # noqa: F401 — 픽스처를 그대로 쓴다

ANSWER_LINE = "답이 없으면 원래 일정을 그대로 둡니다"


def _clear(**_):
    """고른 안을 그 시각에 다시 점검하는 자리 — 이 파일은 흐름만 본다(재점검은 `test_ask_first.py` 등이 본다)."""
    return {"verdict": "clear", "disruptions": []}


def _create_unknown(api) -> str:
    body = _body(api["customer"])
    for place in body["places"]:
        if place["key"] == "seoul_sky":
            place["weather_sensitive"] = None          # ★모름
    response = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert response.status_code == 201, response.text
    return response.json()["trip_id"]


def _proposals(api, trip_id):
    with get_connection() as conn:
        return PendingStore(api["tenant"]).list(conn, trip_id)


def _choose(api, trip_id, proposal_id, key, check=_clear):
    store = api["store"]
    with get_connection() as conn, conn.transaction():
        places = {str(p["place_id"]): p for p in store.places(conn, trip_id)}
        return choose(conn=conn, store=store, pending=PendingStore(api["tenant"]), trip_id=trip_id,
                      proposal_id=proposal_id, key=key, by="web:guest", places_by_id=places, check=check)


def test_unknown_indoor_is_asked_first_without_computing_alternatives(api):
    trip_id = _create_unknown(api)
    tick = api["tick"]("09:00")
    assert tick.adjusted == [] and [a["reason"] for a in tick.asked] == [CONSENT_REASON]
    assert _detail(api, trip_id)["version"] == 1                   # 일정은 그대로

    [proposal] = _proposals(api, trip_id)
    assert proposal["status"] == "open" and proposal["options_json"] == []   # ★안을 아직 계산하지 않았다
    notice = api["notices"]()[-1][1]
    assert notice["consent"] is True and notice["consent_key"] == CONSENT_KEY and notice["options"] == []
    assert "실내인지 확인하지 못했어요" in notice["text"] and ANSWER_LINE in notice["text"]


def test_saying_change_computes_options_then_choosing_applies(api):
    trip_id = _create_unknown(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)

    shown = _choose(api, trip_id, proposal["proposal_id"], CONSENT_KEY)
    assert shown["status"] == "options" and shown["options"]
    assert _detail(api, trip_id)["version"] == 1                   # 안을 보였을 뿐, 아직 안 바꿨다
    [reopened] = _proposals(api, trip_id)
    assert reopened["status"] == "open" and reopened["reason"] == f"{CONSENT_REASON}_options"
    names = [o["name"] for o in reopened["options_json"]]
    assert "아쿠아리움" in names
    assert api["notices"]()[-1][1]["type"] == "proposal_request"   # 안 1·2·3을 보이는 알림

    pick = next(o["key"] for o in reopened["options_json"] if o["name"] == "아쿠아리움")
    chosen = _choose(api, trip_id, proposal["proposal_id"], pick)
    assert chosen["status"] == "chosen" and chosen["version"] == 2
    assert _slot(_detail(api, trip_id), 2)["place"] == "아쿠아리움"


def test_keeping_the_original_changes_nothing_and_computes_nothing(api):
    trip_id = _create_unknown(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    calls = []

    def counting(**kwargs):
        calls.append(kwargs)
        return _clear()

    assert _choose(api, trip_id, proposal["proposal_id"], None, check=counting) == {"status": "kept"}
    assert calls == [] and _detail(api, trip_id)["version"] == 1


def test_an_option_key_before_consent_is_refused(api):
    trip_id = _create_unknown(api)
    api["tick"]("09:00")
    [proposal] = _proposals(api, trip_id)
    with pytest.raises(ProposalRefused) as refused:
        _choose(api, trip_id, proposal["proposal_id"], "some-place-id")
    assert refused.value.code == "unknown_option"


def test_a_known_outdoor_place_is_still_changed_right_away(api):
    """★모름이 아닌 곳은 지금과 같다 — 스카이타워를 「야외」로 등록하면 09:00 에 바로 바뀐다."""
    response = api["client"].post("/v1/trips", json=_body(api["customer"], request_id="known"),
                                  headers=api["auth"]("trip:write"))
    trip_id = response.json()["trip_id"]
    tick = api["tick"]("09:00")
    assert tick.asked == [] and len(tick.adjusted) == 1
    assert _slot(_detail(api, trip_id), 2)["place"] == "아쿠아리움"


# ── 판정 부품 ─────────────────────────────────────────────────
@pytest.mark.parametrize("report, expected", [
    ({"indoor_unknown": True, "disruptions": [{"category": "air_quality"}]}, True),
    ({"indoor_unknown": True, "disruptions": [{"category": "weather_warning", "kind": "호우주의보"}]}, True),
    ({"indoor_unknown": False, "disruptions": [{"category": "air_quality"}]}, False),        # 아는 야외 — 지금 규칙
    ({"indoor_unknown": True, "disruptions": [{"category": "weather_warning", "kind": "호우경보"}]}, False),  # 안전
    ({"indoor_unknown": True, "disruptions": [{"category": "earthquake"}]}, False),          # 안전
    ({"indoor_unknown": True, "disruptions": [{"category": "traffic_control"}]}, False),     # 실내외와 무관
    ({"indoor_unknown": True, "disruptions": []}, False),
])
def test_needs_consent(report, expected):
    assert needs_consent(report) is expected


def test_scenario_place_is_the_one_we_mark_unknown():
    """이 파일이 기대는 사실 — 시나리오의 스카이타워는 활동이고, 09:00 장면이 그곳을 친다."""
    sky = next(p for p in SCENARIO["places"] if p["key"] == "seoul_sky")
    assert sky["kind"] == "activity"


# ── Case 버전(기본 감시 — 사건을 열고 활동 에이전트가 처리) ─────────────────
from tests.scenario.test_case_version_day import _at, _latest, case_world  # noqa: E402,F401 — 픽스처


def test_the_case_path_also_asks_first_and_changes_nothing(case_world):
    """★기본 감시(Case 버전)도 같다 — 활동 에이전트가 대체안을 계산하지 않고 「바꿀까요?」만 연다."""
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE places SET weather_sensitive = NULL WHERE tenant_id=%s AND name=%s",
                    (case_world["tenant"], "잠실 스카이타워"))
    case_world["clock"].now = _at("09:00")
    tick = case_world["engine"].tick()
    assert len(tick.opened) == 1
    trip, _ = _latest(case_world)
    assert trip["version"] == 1                                    # 일정은 그대로
    with get_connection() as conn:
        [proposal] = PendingStore(case_world["tenant"]).list(conn, case_world["trip_id"])
    assert proposal["reason"] == CONSENT_REASON and proposal["options_json"] == []
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND topic='trip.notice'",
                    (case_world["tenant"],))
        notices = [row[0] for row in cur.fetchall()]
    assert any(n.get("consent") is True and "실내인지 확인하지 못했어요" in n["text"] for n in notices)


# ── `[2026-09-29 오후]` 제안이 기본 · 자동은 설문에서 직접 고른 경우만 · 관광공사 목록도 후보 ─────────────
def _create_with(api, constraints, request_id="c"):
    response = api["client"].post("/v1/trips", json=_body(api["customer"], request_id=request_id,
                                                        constraints=constraints),
                                  headers=api["auth"]("trip:write"))
    assert response.status_code == 201, response.text
    return response.json()["trip_id"]


def test_a_known_outdoor_place_is_asked_first_unless_auto_was_chosen(api):
    """★스카이타워는 「야외」로 안다. 그래도 설문에서 자동을 **직접** 고르지 않았으면 바꾸지 않고 먼저 묻는다."""
    trip_id = _create_with(api, {"payment": "card"})
    tick = api["tick"]("09:00")
    assert tick.adjusted == [] and [a["reason"] for a in tick.asked] == [CONSENT_REASON]
    notice = api["notices"]()[-1][1]
    assert notice["consent"] is True and "실내인지" not in notice["text"]     # 모름 때문이 아니다
    assert _detail(api, trip_id)["version"] == 1


def test_skipping_the_survey_question_is_not_choosing_auto(api):
    """설문을 냈어도 그 문항을 건너뛰었으면(기본값 replace 만 저장) 자동이 아니다."""
    trip_id = _create_with(api, {"payment": "card", "survey": {"version": "2026-09-24.v1", "pace": "moderate"}})
    tick = api["tick"]("09:00")
    assert tick.adjusted == [] and len(tick.asked) == 1
    assert _detail(api, trip_id)["version"] == 1


def test_explicit_auto_changes_right_away_and_offers_a_rollback(api):
    trip_id = _create_with(api, {"payment": "card",
                                 "survey": {"version": "2026-09-24.v1", "on_disruption": "replace"}})
    tick = api["tick"]("09:00")
    assert tick.asked == [] and len(tick.adjusted) == 1
    assert _slot(_detail(api, trip_id), 2)["place"] == "아쿠아리움"
    notice = api["notices"]()[-1][1]
    offer = notice["rollback"]
    assert offer["base_version"] == 2 and offer["to_version"] == 1 and offer["label"] == "되돌리기"
    back = api["client"].post(f"/v1/trips/{trip_id}/rollback",
                              json={"request_id": offer["request_id"], "base_version": offer["base_version"],
                                    "to_version": offer["to_version"]},
                              headers=api["auth"]("trip:write"))
    assert back.status_code in (200, 201), back.text
    assert _slot(_detail(api, trip_id), 2)["place"] == "잠실 스카이타워"


def test_a_catalog_place_is_offered_after_consent_and_registered_only_when_chosen(api):
    """★관광공사 목록의 가까운 실내 전시관(VE07)도 안으로 나온다. 목록 장소는 **고른 순간에만** 그 여행 장소로 등록된다."""
    import json as _json

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, title, latitude, longitude, "
                    "raw_json) VALUES (%s,'tour_api','t-ve07-1','14','시험 전시관',%s,%s,%s)",
                    (api["tenant"], 37.5140, 127.1030,
                     _json.dumps({"lclsSystm1": "VE", "lclsSystm2": "VE07", "lclsSystm3": "VE070100",
                                  "sigungucode": "18"})))
    try:
        trip_id = _create_with(api, {"payment": "card"}, request_id="catalog")
        api["tick"]("09:00")
        [asked] = _proposals(api, trip_id)
        shown = _choose(api, trip_id, asked["proposal_id"], CONSENT_KEY)
        assert shown["status"] == "options"
        [proposal] = _proposals(api, trip_id)
        names = [o["name"] for o in proposal["options_json"]]
        assert "시험 전시관" in names
        catalog_option = next(o for o in proposal["options_json"] if o["name"] == "시험 전시관")
        assert catalog_option["catalog_place"]["attributes"]["catalog_pending"] is True
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM places WHERE tenant_id=%s AND name='시험 전시관'", (api["tenant"],))
            assert cur.fetchone()[0] == 0                          # 안으로 보였을 뿐 아직 등록하지 않았다

        chosen = _choose(api, trip_id, proposal["proposal_id"], catalog_option["key"])
        assert chosen["status"] == "chosen" and _slot(_detail(api, trip_id), 2)["place"] == "시험 전시관"
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT trip_scope::text, weather_sensitive FROM places WHERE tenant_id=%s AND name='시험 전시관'",
                        (api["tenant"],))
            assert cur.fetchall() == [(trip_id, False)]           # 그 여행 전용 · 실내(전시관)
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM place_catalog WHERE tenant_id=%s", (api["tenant"],))


def test_auto_with_no_alternative_asks_instead_of_going_silent(api):
    """★자동을 고른 고객이라도 대체안을 못 찾으면 조용히 끝내지 않는다 — 「바꿀까요?」로 넘긴다(그때 목록까지 뒤진다)."""
    body = _body(api["customer"], request_id="lonely",
                 constraints={"payment": "card", "survey": {"version": "2026-09-24.v1", "on_disruption": "replace"}})
    body["places"] = [p for p in body["places"]
                      if p["key"] not in ("aquarium", "lotte_world", "mart_on_route", "mart_off_route", "lotte_mart")]
    keep = {p["key"] for p in body["places"]}
    body["items"] = [it for it in body["items"] if it.get("place") in keep or it.get("place") is None]
    response = api["client"].post("/v1/trips", json=body, headers=api["auth"]("trip:write"))
    assert response.status_code == 201, response.text
    trip_id = response.json()["trip_id"]
    tick = api["tick"]("09:00")
    assert tick.adjusted == [] and [a["reason"] for a in tick.asked] == [CONSENT_REASON]
    assert _detail(api, trip_id)["version"] == 1


def test_catalog_candidates_use_the_hours_already_read_in_the_db(api):
    """★`[2026-10-01]` DB 에 읽어 둔 운영시간(`catalog_hours` — 새벽 작업·팀 자료 옮김)이 있는 목록 후보는 **휴무면 걸러지고,
    열면 「영업을 확인할 수 없다」 경고 없이** 나온다. 읽어 둔 값이 없는 후보는 그대로 경고와 함께 나온다(바깥을 부르지 않는다)."""
    import json as _json

    always = {day: {"open": "00:00", "close": "23:59", "last_entry": None}
              for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    never = {day: "closed" for day in always}
    rows = [("t-open", "시험 열린 전시관", 37.5140, always), ("t-shut", "시험 쉬는 전시관", 37.5141, never),
            ("t-unknown", "시험 모르는 전시관", 37.5142, None)]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for cid, title, lat, week in rows:
            cur.execute("INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, title, latitude, "
                        "longitude, raw_json) VALUES (%s,'tour_api',%s,'14',%s,%s,%s,%s)",
                        (api["tenant"], cid, title, lat, 127.1030,
                         _json.dumps({"lclsSystm1": "VE", "lclsSystm2": "VE07", "lclsSystm3": "VE070100",
                                      "sigungucode": "18"})))
            if week is not None:
                cur.execute("INSERT INTO catalog_hours (tenant_id, source, content_id, hours_week, hours_read, read_at) "
                            "VALUES (%s,'tour_api',%s,%s,%s, now())",
                            (api["tenant"], cid, _json.dumps(week), _json.dumps({"method": "csv_rule"})))
    try:
        trip_id = _create_with(api, {"payment": "card"}, request_id="catalog-hours")
        api["tick"]("09:00")
        [asked] = _proposals(api, trip_id)
        _choose(api, trip_id, asked["proposal_id"], CONSENT_KEY)
        [proposal] = _proposals(api, trip_id)
        options = {o["name"]: o for o in proposal["options_json"]}
        assert "시험 쉬는 전시관" not in options                                  # 쉬는 곳은 걸러진다
        assert "시험 열린 전시관" in options
        assert not any("영업" in w for w in options["시험 열린 전시관"].get("warnings", []))
        assert options["시험 열린 전시관"]["catalog_place"]["attributes"]["hours_week"]["mon"]["open"] == "00:00"
        if "시험 모르는 전시관" in options:
            assert any("영업" in w for w in options["시험 모르는 전시관"].get("warnings", []))
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM catalog_hours WHERE tenant_id=%s", (api["tenant"],))
            cur.execute("DELETE FROM place_catalog WHERE tenant_id=%s", (api["tenant"],))
