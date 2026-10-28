# -*- coding: utf-8 -*-
"""전체 자동 추천 — 일정상 무리한 식사는 **앞뒤 일정 근처 식당**으로, 그래도 안 되면 다음 일정을 민다. `[2026-10-13 사용자 지시]`

☆전에는 식사가 앞뒤 이동에 못 맞으면 「맞출 수 없음」(`no_fitting_time`)으로 그대로 두었다 — 「10:00~12:00 국립중앙박물관 → 12:10 광장시장 점심
  → 13:10 전쟁기념관」에서 용산 근처 식당이 있어도 권하지 않았다(대체 후보를 원래 식당 둘레에서만 찾았다).
★순서: ① 지금 곳에서 시각을 맞춘다(전과 같다) ② 앞 · 뒤 일정 근처 식당(원장 · 카카오)을 돌아가는 거리가 짧은 순으로 맞춰 본다
  ③ 그래도 안 맞으면 다음 일정에 묶지 않고 머무는 시간을 지킨다 — 다음 일정은 그 뒤에 늦음으로 다시 맞춰진다. **식사를 「맞출 수 없음」으로 두지 않는다.**
★계산만 한다 — 모델(LLM)을 부르지 않는다. 고정 · 예약한 식사는 그대로다.
"""
from __future__ import annotations

from .test_intake_review import Kakao, Tour, _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_10_15 = reldate.day("2026-10-15")


class SeoulTour(Tour):
    PLACES = {**Tour.PLACES,
              "국립중앙박물관": ("129703", "14", 37.5240, 126.9803),      # 용산
              "전쟁기념관": ("126539", "14", 37.5365, 126.9772)}           # 용산


class NearKakao(Kakao):
    """근처 찾기(거리순)에 답한다 — 용산 근처 음식점 둘 · 광장시장 근처 음식점 하나."""

    YONGSAN = [{"id": "y1", "name": "용산 국밥집", "category": "음식점 > 한식", "category_group": "FD6",
                "address": "서울 용산구 서빙고로 1", "latitude": 37.5248, "longitude": 126.9810},
               {"id": "y2", "name": "이촌 칼국수", "category": "음식점 > 한식", "category_group": "FD6",
                "address": "서울 용산구 이촌로 2", "latitude": 37.5230, "longitude": 126.9760}]
    MARKET = [{"id": "m1", "name": "순희네빈대떡", "category": "음식점 > 한식", "category_group": "FD6",
               "address": "서울 종로구 종로32길 5", "latitude": 37.5701, "longitude": 126.9994}]

    def __init__(self, pool=None):
        super().__init__()
        self.pool = self.YONGSAN + self.MARKET if pool is None else pool

    def search(self, query, size=5, near=None, **kw):
        self.asked.append((query, near))
        if near is not None:
            from app.domains.travel_ops.components.intake.places import distance_m

            return sorted(self.pool, key=lambda h: distance_m(near[0], near[1], h["latitude"], h["longitude"]))
        return super().search(query, size=size, near=near)


TIGHT = f"{D_2026_10_15}\n10:00~12:00 국립중앙박물관 관람\n12:10~13:00 광장시장 점심\n13:10~15:00 전쟁기념관 관람"
ROOMY = f"{D_2026_10_15}\n10:00~11:30 국립중앙박물관 관람\n11:40~13:00 광장시장 점심\n16:00 경복궁 관람"


def _autofix(client, headers, view):
    got = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers,
                      json={"revision": view["revision"], "dry_run": True})
    assert got.status_code == 200, got.text
    return got.json()


def _change(body, title):
    return next((c for c in body["changed"] if c["title"] == title), None)


def test_a_meal_with_no_time_left_moves_to_a_restaurant_near_the_route(rv):
    """☆회귀 — 광장시장까지 오가면 점심 자리가 없다 → 박물관 · 전쟁기념관 근처 식당으로 바꾼다(전에는 「맞출 수 없음」)."""
    client, _, _ = _client(tour=SeoulTour(), kakao=NearKakao())
    headers = _key(client)
    body = _autofix(client, headers, _send(client, headers, TIGHT))
    meal = _change(body, "광장시장")
    assert meal is not None and meal["reason"] == "place_and_time"
    assert meal["to"]["place"]["name"] == "용산 국밥집"                       # 돌아가는 거리가 가장 짧은 곳
    assert "근처" in meal["note"]
    assert not [k for k in body["kept"] if k["title"] == "광장시장"]           # ★「맞출 수 없음」으로 두지 않는다
    assert meal["to"]["starts_at"] >= "12:00" and meal["to"]["ends_at"] <= "13:10"


def test_a_meal_that_fits_by_time_keeps_its_place(rv):
    """시각만 미뤄 맞으면 장소는 그대로다(전과 같다)."""
    client, _, _ = _client(tour=SeoulTour(), kakao=NearKakao())
    headers = _key(client)
    body = _autofix(client, headers, _send(client, headers, ROOMY))
    meal = _change(body, "광장시장")
    assert meal is not None and meal["reason"] == "time"
    assert meal["to"]["place"]["name"] == meal["from"]["place"]["name"]


def test_with_no_restaurant_anywhere_the_meal_keeps_its_time_and_the_next_stop_is_pushed(rv):
    """근처 식당이 하나도 없다 — 그래도 「맞출 수 없음」으로 두지 않는다. 머무는 시간을 지키고 다음 일정을 뒤로 민다."""
    client, _, _ = _client(tour=SeoulTour(), kakao=NearKakao(pool=[]))
    headers = _key(client)
    body = _autofix(client, headers, _send(client, headers, TIGHT))
    meal = _change(body, "광장시장")
    assert meal is not None and not [k for k in body["kept"] if k["title"] == "광장시장"]
    assert "다음 일정" in meal["note"]
    after = _change(body, "전쟁기념관 관람")
    assert after is not None and after["to"]["starts_at"] > "13:10"          # 다음 일정이 밀렸다
