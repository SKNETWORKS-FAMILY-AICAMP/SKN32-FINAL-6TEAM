"""등록 전후 검증 이동 보존과 기존 여행의 정확한 대응만 복구하는 경계."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4

import pytest

from app.domains.travel_ops.components.intake.registered_moves import recover_for_routes, with_review_moves
from app.domains.travel_ops.components.itinerary.itinerary import Item


def example():
    places = [{"key": "p1", "lat": 37.5, "lon": 127.0}, {"key": "p2", "lat": 37.6, "lon": 127.1}]
    stops = [{"seq": i + 1, "title": title, "kind": "activity", "place": f"p{i + 1}",
              "starts_at": f"2026-10-18T{start}:00+09:00", "ends_at": f"2026-10-18T{end}:00+09:00",
              "detail": {"intake": {"intake_id": "intake", "revision": 2, "source_id": "source", "index": i}}}
             for i, (title, start, end) in enumerate([("경복궁", "09:00", "10:00"), ("광장시장", "11:00", "12:00")])]
    checked = [{"id": f"0-{i}", "source_id": "source", "index": i, "title": stop["title"], "kind": "activity",
                "date": "2026-10-18", "starts_at": stop["starts_at"][11:16], "ends_at": stop["ends_at"][11:16],
                "place": {"latitude": places[i]["lat"], "longitude": places[i]["lon"]}} for i, stop in enumerate(stops)]
    review = {"items": checked, "moves": [{"from": "0-0", "to": "0-1", "depart": "10:00", "arrive": "10:20", "minutes": 20,
               "mode": "subway", "mode_label": "지하철", "uses": ["3호선:경복궁", "3호선:종로3가"], "basis": "timetable", "summary": "지하철 20분"}]}
    return {"items": stops, "places": places}, review


def stored(body, *, legacy=False):
    result = []
    for row, place in zip(body["items"], body["places"]):
        detail = deepcopy(row["detail"])
        if legacy:
            detail["intake"].pop("source_id")
            detail["intake"].pop("index")
        result.append(Item(item_id=uuid4(), seq=row["seq"], kind=row["kind"], title=row["title"], place_id=uuid4(),
                           starts_at=datetime.fromisoformat(row["starts_at"]), ends_at=datetime.fromisoformat(row["ends_at"]),
                           detail=detail, place={"latitude": place["lat"], "longitude": place["lon"]}))
    return result


def test_registration_preserves_the_checked_mode_times_and_stations_without_mutating_the_input():
    body, review = example()
    before = deepcopy(body)
    result = with_review_moves(body, review)
    assert body == before
    assert [row["kind"] for row in result["items"]] == ["activity", "mobility", "activity"]
    move = result["items"][1]
    assert move["starts_at"] == "2026-10-18T10:00:00+09:00" and move["ends_at"] == "2026-10-18T10:20:00+09:00"
    assert move["detail"]["route_def"]["options"][0]["uses"] == review["moves"][0]["uses"]
    assert move["detail"]["route_def"]["planned"] == "subway"
    assert [row["seq"] for row in result["items"]] == [1, 2, 3]


@pytest.mark.parametrize("change", ["place", "time", "end", "legacy_title", "kind", "key", "order", "date", "missing_time"])
def test_registration_does_not_attach_a_stale_or_wrong_pair(change):
    body, review = example()
    if change == "place": body["places"][1]["lat"] = 37.9
    elif change == "time": body["items"][1]["starts_at"] = "2026-10-18T12:00:00+09:00"
    elif change == "end": body["items"][1]["ends_at"] = None
    elif change == "legacy_title":                       # 원본 위치가 없는 옛 일정은 제목까지 같아야 짝이다
        body["items"][1]["title"] = "다른 장소"
        for stop in body["items"]:
            stop["detail"]["intake"].pop("source_id")
            stop["detail"]["intake"].pop("index")
    elif change == "kind": body["items"][1]["kind"] = "dining"
    elif change == "key": body["items"][1]["detail"]["intake"]["index"] = 5
    elif change == "order": body["items"].reverse()
    elif change == "date": body["items"][1]["starts_at"] = "2026-10-19T11:00:00+09:00"
    elif change == "missing_time": review["moves"][0]["depart"] = None
    assert len(with_review_moves(body, review)["items"]) == 2


def test_a_stop_renamed_to_the_place_the_customer_picked_keeps_its_moves():
    """`[2026-10-25 사용자 결정]` 등록은 고객이 고른 곳의 이름으로 제목을 바꾼다(`assemble._item_title`) — 원본 위치가 같으면 제목은 견주지 않는다.
    ☆제목까지 견주다 「인사동 쌈지길」 → 「인사동」 일정 옆 이동이 등록에서 빠졌다(로컬 실서버 여행 f966844a)."""
    body, review = example()
    body["items"][1]["title"] = "광장시장 빈대떡집"
    assert [row["kind"] for row in with_review_moves(body, review)["items"]] == ["activity", "mobility", "activity"]


@pytest.mark.parametrize("legacy", [False, True])
def test_old_trip_routes_recover_checked_moves_with_stable_ids_without_changing_stored_stops(legacy):
    body, review = example()
    items = stored(body, legacy=legacy)
    result = recover_for_routes(items, review)
    assert [row.kind for row in result] == ["activity", "mobility", "activity"]
    assert recover_for_routes(items, review)[1].item_id == result[1].item_id
    assert items[1].seq == 2 and result[2].seq == 3
    assert result[1].detail["route_def"]["options"][0]["uses"] == review["moves"][0]["uses"]


def test_explicit_mobility_is_not_replaced_and_unrelated_missing_review_has_no_effect():
    body, review = example()
    items = stored(body)
    move = Item(item_id=uuid4(), seq=2, kind="mobility", title="현재 이동", place_id=None,
                starts_at=items[0].ends_at, ends_at=items[1].starts_at, detail={"route_def": {"planned": "walk"}})
    items[1].seq = 3
    result = recover_for_routes([items[0], move, items[1]], review)
    assert len(result) == 3 and result[1].item_id == move.item_id and result[1].detail == move.detail
    assert len(recover_for_routes(items, None)) == 2


def test_ambiguous_legacy_stops_do_not_get_a_review_route():
    body, review = example()
    items = stored(body, legacy=True)
    clone = deepcopy(items[0]); clone.item_id = uuid4(); clone.seq = 0
    assert all(item.kind != "mobility" for item in recover_for_routes([clone, *items], review))
