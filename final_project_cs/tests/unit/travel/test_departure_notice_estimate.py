# -*- coding: utf-8 -*-
"""어림값 이동의 출발 안내에는 「경로 확인」이 붙지 않는다 - 이동 계산기 실제 흐름 확인(2026-09-30) C2.

확인할 노선·도로(`uses`)가 하나도 없는 이동(직선 어림값 · 도보)은 사건 소스가 볼 것이 없다. 앞 판은 「확인 못 한 대상이 없다」를
「확인했다」로 읽어 「경로 확인 11:46」을 붙였다 - 어림값 이동이 확인된 경로처럼 나갔다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.trip_reminders import build_departure

KST = timezone(timedelta(hours=9))
T = lambda hm: datetime.fromisoformat(f"2026-10-07T{hm}:00+09:00")  # noqa: E731


class _NoEvents:
    def affecting(self, targets):
        return {}

    def unsupported(self, targets):
        return []                                       # 모르는 대상이 없다 - uses 가 비어 있어도 같다


def _scene(uses: list[str], label: str):
    route = {"from": "A", "to": "B", "planned": "p", "options": [{"id": "p", "label": label, "eta_min": 17, "uses": uses}]}
    move = Item(item_id=uuid4(), seq=2, kind="mobility", title="A → B", place_id=None, starts_at=T("11:46"),
                ends_at=T("12:03"), detail={"route_def": route})
    nxt = Item(item_id=uuid4(), seq=3, kind="activity", title="B 관람", place_id=None, starts_at=T("12:10"), ends_at=T("13:00"))
    return move, [move, nxt]


def test_an_estimate_move_is_not_announced_as_route_checked():
    move, items = _scene([], "도보 기준 [추정]")
    status, phrase = build_departure(move, items, route_events=_NoEvents(), routes=None, now=T("11:40"))
    text = phrase.render()
    assert status == "ok" and "가는 방법: 도보 기준 [추정] · 약 17분" in text, text
    assert "경로 확인" not in text, "확인할 노선이 없는 어림값 이동을 확인했다고 말하지 않는다"


def test_a_route_with_checked_targets_still_says_so():
    move, items = _scene(["2호선:잠실", "2호선:성수"], "2호선 잠실→성수")
    status, phrase = build_departure(move, items, route_events=_NoEvents(), routes=None, now=T("11:40"))
    assert status == "ok" and "(경로 확인 11:40)" in phrase.render(), phrase.render()


def test_estimate_labels_carry_the_marker_the_same_way_everywhere():
    """일정 생성(planner)과 장소 교체(itinerary_changes)가 어림값을 같은 모양(「… [추정]」)으로 적는다."""
    from app.modules.travel_ops.planner import Cand, _transfer_minutes

    def cand(key, lat, lon):
        return Cand(key=key, name=key, kind="activity", lat=lat, lon=lon, attributes={}, origin="places")

    near = _transfer_minutes(cand("a", 37.5700, 126.9800), cand("b", 37.5720, 126.9800))
    far = _transfer_minutes(cand("a", 37.5700, 126.9800), cand("c", 37.6200, 127.0600))
    assert near[2] == "도보 기준 [추정]" and far[2] == "대중교통 권장 [추정]", (near, far)
    assert "[추정]" in near[1] and "[추정]" in far[1]
