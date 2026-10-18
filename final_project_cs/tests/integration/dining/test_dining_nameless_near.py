# -*- coding: utf-8 -*-
"""가게 이름 없는 식사의 원장 후보(`instances/dining/review_alternatives.near_pool`) — 실제 원장 SQL. `[2026-10-18 사용자 지시]`

★한 지점 둘레의 원장 식당 중 ①폐업 아님 ②그 시각 닫힘으로 확인되지 않음 ③(끼니면) 요리 갈래 「카페디저트」 아님 ④반경 안.
  영업이 확인된 곳이 먼저, 그다음 가까운 순. 영업시간을 모르는 곳은 빼지 않고 뒤에 둔다(모르는 것을 닫힘으로 짓지 않는다).
"""
from __future__ import annotations

from datetime import datetime

from app.domains.travel_ops.instances.dining.review_alternatives import near_pool

from tests.integration.dining.test_dining_judgment import add_hours

POINT = (33.4500, 126.5600)
START = datetime.fromisoformat("2026-09-21T12:00:00+09:00")       # 월요일 — add_hours 의 요일 1
END = datetime.fromisoformat("2026-09-21T13:00:00+09:00")
M = 1 / 111_000                                                    # 1m 의 위도 차


def _cuisine(conn, uid, category):
    conn.execute("UPDATE dining.dn_place SET category=%s, category_method='manual' WHERE place_uid=%s", (category, uid))


def test_open_restaurants_first_and_no_desserts_closed_or_far_places(conn, place):
    open_food = place("열린한식", lat=POINT[0] + 100 * M, lng=POINT[1])
    dessert = place("디저트집", lat=POINT[0] + 50 * M, lng=POINT[1])
    shut_down = place("폐업집", lat=POINT[0] + 30 * M, lng=POINT[1])
    later = place("저녁에만", lat=POINT[0] + 80 * M, lng=POINT[1])
    unknown = place("모르는집", lat=POINT[0] + 120 * M, lng=POINT[1])
    far = place("먼집", lat=POINT[0] + 3000 * M, lng=POINT[1])
    _cuisine(conn, open_food, "한식")
    _cuisine(conn, dessert, "카페디저트")
    conn.execute("UPDATE dining.dn_place SET record_status='closed' WHERE place_uid=%s", (shut_down,))
    for uid in (open_food, dessert, shut_down, far):
        add_hours(conn, uid, 1, [(660, 1320, None)])
    add_hours(conn, later, 1, [(1020, 1320, None)])                  # 17:00 에 연다 — 12시에는 닫힘
    got = near_pool(conn, POINT, START, END, meal=True, radius_m=2000)
    uids = [row["place_uid"] for row in got]
    assert uids[:2] == [open_food, unknown], got                     # 영업 확인 → 모름 순
    assert dessert not in uids and shut_down not in uids and later not in uids and far not in uids
    assert got[0]["open_state"] is True and got[1]["open_state"] is None
    assert 90 < got[0]["distance_m"] < 110


def test_a_cafe_line_keeps_desserts(conn, place):
    dessert = place("디저트집", lat=POINT[0] + 50 * M, lng=POINT[1])
    _cuisine(conn, dessert, "카페디저트")
    add_hours(conn, dessert, 1, [(660, 1320, None)])
    assert dessert in [row["place_uid"] for row in near_pool(conn, POINT, START, END, meal=False, radius_m=2000)]


def test_the_radius_is_kept(conn, place):
    near_one = place("가까운집", lat=POINT[0] + 300 * M, lng=POINT[1])
    farther = place("조금먼집", lat=POINT[0] + 900 * M, lng=POINT[1])
    for uid in (near_one, farther):
        add_hours(conn, uid, 1, [(660, 1320, None)])
    uids = [row["place_uid"] for row in near_pool(conn, POINT, START, END, meal=True, radius_m=500)]
    assert near_one in uids and farther not in uids
