# -*- coding: utf-8 -*-
"""지도 조합 — 고객 자기 지도 앱으로 여는 링크(키 없음). `[2026-09-29 사용자 결정]`

☆한국에서는 구글이 자동차·도보 길찾기를 주지 않고 대중교통은 들를 곳을 받지 않는다(ui 세션 실측) — 그래서 링크는
  **두 곳 사이 대중교통**만 만든다. 하루 경로 링크 · 퍼가기 경로 지도는 뺐다.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from app.domains.travel_ops.entry.trip_api import map_view


def _view(n, day="2030-01-01", kind="activity", address=None):
    return {"item_id": f"i{n}", "kind": kind, "title": f"곳 {n}", "place": f"곳 {n}" if kind != "mobility" else None,
            "starts_at": f"{day}T{9 + n:02d}:00:00+09:00",
            "lat": None if kind == "mobility" else 37.5 + n * 0.001, "lon": None if kind == "mobility" else 127.0,
            "place_info": {"address": address} if address else None, "map_url": None}


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_places_open_in_the_app_and_a_move_opens_transit_between_its_two_places():
    views = [_view(1, address="서울 종로구 1"), _view(2, kind="mobility"), _view(3)]
    out = map_view(views)
    assert _query(views[0]["map_url"])["query"] == "곳 1 서울 종로구 1" and "key" not in _query(views[0]["map_url"])
    assert _query(views[2]["map_url"])["query"].startswith("37.")                       # 주소 모르면 좌표
    move = _query(views[1]["map_url"])
    assert (move["origin"], move["travelmode"]) == ("곳 1 서울 종로구 1", "transit") and "waypoints" not in move
    day = out["days"][0]
    assert [s["number"] for s in day["stops"]] == [1, 2] and len(day["legs"]) == 1 and day["legs"][0]["from_item_id"] == "i1" and day["legs"][0]["url"]
    assert "embed" not in day and "app_route_urls" not in day


def test_days_are_separate_and_a_one_stop_day_has_no_legs():
    out = map_view([_view(1), _view(2), _view(3, day="2030-01-02")])
    assert [d["date"] for d in out["days"]] == ["2030-01-01", "2030-01-02"] and out["days"][1]["legs"] == []
