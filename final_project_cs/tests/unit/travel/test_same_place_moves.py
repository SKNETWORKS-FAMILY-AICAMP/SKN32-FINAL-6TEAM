# -*- coding: utf-8 -*-
"""같은 곳 두 칸 사이에는 이동 구간을 만들지 않는다 — 같은 곳 판정 규칙. `[2026-10-21]`

재현:

    python -m pytest tests/unit/travel/test_same_place_moves.py -v
"""
from app.domains.travel_ops.components.intake.moves import SAME_PLACE_M, same_place


def place(name="황생가칼국수", lat=37.5665, lon=126.9780, place_id=None):
    return {"name": name, "latitude": lat, "longitude": lon, "place_id": place_id}


def test_the_same_name_at_the_same_spot_is_one_place():
    assert same_place(place(), place()) is True


def test_the_same_place_id_is_one_place_even_if_the_names_differ():
    assert same_place(place(name="황생 칼국수", place_id="p1"), place(name="황생가칼국수", place_id="p1")) is True


def test_the_same_name_far_apart_is_two_places():
    # 같은 상호의 다른 지점은 같은 곳이 아니다
    far = place(lat=37.5665 + 0.01)                      # 약 1.1 km
    assert same_place(place(), far) is False


def test_a_few_metres_apart_still_counts_as_one_place():
    near = place(lat=37.5665 + 0.0003)                   # 약 33 m
    assert SAME_PLACE_M >= 33
    assert same_place(place(), near) is True


def test_different_names_are_different_places_without_a_shared_id():
    assert same_place(place(), place(name="고속터미널")) is False


def test_an_unsettled_place_or_missing_coordinates_is_never_the_same():
    assert same_place(None, place()) is False
    assert same_place(place(), None) is False
    assert same_place(place(lat=None), place()) is False
