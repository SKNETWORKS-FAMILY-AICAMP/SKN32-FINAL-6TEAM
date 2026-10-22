# -*- coding: utf-8 -*-
"""가게 이름 없는 식사(「점심」 · 「ㅇㅇ 근처 점심」)의 확인 화면 후보 — **요식 팀이 먼저** 원장 식당을 내고, 끼니에는 카페 · 디저트를 넣지 않는다. `[2026-10-18 사용자 지시]`

★실측(테스트 서버, 2026-10-18): 이름 없는 식사는 요식 팀 대체안을 부르지 않았다(원래 식당 번호가 없어 `_team_dining_places` 가 None) ·
  자동 추천이 카카오 「음식점」 검색의 카페(CE7)를 식사로 받아 점심에 디저트카페가 들어갔다. 증거 `eval/reports/2026-10-18_dining_vague_meal_lines_guguroute.md`.

재현:

    python -m pytest tests/e2e/test_intake_nameless_meal_team.py -v
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.intake import autofix, candidates
from app.domains.travel_ops.components.team_hooks import dining_alternatives
from app.infrastructure.db.session import get_connection

from .test_intake_review import rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

NOW = datetime(2030, 1, 5, 9, 0, tzinfo=timezone(timedelta(hours=9)))
#: 실데이터와 섞이지 않게 서울 밖(제주 근처)에 둔다 — 원장(`dining.dn_place`)은 테넌트가 없는 공용 표다
SPOT = (33.4500, 126.5600)


class Kakao:
    """카카오 근처 찾기 — 같은 자리의 카페 하나 · 음식점 하나."""

    def __init__(self):
        self.asked = []

    def search(self, query, size=10, near=None):
        self.asked.append(query)
        lat, lon = near or SPOT
        return [{"id": "k-cafe", "name": "지도디저트카페", "latitude": lat + 0.0003, "longitude": lon, "category_group": "CE7",
                 "category": "음식점 > 카페 > 테마카페 > 디저트카페", "address": "제주"},
                {"id": "k-food", "name": "지도백반집", "latitude": lat + 0.0004, "longitude": lon, "category_group": "FD6",
                 "category": "음식점 > 한식 > 백반", "address": "제주"}]


@pytest.fixture()
def ledger_world(rv):  # noqa: F811
    """원장 식당 둘(한식 · 카페디저트)과 그 공용 장소 행."""
    made = []
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for name, cuisine, dlat in (("원장한식당", "한식", 0.0005), ("원장디저트집", "카페디저트", 0.0001)):
            uid = str(uuid.uuid4())
            cur.execute("INSERT INTO dining.dn_place (place_uid, name_ko, area, record_status, is_synthetic, lat, lng, category, category_method) "
                        "VALUES (%s,%s,'시험','active',true,%s,%s,%s,'manual')", (uid, name, SPOT[0] + dlat, SPOT[1], cuisine))
            cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) "
                        "VALUES (%s,%s,'dining',%s,%s,'dining_ledger',jsonb_build_object('source','dining_ledger','dining_place_uid',%s::text))",
                        (rv["tenant"], name, SPOT[0] + dlat, SPOT[1], uid))
            made.append(uid)
    yield rv
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM places WHERE tenant_id=%s AND source_name='dining_ledger'", (rv["tenant"],))
        cur.execute("DELETE FROM dining.dn_core_place_link WHERE place_uid::text = ANY(%s)", (made,))   # 후보 고르기가 이은 연결 행
        cur.execute("DELETE FROM dining.dn_place WHERE place_uid::text = ANY(%s)", (made,))


def _review(title="점심", meal="점심", label=None):
    before = {"id": "a", "date": "2030-01-05", "starts_at": "10:00", "ends_at": "11:30", "kind": "activity", "title": "앞 일정",
              "place": {"name": "앞 일정", "latitude": SPOT[0] - 0.002, "longitude": SPOT[1], "kind": "activity"},
              "place_state": "found", "parts": None}
    meal_item = {"id": "m", "date": "2030-01-05", "starts_at": "12:00", "ends_at": "13:00", "kind": "dining", "title": title,
                 "place": None, "place_state": "needs_choice", "parts": {"meal": meal, "label": label}}
    after = {"id": "b", "date": "2030-01-05", "starts_at": "15:00", "ends_at": "16:30", "kind": "activity", "title": "뒤 일정",
             "place": {"name": "뒤 일정", "latitude": SPOT[0] + 0.002, "longitude": SPOT[1], "kind": "activity"},
             "place_state": "found", "parts": None}
    return {"items": [before, meal_item, after], "moves": []}, meal_item


def _alternatives(world, review, item, kakao):
    with get_connection() as conn:
        return candidates.alternatives(conn, tenant_id=world["tenant"], review=review, item=item, kakao=kakao, use_engine=False, now=NOW)


def test_a_nameless_lunch_asks_the_dining_team_first(ledger_world, monkeypatch):
    seen = {}

    def near(conn, tenant, point, starts_at, ends_at=None, *, next_point=None, conditions=(), meal=True, radius_m=2000):
        seen.update(meal=meal, point=point)
        return {"alternatives": [{"place_uid": None, "place_id": str(uuid.uuid4()), "name": "팀이고른식당", "latitude": SPOT[0],
                                  "longitude": SPOT[1] + 0.0002, "address": "제주", "axis": "impact", "axis_label": "일정이 가장 덜 밀리는 곳"}]}

    monkeypatch.setattr(dining_alternatives, "near", near)
    kakao = Kakao()
    review, item = _review(label="식당")
    got = _alternatives(ledger_world, review, item, kakao)
    names = [c["place"]["name"] for c in got["candidates"]]
    assert "team_ranked" in got["notes"], got["notes"]
    assert names[0] == "팀이고른식당" and seen["meal"] is True, names
    assert kakao.asked == []                                          # 팀이 답했으면 지도로 채우지 않는다(후보는 팀이)


def test_when_the_team_cannot_answer_the_ledger_fallback_still_leaves_out_desserts(ledger_world, monkeypatch):
    monkeypatch.setattr(dining_alternatives, "near", lambda *a, **k: None)
    review, item = _review(label="식당")
    got = _alternatives(ledger_world, review, item, Kakao())
    names = [c["place"]["name"] for c in got["candidates"]]
    assert "team_ranked" not in got["notes"]
    assert "원장한식당" in names and "원장디저트집" not in names, names        # 원장 요리 갈래 「카페디저트」는 끼니가 아니다
    assert "지도디저트카페" not in names, names                             # 카카오 카페(CE7)도 끼니가 아니다


def test_when_the_team_finds_nothing_the_local_picker_and_the_map_fill_with_restaurants_only(ledger_world, monkeypatch):
    """팀이 「둘레에 없다」고 답하면(빈 목록) 이름 없는 식사는 자체 고르기(원장) → 지도로 채운다 — 음식점만."""
    monkeypatch.setattr(dining_alternatives, "near", lambda *a, **k: {"alternatives": []})
    kakao = Kakao()
    review, item = _review(label="식당")
    got = _alternatives(ledger_world, review, item, kakao)
    names = [c["place"]["name"] for c in got["candidates"]]
    assert kakao.asked and "지도백반집" in names and "원장한식당" in names, names
    assert "지도디저트카페" not in names and "원장디저트집" not in names, names


def test_a_cafe_line_still_gets_cafes(ledger_world, monkeypatch):
    """끼니가 아닌 카페 일정은 카페가 맞다 — 거르지 않는다."""
    monkeypatch.setattr(dining_alternatives, "near", lambda *a, **k: {"alternatives": []})
    review, item = _review(title="카페", meal=None, label="카페")
    got = _alternatives(ledger_world, review, item, Kakao())
    assert "지도디저트카페" in [c["place"]["name"] for c in got["candidates"]]


def test_auto_fix_route_restaurants_leave_out_cafes_for_a_meal(monkeypatch):
    """자동 추천의 「앞뒤 일정 근처 식당」(`_route_restaurants`) — 실측에서 점심에 디저트카페가 들어간 길."""
    monkeypatch.setattr(candidates, "_ledger_places", lambda *a, **k: [])
    review, item = _review()
    prev, nxt = review["items"][0], review["items"][2]
    pool = autofix._route_restaurants(None, "t", item, [], prev, nxt, Kakao())
    assert {p["name"] for p in pool} == {"지도백반집"}                    # 앞 · 뒤 일정 둘레에서 각각 찾은 같은 이름의 음식점
    cafe_item = {**item, "title": "카페", "parts": {"meal": None}}
    assert "지도디저트카페" in [p["name"] for p in autofix._route_restaurants(None, "t", cafe_item, [], prev, nxt, Kakao())]
