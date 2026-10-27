# -*- coding: utf-8 -*-
"""등록한 여행 채팅 「○○호텔 넣어 줘」 — 정상 웹 입구에서 종류를 묻고, 고른 선택지는 모델 없이 숙박으로 넣는다. `[2026-10-27 B 채팅 전수검사]`

☆사용자 보고: 등록 뒤 채팅으로 호텔을 넣으면 액티비티로 들어갔다(`chat_edit` 가 숙소 찾기의 kind=activity 를 그대로 썼다).
해석 모델은 시험용 고정 답이다. 선택지를 누른 둘째 턴은 모델을 부르면 실패하게 해 「모델 없이」를 확인한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore

from .test_chat_edit_web import _answer, _hm, _say
from .test_decision_unit_web import decided  # noqa: F401 — 시험 준비물
from .test_trip_reopen import TOMORROW, YESTERDAY, _at, _member
from .test_web_api import _fresh_limit_cache, _h, api  # noqa: F401

KST = ZoneInfo("Asia/Seoul")


def _place(key, name, lat, lon, kind="activity"):
    return {"key": key, "name": name, "kind": kind, "lat": lat, "lon": lon, "weather_sensitive": None, "attributes": {}}


@pytest.fixture()
def hotel_chat(decided, api):
    _member(api, decided["key"])
    body = {"request_id": "hotel-chat-trip", "title": "서울 이틀", "locale": "ko", "party_size": 2, "constraints": {},
            "places": [_place("gb", "경복궁", 37.5796, 126.9770), _place("bc", "북촌한옥마을", 37.5826, 126.9836),
                       _place("ht", "롯데호텔 서울", 37.5651, 126.9810, kind="lodging")],
            "items": [{"seq": 1, "kind": "activity", "title": "경복궁", "place": "gb", "starts_at": _at(YESTERDAY, "10:00"),
                       "ends_at": _at(YESTERDAY, "12:00"), "detail": {}},
                      {"seq": 2, "kind": "activity", "title": "북촌한옥마을", "place": "bc", "starts_at": _at(TOMORROW, "10:00"),
                       "ends_at": _at(TOMORROW, "11:30"), "detail": {}}]}
    response = decided["client"].post("/v1/web/trips", json=body, headers=_h(decided["key"]))
    assert response.status_code == 201, response.text
    return {**decided, "trip": response.json(), "tenant": api["tenant"]}


def _latest(chat):
    with get_connection() as conn:
        trip, items = TripStore(chat["tenant"]).latest(conn, UUID(str(chat["trip"]["trip_id"])))
    return trip["version"], {i.title: i for i in items if i.kind != "mobility"}


def test_a_hotel_added_in_chat_is_asked_and_the_picked_stay_is_saved_as_lodging_without_the_model(hotel_chat):
    before, _ = _latest(hotel_chat)
    _answer(hotel_chat, "add_item", destination_text="롯데호텔 서울", anchor_kind="time", anchor_time="15:00", at_day="tomorrow")
    asked = _say(hotel_chat, "내일 3시에 롯데호텔 서울 넣어줘", "hotel-add-1")
    after, items = _latest(hotel_chat)
    assert asked["status"] == "clarify" and after == before and "롯데호텔 서울" not in items, asked
    assert [c["label"] for c in asked["choices"]] == ["숙박", "활동", "식사"], asked
    assert "어떤 일정으로 넣을까요" in asked["answer"], asked

    calls = []

    def no_model(*a, **kw):
        calls.append(a)
        raise AssertionError("선택지를 누른 턴은 해석 모델을 부르지 않는다")
    hotel_chat["decider"].structured = no_model
    stay = asked["choices"][0]
    done = _say(hotel_chat, stay["message"], "hotel-add-2")
    after, items = _latest(hotel_chat)
    assert done["status"] == "adjusted" and after == before + 1, done
    assert calls == []
    hotel = items["롯데호텔 서울"]
    assert hotel.kind == "lodging", hotel
    assert _hm(hotel.starts_at) == "15:00" and hotel.starts_at.astimezone(KST).date().isoformat() == TOMORROW
    # 끝은 체크아웃 — 숙박 규칙(등록과 같다): 여행 마지막 날이 체크인 날이면 다음 날 11:00
    checkout = (datetime.fromisoformat(TOMORROW) + timedelta(days=1)).date().isoformat()
    assert hotel.ends_at is not None and hotel.ends_at.astimezone(KST).date().isoformat() == checkout and _hm(hotel.ends_at) == "11:00"


def test_the_same_choice_sent_again_after_the_add_does_not_add_twice(hotel_chat):
    _answer(hotel_chat, "add_item", destination_text="롯데호텔 서울", anchor_kind="time", anchor_time="15:00", at_day="tomorrow")
    asked = _say(hotel_chat, "내일 3시에 롯데호텔 서울 넣어줘", "hotel-twice-1")
    done = _say(hotel_chat, asked["choices"][0]["message"], "hotel-twice-2")
    assert done["status"] == "adjusted", done
    version, items = _latest(hotel_chat)
    calls = []

    def model_down(*a, **kw):
        calls.append(a)
        raise RuntimeError("model down")
    hotel_chat["decider"].structured = model_down
    again = _say(hotel_chat, asked["choices"][0]["message"], "hotel-twice-3")
    # 판이 바뀐 뒤의 같은 선택지는 받지 않는다 — 해석(모델)으로 가고, 같은 넣기를 두 번 하지 않는다
    assert calls and _latest(hotel_chat)[0] == version and again["status"] != "adjusted", again


def test_a_hotel_with_a_check_in_word_is_added_as_a_stay_directly(hotel_chat):
    _answer(hotel_chat, "add_item", destination_text="롯데호텔 서울", anchor_kind="time", anchor_time="15:00", at_day="tomorrow")
    done = _say(hotel_chat, "내일 3시에 롯데호텔 서울 체크인 넣어줘", "hotel-checkin")
    _, items = _latest(hotel_chat)
    assert done["status"] == "adjusted" and items["롯데호텔 서울"].kind == "lodging", done
