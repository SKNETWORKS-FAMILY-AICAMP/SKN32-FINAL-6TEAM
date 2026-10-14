# -*- coding: utf-8 -*-
"""묵는 날 아침 「숙소 → 그날 첫 일정」 이동. `[2026-10-13 사용자 결정 — 숙소 항목 B안]`

☆이동 항목은 순서상 「바로 앞 일정 → 바로 뒤 일정」만 가리켰다 — 숙소에서 다음 날 첫 일정으로 가는 이동이 없었다.
  이제 그날 첫 일정 바로 앞에 이동을 넣고 `detail.from_stay` 로 출발지가 그날 묵는 숙소임을 적는다(`origin_of`).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.service_bindings import standalone_services
from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_changes import place_before, with_stay_moves
from app.domains.travel_ops.components.itinerary.itinerary_checks import origin_of
from app.domains.travel_ops.components.team_hooks import legs

KST = ZoneInfo("Asia/Seoul")


def _at(day, hour, minute=0):
    return datetime(2030, 11, day, hour, minute, tzinfo=KST)


def _item(seq, kind, title, start, end, lat=37.56, lon=126.98):
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=uuid4() if kind != "mobility" else None,
                starts_at=start, ends_at=end, detail={},
                place={"name": title, "latitude": lat, "longitude": lon} if kind != "mobility" else None)


@pytest.fixture
def engine():
    calls = []

    def planner(party, constraints, **_):
        def leg(a, b, arrive_by, not_before):
            calls.append((a["name"], b["name"], arrive_by, not_before))
            return {"starts_at": arrive_by - timedelta(minutes=25), "ends_at": arrive_by - timedelta(minutes=5), "eta_min": 20,
                    "route": {"planned": "subway", "options": [{"id": "subway", "eta_min": 20, "uses": []}]}}, None
        return leg
    with standalone_services():
        legs.register(leg_planner=planner, disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: 1500.0)
        yield calls
        legs.clear()


TRIP = [_item(1, "activity", "경복궁", _at(6, 10), _at(6, 12)), _item(2, "lodging", "롯데호텔", _at(6, 15), _at(9, 11)),
        _item(3, "dining", "저녁", _at(6, 18), _at(6, 19)), _item(4, "activity", "남산", _at(7, 10), _at(7, 12)),
        _item(5, "activity", "광장시장", _at(9, 9, 30), _at(9, 10, 30))]


def test_each_morning_of_the_stay_gets_a_move_from_the_hotel_to_the_first_stop(engine):
    out = with_stay_moves(TRIP)
    moves = [i for i in out if i.kind == "mobility"]
    assert [m.title for m in moves] == ["롯데호텔 → 남산", "롯데호텔 → 광장시장"], "체크인 날은 없고, 둘째 날 · 체크아웃 날 아침에 하나씩"
    assert all(m.detail["from_stay"] for m in moves)
    assert [(c[0], c[1], c[3]) for c in engine] == [("롯데호텔", "남산", _at(7, 6)), ("롯데호텔", "광장시장", _at(9, 6))], \
        "출발 하한은 그날 06:00 — 체크아웃 시각이 아니다"
    titles = [i.title for i in out]
    assert titles.index("롯데호텔 → 남산") == titles.index("남산") - 1, "그날 첫 일정 바로 앞에 놓는다"
    assert [i.seq for i in out] == list(range(1, len(out) + 1))
    tower_move = moves[0]
    assert origin_of(out, tower_move).title == "롯데호텔" and place_before(out, tower_move).title == "롯데호텔", \
        "순서상 앞은 전날 저녁이지만 출발지는 그날 묵는 숙소"


def test_it_is_not_added_twice_and_not_without_a_route(engine):
    once = with_stay_moves(TRIP)
    assert with_stay_moves(once) == once, "다시 불러도 같다"
    with standalone_services():
        legs.register(leg_planner=lambda *a, **kw: (lambda *x: (None, {"code": "no_data"})),
                      disruptions_from_events=lambda e: ([], []), walk_limit_m=lambda: None)
        assert with_stay_moves(TRIP) == TRIP, "길을 못 찾으면 넣지 않는다(지어내지 않는다)"


def test_a_trip_without_a_stay_is_untouched(engine):
    plain = [i for i in TRIP if i.kind != "lodging"]
    assert with_stay_moves(plain) == plain and engine == []


def test_changing_the_hotel_remakes_its_morning_moves_from_the_new_hotel(engine):
    from app.domains.travel_ops.components.itinerary.itinerary_changes import refresh_moves_around

    before = with_stay_moves(TRIP)
    hotel = next(i for i in before if i.kind == "lodging")
    new_place = {"place_id": str(uuid4()), "name": "코리아나 호텔", "latitude": 37.5662, "longitude": 126.9768}
    moved = hotel.replaced_by(place=new_place, title="코리아나 호텔")
    after = [moved if i.item_id == hotel.item_id else i for i in before]
    engine.clear()
    out = refresh_moves_around(before, after, {hotel.item_id: moved})
    mornings = [i.title for i in out if i.kind == "mobility" and i.detail.get("from_stay")]
    assert mornings == ["코리아나 호텔 → 남산", "코리아나 호텔 → 광장시장"], "옆 순서가 아니어도 그 숙소에서 출발하는 아침 이동을 다시 만든다"
    assert {c[0] for c in engine} == {"코리아나 호텔"}
