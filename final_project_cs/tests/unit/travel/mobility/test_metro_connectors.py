# -*- coding: utf-8 -*-
"""역 ↔ 건물 지하 연결통로 표(서울교통공사) — 이름 맞대기와 걷기 단축.

표에는 좌표가 없다: 「어느 역과 어느 건물이 이어지나」만 안다. 걷는 거리는 역~장소 직선 × 1.2 로 추정하고, 지상 길 값보다 짧을 때만 쓴다.
"""
from __future__ import annotations


from app.domains.travel_ops.instances.mobility.engine import connectors as K
from app.domains.travel_ops.instances.mobility.engine import plan as P


def _cn():
    return K.Connectors([
        {"station": "잠실역", "facility": "롯데월드", "line": "2"},
        {"station": "시청역", "facility": "지하상가", "line": "1"},          # 일반 이름 — 맞대지 않는다
        {"station": "노원역", "facility": "롯데백화점", "line": "4"},
        {"station": "강남", "facility": "ab", "line": "2"},                  # 너무 짧다
    ])


def test_a_place_inside_the_connected_building_matches_its_own_station_only():
    cn = _cn()
    assert cn.match("잠실", "롯데월드 아쿠아리움") == "롯데월드"
    assert cn.match("잠실역", "세르지오타키니 롯데월드몰점") == "롯데월드", "역 이름 끝의 「역」은 있어도 없어도 같다"
    assert cn.match("노원", "롯데월드 아쿠아리움") is None, "다른 역에 이어진 건물 이름으로는 맞대지 않는다"


def test_generic_or_too_short_facility_names_never_match():
    cn = _cn()
    assert cn.match("시청", "시청 지하상가 옷가게") is None
    assert cn.match("강남", "ab 카페") is None
    assert len(cn) == 2


def test_missing_table_means_no_connectors_not_a_fake_link(tmp_path):
    cn = K.Connectors.load(tmp_path / "없는파일.json")
    assert len(cn) == 0 and cn.match("잠실", "롯데월드") is None


def test_the_shipped_table_is_loaded_and_has_the_known_pairs():
    cn = K.Connectors.load()
    assert len(cn) > 100
    assert cn.match("잠실", "롯데월드몰 나이키") == "롯데월드"


def _planner(cn):
    pl = P.Planner.__new__(P.Planner)
    pl.detour = 1.4
    pl.__dict__["_connectors"] = cn
    return pl


REC = {"lat": 37.5133, "lng": 127.1002}                       # 잠실역 근처


def _place(name, dlat):
    return {"name": name, "lat": REC["lat"] + dlat, "lon": REC["lng"]}


def test_a_connected_place_uses_the_short_underground_walk_only_when_it_beats_the_street_route():
    pl = _planner(_cn())
    pl_place = _place("롯데월드 아쿠아리움", 0.0027)           # 직선 약 300 m
    street = 800 / 1.4                                          # 지상 길 800 m → 직선 환산
    got = pl._via_connector(pl_place, "잠실", REC, street)
    assert got < street, "지상 800 m 보다 짧게 본다"
    assert abs(got * 1.4 - 300 * 1.2) < 15, "역~장소 직선 × 1.2"
    assert pl.connector_used[0]["facility"] == "롯데월드" and pl.connector_used[0]["from_routed_m"] == 800
    short = 200 / 1.4                                           # 지상이 이미 더 짧으면 그대로
    assert pl._via_connector(pl_place, "잠실", REC, short) == short


def test_an_unconnected_or_far_place_is_left_alone():
    pl = _planner(_cn())
    assert pl._via_connector(_place("동네 식당", 0.0027), "잠실", REC, 500.0) == 500.0
    assert pl._via_connector(_place("롯데월드 매장", 0.02), "잠실", REC, 900.0) == 900.0, "역에서 700 m 밖은 연결통로 건물로 보지 않는다"
    assert not getattr(pl, "connector_used", [])
