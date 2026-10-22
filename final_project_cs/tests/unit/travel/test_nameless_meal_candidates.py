# -*- coding: utf-8 -*-
"""가게 이름 없는 식사(「점심」 · 「ㅇㅇ 근처 점심」)의 후보 — 요식 팀이 원장 식당을 낸다 · 끼니에는 카페 · 디저트를 넣지 않는다. `[2026-10-18 사용자 지시]`

★실측(테스트 서버 guguroute, 2026-10-18): 「경복궁 보고 나서 점심」의 「점심」이 자동 추천으로 **디저트카페**(파티스리 데시데)가 됐고,
  「성수 근처 맛집에서 저녁」은 **카페**(무브모브 카페)가 됐다. 이름 없는 식사는 요식 팀 대체안을 부르지 않았고(원래 식당 번호가 없어서),
  자체 고르기의 카카오 채우기가 카페(CE7)를 식사로 쳤다. 증거 `eval/reports/2026-10-18_dining_vague_meal_lines_guguroute.md`.
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake import candidates
from app.domains.travel_ops.components.team_hooks import dining_alternatives


def _meal(title="점심", meal="점심", start="12:00", kind="dining"):
    return {"id": "m", "date": "2026-10-24", "starts_at": start, "ends_at": None, "kind": kind, "title": title,
            "place": None, "place_state": "needs_choice", "parts": {"meal": meal} if meal else None}


@pytest.mark.parametrize("item,want", [
    (_meal(), True),
    (_meal(title="서울숲", meal="점심"), True),
    (_meal(title="저녁 식사", meal=None), True),                      # 끼니 말이 제목에만 있어도 끼니다
    (_meal(title="카페", meal=None), False),                           # 카페 가는 일정은 끼니가 아니다
    (_meal(title="디저트 카페", meal=None), False),
    (_meal(title="점심 후 카페", meal="점심"), False),                    # 끼니 말이 있어도 카페 · 디저트 일정이면 카페가 맞다
    (_meal(title="성수 근처 맛집", meal=None, start="15:30"), False),    # 단서가 없고 끼니 시간도 아니면 거르지 않는다(모르는 것을 가정하지 않는다)
    (_meal(kind="activity"), False),
    # ★실측(로컬 원장, 2026-10-18): 「12:30 보라매공원 근처 점심」 — 장소를 못 정한 줄(unresolved)은 읽은 칸이 없고 끼니 말도 제목에서 떨어졌다.
    #   남은 단서는 시각뿐 — 끼니 시간대의 식사 일정이면 끼니다(자동 추천이 이 자리에 교회 카페를 넣었다)
    ({**_meal(title="보라매공원 근처", meal=None, start="12:30"), "place_state": "unresolved"}, True),
    ({**_meal(title="성수 근처", meal=None, start="19:00"), "place_state": "unresolved"}, True),
    ({**_meal(title="성수 근처", meal=None, start="23:30"), "place_state": "unresolved"}, False),
    # ★실측(로컬 원장, 2026-10-18): 「18:00 성수 근처 저녁」 — 규칙이 끼니 말을 떼어 종류(식사)로만 남겨 `meal` 이 비고, 찾는 말(label)이 「식당」이다
    ({**_meal(title="성수 근처", meal=None), "parts": {"meal": None, "label": "식당"}}, True),
    ({**_meal(title="성수 근처", meal=None), "parts": {"meal": None, "label": "카페"}}, False),
    ({**_meal(title="하동관 명동본점", meal=None), "place": {"name": "하동관", "category": "음식점 > 한식"}}, True),   # 이미 정한 곳이 음식점
    ({**_meal(title="블루보틀", meal="점심"), "place": {"name": "블루보틀", "category": "음식점 > 카페"}}, False),  # 정한 곳이 카페면 카페 일정
])
def test_which_lines_are_meals(item, want):
    assert candidates.is_meal_line(item) is want


@pytest.mark.parametrize("category,want", [
    ("음식점 > 카페 > 테마카페 > 디저트카페", True),                        # 카카오 카페(CE7)
    ("음식점 > 카페디저트", True),                                       # 요식 원장 요리 갈래
    ("음식점 > 간식 > 제과,베이커리", True),
    ("음식점 > 한식 > 육류,고기 > 닭요리 > 삼계탕", False),
    ("음식점 > 분식 > 떡볶이", False),                                    # 「떡」이 들었다고 디저트가 아니다
    ("음식점", False),
    (None, False),
])
def test_cafes_and_desserts_are_not_meal_places(category, want):
    assert candidates.not_a_meal({"name": "x", "category": category}) is want


def test_a_nameless_meal_asks_the_dining_team_around_the_reference_point(monkeypatch):
    seen = {}

    def near(conn, tenant, point, starts_at, ends_at=None, *, next_point=None, conditions=(), meal=True, radius_m=2000):
        seen.update(point=point, start=starts_at.isoformat(), meal=meal, next_point=next_point, radius_m=radius_m)
        return {"alternatives": [{"place_uid": "u1", "place_id": "p1", "name": "원장국밥", "latitude": 37.57, "longitude": 126.98,
                                  "address": "서울 종로구", "axis": "impact", "axis_label": "일정이 가장 덜 밀리는 곳"}]}

    monkeypatch.setattr(dining_alternatives, "near", near)
    monkeypatch.setattr(candidates, "_ledger_details", lambda conn, uids: {"u1": ("서울 종로구 1", "한식")})
    nxt = {"place": {"latitude": 37.58, "longitude": 126.99}}
    got = candidates._team_dining_near(None, "t", _meal(), (37.576, 126.977), nxt, radius_m=1500)
    assert seen == {"point": (37.576, 126.977), "start": "2026-10-24T12:00:00+09:00", "meal": True,
                    "next_point": (37.58, 126.99), "radius_m": 1500}
    assert [(p["name"], p["kind"], p["source"], p["category"], p["team_rank"], p["place_id"]) for p in got] == [
        ("원장국밥", "dining", "places", "음식점 > 한식", 0, "p1")]


def test_without_a_team_answer_or_a_time_the_local_picker_is_used(monkeypatch):
    monkeypatch.setattr(dining_alternatives, "near", lambda *a, **k: None)
    assert candidates._team_dining_near(None, "t", _meal(), (37.5, 127.0), None) is None
    monkeypatch.setattr(dining_alternatives, "near", lambda *a, **k: {"alternatives": []})
    assert candidates._team_dining_near(None, "t", _meal(start=None), (37.5, 127.0), None) is None
    assert candidates._team_dining_near(None, "t", _meal(), None, None) is None
