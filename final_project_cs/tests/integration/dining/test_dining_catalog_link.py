"""등록 전 확인 화면의 원장 연결(`ledger._catalog_uid`) — 이름이 같아도 **다른 곳의 가게와 잇지 않는다**. `[2026-10-14]`

연결 정답셋(`eval/reports/2026-10-14_dining_link.md`)에서 확인 화면 길이 dev 7 · holdout 2 건을 다른 가게와 이었다 —
이름 찾기가 좌표를 안 봐서 1.5~3km 떨어진 같은 이름 가게와 잇고(「운종가」 · 「텐바」), 지점 이름으로 「확인 필요」로 찾은
체인 가게(「메가MGC커피 종로점」 → 「관악구청점」)도 그 가게의 관광공사 번호로 이었다. 다른 가게의 영업시간으로 판정하게 된다.
"""
from __future__ import annotations

from app.domains.travel_ops.instances.dining.ledger import _catalog_uid
from tests.integration.dining.test_dining_find_by_name import _name, shop  # noqa: F401 — 픽스처

LAT, LNG = 37.5777, 126.9715


def test_same_name_far_away_is_not_this_shop(conn, shop):  # noqa: F811
    name = _name()
    shop(name, lat=LAT, lng=LNG)
    assert _catalog_uid(conn, None, {"name": name, "latitude": LAT + 0.018, "longitude": LNG}) is None   # 약 2km


def test_same_name_nearby_is_this_shop(conn, shop):  # noqa: F811
    name = _name()
    uid, _ = shop(name, lat=LAT, lng=LNG)
    assert _catalog_uid(conn, None, {"name": name, "latitude": LAT + 0.0009, "longitude": LNG}) == uid  # 약 100m


def test_without_coordinates_the_unique_exact_name_still_links(conn, shop):  # noqa: F811
    name = _name()
    uid, _ = shop(name, lat=LAT, lng=LNG)
    assert _catalog_uid(conn, None, {"name": name}) == uid


def test_a_chain_branch_elsewhere_is_not_linked_through_its_tour_id(conn, shop):  # noqa: F811
    name = _name()
    shop(f"{name} 관악구청점", lat=LAT, lng=LNG)
    assert _catalog_uid(conn, None, {"name": f"{name} 종로점", "latitude": LAT + 0.05, "longitude": LNG}) is None


def test_a_branch_label_on_the_same_spot_is_the_same_shop(conn, shop):  # noqa: F811
    name = _name()
    uid, _ = shop(name, lat=LAT, lng=LNG)
    assert _catalog_uid(conn, None, {"name": f"{name} 본점", "latitude": LAT + 0.0003, "longitude": LNG}) == uid


def test_without_coordinates_a_branch_guess_is_not_linked(conn, shop):  # noqa: F811
    name = _name()
    shop(f"{name} 관악구청점", lat=LAT, lng=LNG)
    assert _catalog_uid(conn, None, {"name": f"{name} 종로점"}) is None
