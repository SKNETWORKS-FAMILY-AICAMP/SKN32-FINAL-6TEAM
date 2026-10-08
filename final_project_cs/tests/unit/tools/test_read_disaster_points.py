# -*- coding: utf-8 -*-
"""`read.disaster_points` — 대체 후보 좌표 여러 곳의 재난문자를 한 번에 본다. `[2026-10-07]`

지역 판정은 `disaster()` 와 같은 `near()` 가 한다. 여기서는 순서·모름·상한만 본다.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.tools.read_tools import ReadToolbox


class _Source:
    def __init__(self) -> None:
        self.calls: list[tuple[float, float]] = []

    def near(self, latitude, longitude, at=None):
        self.calls.append((latitude, longitude))
        blocked = latitude > 37.6          # 북쪽 좌표만 위급재난 지역이라고 둔다
        return {"for_region": [{"step": "위급재난", "kind": "호우"}] if blocked else []}


def _box(source):
    box = ReadToolbox(lambda: None)
    box.travel = SimpleNamespace(disaster=source)
    return box


def test_answers_each_point_in_order_and_unknown_for_bad_coordinates():
    source = _Source()
    result = _box(source).disaster_points(None, points=[[37.5, 126.9], [37.7, 127.0], [None, None]])
    first, second, third = result["points"]
    assert first["for_region"] == [] and second["for_region"][0]["step"] == "위급재난"
    assert third is None
    assert source.calls == [(37.5, 126.9), (37.7, 127.0)]


def test_unknown_without_a_source_or_points():
    assert _box(None).disaster_points(None, points=[[37.5, 126.9]]) is None
    assert _box(_Source()).disaster_points(None, points=None) is None


def test_caps_the_number_of_points():
    source = _Source()
    result = _box(source).disaster_points(None, points=[[37.5, 126.9]] * 30)
    assert len(result["points"]) == ReadToolbox.DISASTER_POINTS_MAX


def test_is_a_registered_tool():
    assert "read.disaster_points" in ReadToolbox(lambda: None)._travel_tools()


class _AddressSource(_Source):
    def __init__(self) -> None:
        super().__init__()
        self.addresses: list[str | None] = []

    def near(self, latitude, longitude, at=None, address=None):
        self.addresses.append(address)
        return super().near(latitude, longitude, at)


def test_addresses_are_passed_through_when_given():
    """★`[2026-10-07]` 주소가 있으면 그 구로 거르게 넘긴다. 없으면 키를 싣지 않는다."""
    source = _AddressSource()
    _box(source).disaster_points(None, points=[[37.5, 126.9, "서울특별시 종로구 사직로 161"], [37.5, 126.9]])
    _box(source).disaster(None, latitude=37.5, longitude=126.9, address="서울특별시 중구 세종대로 110")
    assert source.addresses == ["서울특별시 종로구 사직로 161", None, "서울특별시 중구 세종대로 110"]
