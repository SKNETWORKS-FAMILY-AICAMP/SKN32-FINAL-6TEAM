# -*- coding: utf-8 -*-
"""후보 고르기가 **관광공사 분류 나무**로 비슷한 곳을 고른다. `[2026-10-07 사용자 지시]`

사용자: 「분류 값이 비었다고 사람이 갑자기 약국을 가지는 않는다 — 최대한 비슷한 카테고리로 가게 해야지」 ·
「광장시장 12:30 인데 다른 식사 일정이 없으면 거기서 밥을 먹는 것이다 — 대체가 올리브영이면 안 된다」.
`place_catalog.raw_json` 의 `lclsSystm1·2·3`(대·중·소분류)이 나무다 — 경복궁 = 역사(HS) › 고궁(HS01) · 광장시장 = 쇼핑(SH) › 시장(SH06) · 약국 · 편의점 = 쇼핑(SH) › 전문매장(SH04).

★지키려는 것
 ①같은 소분류 → 같은 중분류 → 같은 대분류 순, 같은 단계 안에서는 가까운 순. **다른 대분류(약국 · 박물관)는 절대 안 나온다**
 ②원래 장소의 분류는 관광공사 번호 → 같은 이름 순으로 찾고, 이름이 여러 곳에 걸치면 **같은 단계까지만** 쓴다(대분류까지 갈리면 모른다)
 ③활동 일정이 **시장**이고 끼니 시간이며 앞뒤 2시간 안에 다른 식사 일정이 없으면 — 같은 중분류(시장)와 식당만 후보다(`meal_inferred`). 식사 일정이 있으면 그냥 시장 가지
 ④후보에는 맞은 단계(`similarity`)가 실린다 · 순위는 맞는 곳 → 비슷한 정도 → 거리 순이다

재현:

    python -m pytest tests/e2e/test_intake_similar_places.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.intake import candidates
from app.domains.travel_ops.components.intake.candidates import _eats_there, _original_class, _similar_places
from app.infrastructure.db.session import get_connection

from .test_intake_review import rv  # noqa: F401
from .test_trip_api import api  # noqa: F401

NOW = datetime(2030, 1, 5, 9, 0, tzinfo=timezone(timedelta(hours=9)))
PALACE = (37.5796, 126.9770)
MARKET = (37.5700, 126.9990)


def _row(rv, cid, ctype, title, lat, lon, l1, l2, l3):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, title, address, latitude, longitude, raw_json) "
                    "VALUES (%s,'tour_api',%s,%s,%s,'서울특별시 종로구 사직로 1',%s,%s,%s) ON CONFLICT DO NOTHING",
                    (rv["tenant"], cid, ctype, title, lat, lon,
                     json.dumps({"lclsSystm1": l1, "lclsSystm2": l2, "lclsSystm3": l3}, ensure_ascii=False)))


@pytest.fixture()
def palace_world(rv):  # noqa: F811
    _row(rv, "940001", "12", "경복궁", *PALACE, "HS", "HS01", "HS010100")            # 원래 장소(목록에도 있다)
    _row(rv, "940002", "12", "창덕궁", 37.5794, 126.9910, "HS", "HS01", "HS010100")   # 같은 소분류 — 가장 멀다
    _row(rv, "940003", "12", "탑골공원", 37.5714, 126.9882, "HS", "HS02", "HS020100")  # 같은 대분류 · 다른 중분류 — 더 가깝다
    _row(rv, "940004", "12", "역사 마을", 37.5800, 126.9780, "HS", "HS03", "HS030100")  # 같은 대분류 · 다른 중분류 — 가장 가깝다
    _row(rv, "940005", "38", "우정약국 종로", 37.5797, 126.9771, "SH", "SH04", "SH040100")  # 쇼핑 — 가장 가깝다
    _row(rv, "940006", "14", "가까운 박물관", 37.5798, 126.9772, "VE", "VE07", "VE070100")   # 다른 대분류 — 가깝다
    yield rv


def _names(rows):
    return [row["name"] for row in rows]


def test_similar_places_go_small_branch_first_then_wider_and_never_leave_the_big_branch(palace_world):
    with get_connection() as conn:
        found = _similar_places(conn, palace_world["tenant"], PALACE, ["HS", "HS01", "HS010100"], NOW)
    names = _names(found)
    assert names[0] in ("경복궁", "창덕궁")                                                    # 같은 소분류가 맨 앞(자기 자신은 호출한 쪽이 뺀다)
    assert set(names[:2]) == {"경복궁", "창덕궁"} and {"탑골공원", "역사 마을"} == set(names[2:])
    assert [row["similarity"] for row in found] == [3, 3, 1, 1]                              # 소분류 둘 다 먼저 · HS02 · HS03 은 대분류만 같다
    assert "우정약국 종로" not in names and "가까운 박물관" not in names                          # 다른 대분류(쇼핑 · 문화시설)는 가장 가까워도 안 나온다


def test_the_similarity_levels_are_carried_and_ordered(palace_world):
    with get_connection() as conn:
        found = _similar_places(conn, palace_world["tenant"], PALACE, ["HS", "HS01", "HS010100"], NOW)
    levels = {row["name"]: row["similarity"] for row in found}
    assert levels["창덕궁"] == 3 and levels["탑골공원"] == 1 and levels["역사 마을"] == 1             # HS01 이 아닌 곳은 대분류만 같다
    ordered = [row["similarity"] for row in found]
    assert ordered == sorted(ordered, reverse=True)                                         # 높은 단계가 앞이다


def test_a_minimum_level_drops_the_widest_branch(palace_world):
    with get_connection() as conn:
        found = _similar_places(conn, palace_world["tenant"], PALACE, ["HS", "HS01", "HS010100"], NOW, min_level=2)
    assert set(_names(found)) == {"경복궁", "창덕궁"}                                           # 같은 중분류까지만


def test_the_original_class_is_found_by_content_id_then_by_name_and_shared_prefix_only(palace_world):
    tenant = palace_world["tenant"]
    _row(palace_world, "940010", "12", "겹치는 이름", 37.58, 126.98, "HS", "HS01", "HS010100")
    _row(palace_world, "940011", "12", "겹치는 이름", 37.59, 126.99, "HS", "HS02", "HS020100")      # 같은 이름 · 다른 중분류
    _row(palace_world, "940012", "38", "갈리는 이름", 37.58, 126.98, "HS", "HS01", "HS010100")
    _row(palace_world, "940013", "38", "갈리는 이름", 37.59, 126.99, "SH", "SH04", "SH040100")      # 같은 이름 · 다른 대분류
    with get_connection() as conn:
        by_id = _original_class(conn, tenant, {"name": "아무 이름", "content_id": "940001"})
        by_name = _original_class(conn, tenant, {"name": "경복궁"})
        shared = _original_class(conn, tenant, {"name": "겹치는 이름"})
        split = _original_class(conn, tenant, {"name": "갈리는 이름"})
        nothing = _original_class(conn, tenant, {"name": "목록에 없는 곳"})
        given_only = _original_class(conn, tenant, {"name": "목록에 없는 곳", "content_type_id": "14"})
    assert by_id["lcls"] == ["HS", "HS01", "HS010100"] and by_id["by"] == "content_id"            # 번호가 이름보다 먼저다
    assert by_name["lcls"] == ["HS", "HS01", "HS010100"] and by_name["by"] == "name"
    assert shared["lcls"] == ["HS", None, None]                                             # 같은 단계(대분류)까지만
    assert split is None or split["lcls"] is None                                           # 대분류까지 갈리면 나무는 모른다
    assert nothing is None
    assert given_only == {"content_type": "14", "lcls": None, "by": "given", "grade": None}                  # 번호만 알면 번호만


# ── 끼니 시간의 시장 ───────────────────────────────────────────────
def _item(item_id, kind, start, date="2030-01-05"):
    return {"id": item_id, "date": date, "starts_at": start, "ends_at": start, "kind": kind, "title": item_id}


MARKET_CLASS = {"content_type": "38", "lcls": ["SH", "SH06", "SH060200"], "by": "name"}


@pytest.mark.parametrize("start,expect", [("12:30", True), ("11:30", True), ("14:30", True), ("08:30", True), ("19:00", True),
                                          ("10:30", False), ("15:30", False), ("16:00", False)])
def test_a_market_in_a_mealtime_is_read_as_eating_there(start, expect):
    market = _item("m", "activity", start)
    assert _eats_there([market], market, MARKET_CLASS) is expect


def test_another_meal_nearby_or_another_kind_of_place_turns_it_off():
    market = _item("m", "activity", "12:30")
    assert _eats_there([market, _item("lunch", "dining", "13:30")], market, MARKET_CLASS) is False        # 앞뒤 2시간 안의 식사 일정
    assert _eats_there([market, _item("dinner", "dining", "19:00")], market, MARKET_CLASS) is True         # 먼 식사는 상관없다
    assert _eats_there([market, _item("other-day", "dining", "12:30", "2030-01-06")], market, MARKET_CLASS) is True
    assert _eats_there([market], market, {"content_type": "12", "lcls": ["HS", "HS01", "HS010100"], "by": "name"}) is False   # 시장이 아니다
    assert _eats_there([market], market, None) is False
    assert _eats_there([_item("m", "dining", "12:30")], _item("m", "dining", "12:30"), MARKET_CLASS) is False  # 이미 식사 일정


@pytest.fixture()
def market_world(rv):  # noqa: F811
    _row(rv, "950001", "38", "광장시장", *MARKET, "SH", "SH06", "SH060200")
    _row(rv, "950002", "38", "남대문시장", 37.5590, 126.9770, "SH", "SH06", "SH060200")
    _row(rv, "950003", "38", "올리브영 종로", 37.5701, 126.9991, "SH", "SH04", "SH040100")         # 쇼핑 전문매장 — 가장 가깝다
    _row(rv, "950004", "38", "우정약국", 37.5702, 126.9992, "SH", "SH04", "SH040100")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) "
                    "VALUES (%s,'시장 빈대떡집','dining',37.5703,126.9993,'dining_ledger','{\"source\": \"dining_ledger\"}')", (rv["tenant"],))
    yield rv
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM places WHERE tenant_id=%s AND source_name='dining_ledger'", (rv["tenant"],))


def _review(extra_items=()):
    market_place = {"name": "광장시장", "latitude": MARKET[0], "longitude": MARKET[1], "kind": "activity", "source": "tour_api",
                    "content_id": "950001", "content_type_id": "38", "ref": "tour:950001"}
    item = {**_item("market", "activity", "12:30"), "ends_at": "13:30", "title": "광장시장", "place": market_place, "place_state": "found", "parts": None}
    others = [{**_item(i["id"], i["kind"], i["starts_at"]), "ends_at": i["starts_at"], "place": None, "place_state": "none", "parts": None} for i in extra_items]
    return {"items": [item, *others]}, item


def test_a_market_at_lunch_with_no_other_meal_offers_markets_and_restaurants_never_drugstores(market_world):
    review, item = _review()
    with get_connection() as conn:
        got = candidates.alternatives(conn, tenant_id=market_world["tenant"], review=review, item=item, kakao=None, use_engine=False, now=NOW)
    names = [c["place"]["name"] for c in got["candidates"]]
    assert "meal_inferred" in got["notes"]
    assert "남대문시장" in names and "시장 빈대떡집" in names                                    # 시장과 식당 — 거기서 먹는다
    assert "올리브영 종로" not in names and "우정약국" not in names                             # 가장 가까워도 쇼핑 전문매장은 안 나온다
    kinds = {c["place"]["name"]: c["place"]["kind"] for c in got["candidates"]}
    assert kinds["시장 빈대떡집"] == "dining" and kinds["남대문시장"] == "activity"               # 식당 후보는 식당으로 판정된다
    by_name = {c["place"]["name"]: c for c in got["candidates"]}
    assert by_name["남대문시장"]["similarity"] == 3 and by_name["시장 빈대떡집"]["similarity"] is None


def test_with_a_meal_already_planned_a_market_stays_a_market_branch(market_world):
    review, item = _review(extra_items=[{"id": "lunch", "kind": "dining", "starts_at": "12:00"}])
    with get_connection() as conn:
        got = candidates.alternatives(conn, tenant_id=market_world["tenant"], review=review, item=item, kakao=None, use_engine=False, now=NOW)
    names = [c["place"]["name"] for c in got["candidates"]]
    assert "meal_inferred" not in got["notes"] and "시장 빈대떡집" not in names                  # 식사 일정이 따로 있으면 식당을 권하지 않는다
    assert names[0] == "남대문시장"                                                          # 같은 소분류(시장)가 먼저, 쇼핑 전문매장은 그 뒤(같은 대분류)
    assert "올리브영 종로" in names and names.index("남대문시장") < names.index("올리브영 종로")      # 더 가까워도 같은 대분류 안의 다른 가지는 뒤다
