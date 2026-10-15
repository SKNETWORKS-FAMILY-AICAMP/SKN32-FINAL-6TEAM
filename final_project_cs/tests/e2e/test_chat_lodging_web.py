# -*- coding: utf-8 -*-
"""웹 채팅 「숙소 다른 데로 바꿔줘」 — 숙소 항목이 **숙소 팀**에 닿아 실제 숙소 후보를 내밀고, 고르면 그 숙소로 바뀌는지 본다. `[2026-10-15]`

☆전에는 채팅의 「바꾸기」가 숙소 항목을 활동 팀으로 보냈다(`trip_messages._dispatch_decision` 의 담당 팀에 lodging 이 없었다).

★바깥 숙소 API(마이리얼트립 · 구글 호텔 SerpApi)는 **부르지 않는다** — 한도가 작다(마이리얼트립 상세 답 하나에 2번 · 429 뒤 10분 쉼,
  SerpApi 하루 8 · 달 250). 대신 mock 숙소 자료(`tests/fixtures/lodging_stub_hotels.json`)를 어댑터와 같은 모양으로 돌려주는
  mock 소스를 꽂는다. 자료는 시험용 이름 · 명동 부근 좌표 · 웹 검색의 대략 1박 가격이다(파일 머리말 — 카카오 실호출 근거는 git 밖 데이터 폴더).
해석 모델은 자동 시험용 고정 답(`test_chat_edit_web._answer`)이다 — 서버가 그 해석을 받아 숙소 팀까지 보내는지만 본다.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from app.domains.travel_ops.ports.data_sources import base as data_sources_base
from app.domains.travel_ops.ports.data_sources.base import TravelSources

from .test_chat_edit_web import _answer
from .test_decision_unit_web import decided  # noqa: F401 — 시험 준비물
from .test_web_api import _fresh_limit_cache, _h, _member, api  # noqa: F401

KST = ZoneInfo("Asia/Seoul")
FIXTURE = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "lodging_stub_hotels.json").read_text(encoding="utf-8"))
HOTELS = FIXTURE["hotels"]
ORIGINAL = next(h for h in HOTELS if h["role"] == "original")
PRICED = [h for h in HOTELS if h["role"] == "candidate"]
NOW = datetime.now(KST)
TOMORROW, DAY_AFTER = (NOW + timedelta(days=1)).date().isoformat(), (NOW + timedelta(days=2)).date().isoformat()


class MockStaySource:
    """마이리얼트립 어댑터(`ports/data_sources/myrealtrip.py`)와 같은 모양으로 mock 숙소 자료를 돌려준다. 네트워크 없음."""

    name = "myrealtrip"

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.by_gid = {h["test_gid"]: h for h in HOTELS}
        self.sold_out: set[int] = set()

    def stay_search(self, **arguments):
        self.calls.append(("stay_search", dict(arguments)))
        stays = [{"gid": h["test_gid"], "name": h["name"], "description": "호텔 · 중구 · 서울",
                  "price_per_night": h["price_per_night_krw"], "price_per_night_with_tax": None,
                  "rating": 4.2, "review_count": 100, "tags": [], "thumbnail_url": ""} for h in HOTELS]
        return {"stays": stays, "total": len(stays), "has_next": False, "confirmed_at": FIXTURE["fetched_at"], "source": "myrealtrip"}

    def stay_detail(self, *, gid, check_in, check_out, adults=2, children=0):
        self.calls.append(("stay_detail", {"gid": gid, "check_in": check_in, "check_out": check_out}))
        h = self.by_gid.get(int(gid))
        if h is None:
            return None
        price = h["price_per_night_krw"]
        return {"gid": h["test_gid"], "name": h["name"], "grade": "", "category": "호텔", "city": "서울", "country": "대한민국",
                "rating": 4.2, "review_count": 100, "latitude": h["latitude"], "longitude": h["longitude"],
                "address": h["address"], "link": f"https://example.test/stay/{h['test_gid']}",
                "sold_out": int(gid) in self.sold_out, "no_rooms": False,
                "price_per_night": price, "total_price": price, "room_count": 1, "rooms": [],
                "check_in": check_in, "check_out": check_out, "confirmed_at": FIXTURE["fetched_at"], "source": "myrealtrip"}


def _registry(client):
    return client.app.state.runtime.published_snapshot().controller.registry




#: ☆`[2026-10-15]` 처음 쓸 때는 「다른 안」 없는 숙소 항목이 공용 부품 `conversation_work.run_conversation` 에서 식사 · 활동 전용 계산
#:   (`plan_fresh_alternate`)으로 가 「바꿀 수 있는 다른 안이 없어요」가 됐다 — 숙박 팀이면 팀의 `_change`(숙소 후보)로 가게 고쳤다.
#: 등록 때 「다른 안」 하나를 들고 온 숙소(옛 판 경로)도 같은 숙소 팀 길로 간다 —(시험용 이름). 후보 계산에는 쓰이지 않는다
SEED = [{"key": "seed:grand", "name": "시험 숙소 Z", "rank": 1, "place_id": None}]


@pytest.fixture()
def lodging(decided, api, monkeypatch):
    """mock 숙소 소스를 꽂은 웹 앱. 팀 도구함의 바깥 숙소 · 항공 소스를 mock(또는 없음)으로 바꾼다."""
    source = MockStaySource()
    tools = _registry(decided["client"]).get("lodging").module.tools
    mocked = dataclasses.replace(tools.travel or TravelSources(), travel_search=source, stay_google=None,
                                 flight_offers=None, flight_google=None)
    monkeypatch.setattr(tools, "travel", mocked)
    # 고르기 경로의 가격 재확인(`trip_api._stay_recheck`)은 소스를 따로 만든다 — 그것도 mock 으로
    monkeypatch.setattr(data_sources_base, "build_travel_sources", lambda *a, **k: mocked)
    _member(api, decided["key"])                      # 게스트 제한(여행 1개)과 섞지 않는다
    return {**decided, "tenant": api["tenant"], "source": source}


def _trip(env, *, seeded: bool, booked: bool = False):
    """내일 N서울타워 → 그날 밤 시험 숙소 A(1박, 명동). 숙소 항목이 바꿀 대상이다."""
    detail = {"area": "명동", **({"alternates": SEED} if seeded else {}), **({"booked": True} if booked else {})}
    places = [{"key": "stay", "name": ORIGINAL["name"], "kind": "lodging", "lat": ORIGINAL["latitude"], "lon": ORIGINAL["longitude"],
               "weather_sensitive": None, "attributes": {}},
              {"key": "ns", "name": "N서울타워", "kind": "activity", "lat": 37.5512, "lon": 126.9882, "weather_sensitive": None,
               "attributes": {}}]
    items = [{"seq": 1, "kind": "activity", "title": "N서울타워", "place": "ns", "starts_at": f"{TOMORROW}T10:00:00+09:00",
              "ends_at": f"{TOMORROW}T12:00:00+09:00", "detail": {}},
             {"seq": 2, "kind": "lodging", "title": ORIGINAL["name"], "place": "stay", "starts_at": f"{TOMORROW}T15:00:00+09:00",
              "ends_at": f"{DAY_AFTER}T11:00:00+09:00", "detail": detail}]
    body = {"request_id": f"lodging-trip-{seeded}-{booked}", "title": "서울 1박", "locale": "ko", "party_size": 2,
            "constraints": {}, "places": places, "items": items}
    response = env["client"].post("/v1/web/trips", json=body, headers=_h(env["key"]))
    assert response.status_code == 201, response.text
    env["trip"] = response.json()
    return env


def _say(chat, text, request_id, **extra):
    response = chat["client"].post(f"/v1/web/trips/{chat['trip']['trip_id']}/messages", headers=_h(chat["key"]),
                                   json={"request_id": request_id, "message": text, "at": datetime.now(KST).isoformat(), **extra})
    assert response.status_code == 200, response.text
    return response.json()


def _latest(chat):
    with get_connection() as conn:
        trip, items = TripStore(chat["tenant"]).latest(conn, UUID(str(chat["trip"]["trip_id"])))
    return trip["version"], next(i for i in items if i.kind == "lodging")


def _ask_for_another_hotel(chat, request_id):
    _answer(chat, "apply_change", target=ORIGINAL["name"], change_scope="place")
    return _say(chat, "숙소 다른 데로 바꿔줘", request_id)


def _assert_hotels_offered(chat, body, before):
    after, stay = _latest(chat)
    assert body["classification"] == {"intent": "adjust_reject", "issue_code": "lodging_other"}, body
    assert body["status"] == "asked" and body["outcome"]["itinerary"] == "lodging_options", body
    assert after == before and stay.title == ORIGINAL["name"], "후보만 내민다 — 일정 판은 그대로"
    for hotel in PRICED:
        assert hotel["name"] in body["answer"], body
    assert ORIGINAL["name"] + "(" not in body["answer"] and "시험 숙소 E" not in body["answer"], \
        "지금 숙소와 가격 없는 곳은 후보가 아니다"
    assert "고르시면 바꿀게요" in body["answer"], body
    assert {name for name, _ in chat["source"].calls} <= {"stay_search", "stay_detail"}


def test_a_hotel_change_reaches_the_lodging_team_and_offers_hotels(lodging):
    """웹에서 막 등록한(「다른 안」 없는) 숙소 항목 — 사용자가 실제로 겪는 경우."""
    _trip(lodging, seeded=False)
    before, _ = _latest(lodging)
    body = _ask_for_another_hotel(lodging, "lodging-change")
    _assert_hotels_offered(lodging, body, before)


def test_a_hotel_change_offers_hotels_and_picking_one_changes_the_stay(lodging):
    """「다른 안」 하나를 들고 등록한 숙소도 숙소 팀 경로 끝까지 — 후보 3곳 → 웹 「선택이 필요해요」 카드에서 1번 → 숙소가 바뀐다."""
    _trip(lodging, seeded=True)
    before, _ = _latest(lodging)
    body = _ask_for_another_hotel(lodging, "lodging-change-seeded")
    _assert_hotels_offered(lodging, body, before)

    # 웹은 보류 제안을 카드로 보이고 고르면 `/proposals/{id}/choose` 를 부른다(frontend `lib/live/extras.ts`).
    # ☆채팅으로 「1번」만 보내는 길은 없다 — 제안을 낸 Case 는 이미 닫혀(resolved) 되묻기 대기(`resume_pending`)가 아니다
    trip_id = lodging["trip"]["trip_id"]
    proposals = lodging["client"].get(f"/v1/web/trips/{trip_id}/proposals", headers=_h(lodging["key"])).json()["proposals"]
    [proposal] = [p for p in proposals if p["proposal_id"] == body["outcome"]["proposal_id"]]
    first = next(o for o in proposal["options"] if o["rank"] == 1)
    assert first["name"] in {h["name"] for h in PRICED} and first["key"].startswith("myrealtrip:"), proposal
    chose = lodging["client"].post(f"/v1/web/trips/{trip_id}/proposals/{proposal['proposal_id']}/choose",
                                   json={"key": first["key"]}, headers=_h(lodging["key"]))
    assert chose.status_code == 200, chose.text

    after, stay = _latest(lodging)
    assert after == before + 1, chose.json()
    assert stay.title == first["name"], (stay, chose.json())
    hotel = next(h for h in HOTELS if h["name"] == first["name"])
    assert (stay.place or {}).get("name") in (None, hotel["name"]), stay.place
    assert ("stay_detail", {"gid": hotel["test_gid"], "check_in": TOMORROW, "check_out": DAY_AFTER}) in lodging["source"].calls, \
        "고를 때 그 숙소 1박 값을 mock 소스로 다시 봤다"


@pytest.mark.parametrize("seeded", [
    False,
    True,
])
def test_a_booked_hotel_is_not_changed(lodging, seeded):
    _trip(lodging, seeded=seeded, booked=True)
    before, _ = _latest(lodging)
    body = _ask_for_another_hotel(lodging, f"lodging-booked-{seeded}")
    after, stay = _latest(lodging)
    assert after == before and stay.title == ORIGINAL["name"], body
    assert "이미 예약하신 숙소라 바꾸지 않았어요" in body["answer"], body
    assert lodging["source"].calls == [], "예약한 숙소는 숙소 검색도 하지 않는다"
