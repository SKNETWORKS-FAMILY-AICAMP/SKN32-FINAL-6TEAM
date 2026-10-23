# -*- coding: utf-8 -*-
"""여행 화면 「끝났어요」 — `POST /v1/web/trips/{trip_id}/progress`. `[2026-10-22 사용자 결정 — ST4F-716]`

★계약 `wiki/actions/journey-progress.md` 「웹 진행 단추」. 채팅 진행 보고와 같은 저장 경로(`journey_progress.apply`)를 모델 없이 부른다.
  여기서는 실제 DB 로 ①「바로 진행」이 다음 방문을 지금 출발로 앞당기되 장소 행의 운영시간(여는 시각) 전으로는 당기지 않는 것 · 판 하나
  ②같은 요청 재전송 ③「그대로 유지」는 끝난 시각만 ④낡은 판 · 시작 전 일정 · 이동 항목 · 남의 여행 거절을 본다.

시계는 오늘 10:50 으로 고정하고(`trip_api.datetime`), 이동 계산기는 시험용(걸어서 3분 + 여유 2분)이다 — 계산기 정확도를 재지 않는다.

재현:

    python -m pytest tests/e2e/test_trip_progress_web.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.conversation import journey_progress
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.entry import trip_api

from .test_trip_api import api  # noqa: F401 — 픽스처를 그대로 쓴다
from .test_web_api import _h, _member, _session

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).date().isoformat()
NOW = datetime.fromisoformat(f"{TODAY}T10:50:00+09:00")


class _Clock(datetime):
    """입구가 읽는 지금(`datetime.now(KST)`)만 오늘 10:50 으로 고정한다."""

    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def _walk(origin, destination, deadline, earliest):
    return {"starts_at": deadline - timedelta(minutes=5), "ends_at": deadline - timedelta(minutes=2), "eta_min": 3,
            "route": {"planned": "walk", "options": [{"id": "walk", "eta_min": 3}]},
            "departure_context": {"schema_version": 1, "from_place": origin, "to_place": destination}}, None


def _at(hhmm: str) -> str:
    return f"{TODAY}T{hhmm}:00+09:00"


def _place(key, name, lat, lon, attributes=None):
    return {"key": key, "name": name, "kind": "activity", "lat": lat, "lon": lon, "weather_sensitive": None,
            "attributes": attributes or {}}


def _item(seq, kind, title, place, start, end):
    return {"seq": seq, "kind": kind, "title": title, "place": place, "starts_at": _at(start), "ends_at": _at(end), "detail": {}}


@pytest.fixture()
def day(api, monkeypatch):
    """오늘: 북촌한옥마을 10:00~11:30(진행 중) → 걸음 → 인사동 12:00~13:00(11:30 에 연다) → 창덕궁 14:00~15:30."""
    monkeypatch.setattr(trip_api, "datetime", _Clock)
    monkeypatch.setattr(journey_progress, "_planner", lambda trip, supplied=None: _walk)
    key = _session(api)["user_key"]
    _member(api, key)
    body = {"request_id": "progress-trip", "title": "서울 하루", "locale": "ko", "party_size": 2, "constraints": {},
            "places": [_place("bc", "북촌한옥마을", 37.5826, 126.9836),
                       _place("is", "인사동", 37.5740, 126.9850, {"hours": ["11:30", "21:00"]}),
                       _place("cd", "창덕궁", 37.5794, 126.9910)],
            "items": [_item(1, "activity", "북촌한옥마을", "bc", "10:00", "11:30"),
                      _item(2, "mobility", "북촌한옥마을 → 인사동 · 걸음", None, "11:30", "11:45"),
                      _item(3, "activity", "인사동", "is", "12:00", "13:00"),
                      _item(4, "activity", "창덕궁", "cd", "14:00", "15:30")]}
    response = api["client"].post("/v1/web/trips", json=body, headers=_h(key))
    assert response.status_code == 201, response.text
    return {**api, "key": key, "trip_id": response.json()["trip_id"]}


def _latest(day):
    with get_connection() as conn:
        trip, items = TripStore(day["tenant"]).latest(conn, UUID(str(day["trip_id"])))
    return trip["version"], items


def _id(items, title):
    return str(next(i.item_id for i in items if i.title == title))


def _post(day, body, key=None):
    return day["client"].post(f"/v1/web/trips/{day['trip_id']}/progress", json=body, headers=_h(key or day["key"]))


def _hm(moment):
    return moment.astimezone(KST).strftime("%H:%M")


def test_start_now_moves_the_next_visit_but_not_before_it_opens(day):
    version, items = _latest(day)
    response = _post(day, {"request_id": "now-1", "base_version": version, "item_id": _id(items, "북촌한옥마을"),
                           "action": "advance_trip"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "adjusted" and body["version"] == version + 1 and body["state"] == "departing", body
    assert body["hours_check"] == "checked" and body["next_start_at"] == _at("11:30"), body
    after, items = _latest(day)
    assert after == version + 1
    visits = {i.title: i for i in items if i.kind != "mobility"}
    assert _hm(visits["북촌한옥마을"].ends_at) == "10:50"
    assert visits["북촌한옥마을"].detail["execution"]["state"] == "completed"
    # 걸어서 10:53 도착 · 여유를 넣은 10:55 는 인사동이 여는 11:30 전이다 — 여는 시각으로 맞춘다(머무는 1시간 그대로)
    assert (_hm(visits["인사동"].starts_at), _hm(visits["인사동"].ends_at)) == ("11:30", "12:30")
    assert (_hm(visits["창덕궁"].starts_at), _hm(visits["창덕궁"].ends_at)) == ("14:00", "15:30")
    moves = [i for i in items if i.kind == "mobility"]
    assert len(moves) == 1 and _hm(moves[0].starts_at) == "10:50"             # 옛 11:30 출발 이동은 새 경로로 바뀌었다


def test_the_same_request_again_does_not_write_another_version(day):
    version, items = _latest(day)
    body = {"request_id": "now-twice", "base_version": version, "item_id": _id(items, "북촌한옥마을"), "action": "advance_trip"}
    first = _post(day, body)
    assert first.status_code == 200, first.text
    again = _post(day, body)
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "already_applied" and again.json()["version"] == version + 1
    assert _latest(day)[0] == version + 1


def test_keep_records_only_the_end(day):
    version, items = _latest(day)
    response = _post(day, {"request_id": "keep-1", "base_version": version, "item_id": _id(items, "북촌한옥마을"),
                           "action": "complete_item"})
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "completed"
    _, items = _latest(day)
    visits = {i.title: i for i in items if i.kind != "mobility"}
    assert _hm(visits["북촌한옥마을"].ends_at) == "10:50"
    assert (_hm(visits["인사동"].starts_at), _hm(visits["인사동"].ends_at)) == ("12:00", "13:00")


def test_a_stale_version_is_409_with_the_current_version(day):
    version, items = _latest(day)
    response = _post(day, {"request_id": "stale-1", "base_version": version + 5, "item_id": _id(items, "북촌한옥마을"),
                           "action": "advance_trip"})
    assert response.status_code == 409, response.text
    assert "stale_itinerary" in response.text and str(version) in response.text
    assert _latest(day)[0] == version


def test_a_visit_that_has_not_started_is_409(day):
    version, items = _latest(day)
    response = _post(day, {"request_id": "early-1", "base_version": version, "item_id": _id(items, "창덕궁"),
                           "action": "complete_item"})
    assert response.status_code == 409 and "progress_not_current" in response.text, response.text
    assert _latest(day)[0] == version


def test_a_move_item_or_another_customers_trip_is_404(day, api):
    version, items = _latest(day)
    move = str(next(i.item_id for i in items if i.kind == "mobility"))
    response = _post(day, {"request_id": "move-1", "base_version": version, "item_id": move, "action": "complete_item"})
    assert response.status_code == 404 and "progress_target_not_found" in response.text, response.text
    stranger = _session(api)["user_key"]
    response = _post(day, {"request_id": "other-1", "base_version": version, "item_id": _id(items, "북촌한옥마을"),
                           "action": "complete_item"}, key=stranger)
    assert response.status_code == 404, response.text
    assert _latest(day)[0] == version
