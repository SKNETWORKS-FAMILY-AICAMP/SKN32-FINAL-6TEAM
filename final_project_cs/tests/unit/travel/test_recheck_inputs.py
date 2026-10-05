# -*- coding: utf-8 -*-
"""전체 일정 재판정(`introduced_violations`)이 **맞는 값을 읽는다** — 적대 검토(2026-10-03)가 짚은 두 결함.

☆① 경로를 더 빠른 수단으로 바꾸면 이동 시간이 줄어드는데, 판정(`move_too_short`)이 **옛 계획 수단**(`route.planned`)의 소요를 읽어 「이동 시간이 너무 짧다」를 새 위반으로 잡았다
  — 자동 경로 변경이 재판정(d6101790)에 막혔다(지하철 25분 → 택시 15분). 고른 수단은 `detail.option` 에 있다.
☆② 「새로 생긴 위반」을 `(종류, 항목 순번)` 으로 비교했다 — 대체 항목은 **순번을 물려받아**, 원래 곳이 그날 휴무였고 대체할 곳도 그날 쉬면 「원래 있던 위반」으로 보고 통과했다.
  이제 위반이 가리키는 **항목 id** 로 비교한다 — 바뀐 항목(새 id)에 걸린 위반은 전부 새 위반이다.

재현:

    python -m pytest tests/unit/travel/test_recheck_inputs.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.actions.itinerary_actions import introduced_violations
from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, check_itinerary

KST = ZoneInfo("Asia/Seoul")
MONDAY = datetime(2026, 10, 5, 10, 0, tzinfo=KST)          # 월요일
ROUTE = {"planned": "subway", "options": [{"id": "subway", "label": "지하철", "eta_min": 25},
                                          {"id": "taxi", "label": "택시", "eta_min": 15}]}


def _parts(option=None, minutes=15):
    a = Part(seq=1, kind="activity", title="A", starts_at=MONDAY, ends_at=MONDAY + timedelta(minutes=60))
    m = Part(seq=2, kind="mobility", title="A → B", starts_at=MONDAY + timedelta(minutes=60),
             ends_at=MONDAY + timedelta(minutes=60 + minutes), route=ROUTE, detail={"option": option} if option else {})
    b = Part(seq=3, kind="activity", title="B", starts_at=MONDAY + timedelta(minutes=60 + minutes),
             ends_at=MONDAY + timedelta(minutes=120 + minutes))
    return [a, m, b]


def test_a_faster_chosen_route_option_is_not_too_short():
    """고른 수단(`detail.option`)의 소요로 판정한다 — 택시 15분을 지하철 25분과 비교하지 않는다."""
    assert [v.code for v in check_itinerary(_parts(option="taxi", minutes=15))] == []


def test_a_move_shorter_than_the_chosen_option_is_still_too_short():
    """반대로 **고른 수단**의 소요보다 짧으면 여전히 위반이다(택시 15분인데 10분으로 잡음)."""
    assert [v.code for v in check_itinerary(_parts(option="taxi", minutes=10))] == ["move_too_short"]


def test_registration_without_a_chosen_option_still_uses_the_planned_one():
    """등록 때(`detail.option` 없음)는 전과 같다 — 계획 수단의 소요."""
    assert [v.code for v in check_itinerary(_parts(option=None, minutes=15))] == ["move_too_short"]
    assert [v.code for v in check_itinerary(_parts(option=None, minutes=25))] == []


def _item(seq, kind, title, start, minutes, place=None, **detail):
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=uuid4() if place else None,
                starts_at=start, ends_at=start + timedelta(minutes=minutes), place=place, detail=dict(detail))


def _place(name, closed_on_monday):
    hours = {"hours_week": {"mon": "closed"}} if closed_on_monday else {"hours": ["09:00", "20:00"]}
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5, "longitude": 127.0,
            "attributes": hours}


def test_a_replacement_that_is_also_closed_that_day_is_a_new_violation():
    """원래 곳이 그날 휴무라 위반이 이미 있었고, 대체한 곳도 그날 쉰다 — 순번이 같다고 「원래 있던 위반」으로 넘기면 안 된다(전엔 통과했다)."""
    closed_original = _item(1, "activity", "원래(휴무)", MONDAY, 60, place=_place("원래", True))
    trip = {"constraints": {}, "party_size": 2}
    current = [closed_original]
    assert [v.code for v in check_itinerary([Part(seq=1, kind="activity", title="원래(휴무)", starts_at=MONDAY,
                                                  ends_at=MONDAY + timedelta(minutes=60), place=closed_original.place)])] == ["closed_day"]
    also_closed = closed_original.replaced_by(place=_place("대체도 휴무", True), title="대체도 휴무")
    assert [v.code for v in introduced_violations(trip, current, [also_closed])] == ["closed_day"]


def test_a_replacement_that_is_open_clears_the_violation_and_adds_none():
    closed_original = _item(1, "activity", "원래(휴무)", MONDAY, 60, place=_place("원래", True))
    open_replacement = closed_original.replaced_by(place=_place("여는 곳", False), title="여는 곳")
    assert introduced_violations({"constraints": {}, "party_size": 2}, [closed_original], [open_replacement]) == []


def test_a_violation_between_two_untouched_items_is_not_blamed_on_the_change():
    """바꾸지 않은 두 항목 사이의 위반은 이 변경의 탓이 아니다 — 항목 id 가 같으면 원래 있던 것이다."""
    a = _item(1, "activity", "A", MONDAY, 90)
    overlapping = _item(2, "activity", "B", MONDAY + timedelta(minutes=30), 60)         # A 와 겹친다(변경 전부터)
    tail = _item(3, "activity", "C", MONDAY + timedelta(hours=4), 60, place=_place("C", False))
    tail_replaced = tail.replaced_by(place=_place("C2", False), title="C2")
    assert introduced_violations({"constraints": {}, "party_size": 2}, [a, overlapping, tail],
                                 [a, overlapping, tail_replaced]) == []
