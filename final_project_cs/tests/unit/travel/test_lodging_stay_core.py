# -*- coding: utf-8 -*-
"""숙소 항목(며칠에 걸친다)을 코어 판정 · 이동 계산이 다루는 법. `[2026-10-13 사용자 결정 — 숙소 항목 B안]`

☆숙소 한 항목 = 한 숙박(체크인 ~ 체크아웃). 그대로 두면 앞뒤 일정 짝짓기가 숙소의 끝(체크아웃, 며칠 뒤)을
  「앞 일정 끝」으로 써서 ① 등록이 「시간 겹침」으로 거절되고 ② 체크인 날 저녁 이동이 체크아웃 날로 밀리고
  ③ 늦음 연쇄가 그 뒤 일정을 전부 「늦는다」로 본다.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary, leave_at
from app.domains.travel_ops.components.itinerary.itinerary_delay import delay_knock_on

KST = ZoneInfo("Asia/Seoul")


def _at(day, hour, minute=0):
    return datetime(2030, 11, day, hour, minute, tzinfo=KST)


DAY = [Part(2, "activity", "경복궁", _at(6, 10), _at(6, 12), {"name": "경복궁"}),
       Part(3, "dining", "점심", _at(6, 12, 30), _at(6, 13, 30), {"name": "식당"}),
       Part(4, "dining", "저녁", _at(6, 18), _at(6, 19), {"name": "저녁"}),
       Part(5, "activity", "남산", _at(7, 10), _at(7, 12), {"name": "남산"})]


def test_a_stay_across_nights_does_not_overlap_the_day_plan():
    stay = Part(1, "lodging", "롯데호텔", _at(6, 15), _at(9, 11), {"name": "롯데호텔"})
    assert check_itinerary([*DAY, stay]) == []


def test_two_stays_on_the_same_night_are_refused_with_a_remedy():
    a = Part(1, "lodging", "호텔A", _at(6, 15), _at(8, 11), {"name": "A"})
    b = Part(6, "lodging", "호텔B", _at(7, 15), _at(9, 11), {"name": "B"})
    (found,) = check_itinerary([*DAY, a, b])
    # contract_correction `[2026-10-28 x600 e78e038b]`: 위반 문장이 해요체·붙여쓰기로 바뀌었다(옛 단언 「11-08 11:00」)
    assert found.code == "stay_overlap" and "체크아웃(11월 8일 11:00)" in found.reason and found.remedy


def test_back_to_back_stays_pass_and_day_overlaps_are_still_caught():
    a = Part(1, "lodging", "호텔A", _at(6, 15), _at(8, 11), {"name": "A"})
    b = Part(6, "lodging", "호텔B", _at(8, 15), _at(9, 11), {"name": "B"})
    assert check_itinerary([*DAY, a, b]) == []
    clash = Part(7, "activity", "겹침", _at(6, 11), _at(6, 12), {"name": "x"})
    assert [v.code for v in check_itinerary([*DAY, clash])] == ["overlap"]


def test_leaving_a_stay_means_its_check_in_time():
    stay = Part(1, "lodging", "롯데호텔", _at(6, 15), _at(9, 11))
    assert leave_at(stay) == _at(6, 15), "체크아웃(11-09)이 아니라 체크인 시각에 떠난다고 본다"
    assert leave_at(DAY[0]) == _at(6, 12) and leave_at(Part(9, "activity", "끝 없음", _at(6, 9))) == _at(6, 9)


def test_a_delay_does_not_push_the_stay_or_everything_after_its_check_out():
    def item(seq, kind, title, start, end):
        return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=None, starts_at=start, ends_at=end,
                    place={"name": title, "latitude": 37.56, "longitude": 126.98}, detail={})
    lunch = item(1, "dining", "점심", _at(6, 12, 30), _at(6, 13, 30))
    stay = item(2, "lodging", "롯데호텔", _at(6, 15), _at(9, 11))
    dinner = item(3, "dining", "저녁", _at(6, 18), _at(6, 19))
    knocks = delay_knock_on([lunch, stay, dinner], lunch, 30)
    assert [k.item.title for k in knocks] == [], "30분 늦어도 15:00 체크인 · 18:00 저녁은 그대로 — 숙소가 체크아웃까지 커서를 끌지 않는다"
    assert all(k.item.kind != "lodging" for k in delay_knock_on([lunch, stay, dinner], lunch, 600)), "숙소는 늦음 연쇄 대상이 아니다"


def test_choosing_another_stay_does_not_push_the_evening_plan_to_the_check_out_day():
    """☆2026-10-13 로컬 확인 — 3박 숙소에서 후보를 고르자 「다른 안으로」(`plan_swap`)가 끝(체크아웃)까지 뒤 일정을 밀려다 `conflicts_next` 로 막혔다."""
    from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, plan_swap

    stay = Item(item_id=uuid4(), seq=1, kind="lodging", title="롯데호텔", place_id=None, starts_at=_at(6, 15), ends_at=_at(9, 11),
                place=None, detail={"alternates": [{"key": "myrealtrip:1", "name": "코리아나 호텔", "place_id": None,
                                                    "starts_at": _at(6, 15).isoformat(), "ends_at": _at(9, 11).isoformat()}]})
    move = Item(item_id=uuid4(), seq=2, kind="mobility", title="호텔 → 저녁", place_id=None, starts_at=_at(6, 17, 40), ends_at=_at(6, 17, 52),
                place=None, detail={})
    dinner = Item(item_id=uuid4(), seq=3, kind="dining", title="저녁", place_id=None, starts_at=_at(6, 18), ends_at=_at(6, 19),
                  place=None, detail={})
    plan = plan_swap(trip_version=1, base_version=1, items=[stay, move, dinner], places_by_id={}, item_id=stay.item_id,
                     choice="myrealtrip:1", message=None, request_id=None, check=None)
    assert isinstance(plan, ItineraryChange), plan
    assert set(plan.replacements) == {stay.item_id}, "저녁 쪽 이동은 그대로 — 밀지 않는다"
