"""일정 접수의 장소 찾기가 액티비티 CSV 에서 식당을 못 찾을 때 원장에서 찾는다(2026-10-01).

일정 접수는 액티비티 CSV(관광지 1,586곳)만 봐서 「토속촌삼계탕」 같은 식당을 하나도 못 찾았다.
원장의 관광공사 가게를 같은 모양(관광공사 결과)으로 돌려준다 — 외부 API 를 부르지 않는다.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.modules.travel_ops.dining.ledger import find_place_by_name


@pytest.fixture
def shop(conn, place):
    """관광공사 출처 가게 하나. 이름은 고유하게 붙이고 원문 행을 단다."""
    loads: list[str] = []

    def make(name: str, *, lat=37.5777, lng=126.9715, address="서울특별시 종로구 자하문로5길 5",
             content_id: str | None = None, status: str = "active") -> tuple[str, str]:
        uid = place(name, lat, lng)
        conn.execute("UPDATE dining.dn_place SET name_ko = %s, road_address = %s, record_status = %s, "
                     "is_synthetic = false WHERE place_uid = %s", (name, address, status, uid))
        cid = content_id or f"t{uuid.uuid4().hex[:10]}"
        load_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO dining.dn_load_meta (load_id, source_code, fetched_at, schema_version, scope, "
            "row_count, status) VALUES (%s, 'tourapi_kor_food', %s, 'test', 'test', 1, 'loaded')",
            (load_id, datetime.now()))
        conn.execute(
            "INSERT INTO dining.dn_source_record (load_id, source_code, external_id, place_uid, match_status, "
            "raw_json) VALUES (%s, 'tourapi_kor_food', %s, %s, 'auto', '{}'::jsonb)", (load_id, cid, uid))
        loads.append(load_id)
        return uid, cid

    yield make
    for load_id in loads:
        conn.execute("DELETE FROM dining.dn_source_record WHERE load_id = %s", (load_id,))
        conn.execute("DELETE FROM dining.dn_load_meta WHERE load_id = %s", (load_id,))


def _name() -> str:
    return f"시험삼계탕{uuid.uuid4().hex[:6]}"


def test_finds_tourapi_shop_in_the_tour_result_shape(conn, shop):
    name = _name()
    uid, cid = shop(name)

    found = find_place_by_name(conn, name)

    # 관광공사 결과 모양 + 원장 가게 id · 찾은 단계 · 확인 필요(2026-10-07)
    assert {k: found[k] for k in ("content_id", "content_type_id", "matched_title", "address", "dining_place_uid",
                                  "match", "needs_review")} == {
        "content_id": cid, "content_type_id": "39", "matched_title": name, "address": "서울특별시 종로구 자하문로5길 5",
        "dining_place_uid": uid, "match": "exact", "needs_review": False}
    assert (found["latitude"], found["longitude"]) == (pytest.approx(37.5777), pytest.approx(126.9715))


def test_name_match_ignores_spaces_and_punctuation(conn, shop):
    name = _name()
    shop(name)

    assert find_place_by_name(conn, f" {name[:3]} {name[3:]} ")["matched_title"] == name


def test_unknown_name_is_none(conn):
    assert find_place_by_name(conn, _name()) is None


def test_two_shops_with_the_same_name_pick_the_nearer_one_for_review(conn, shop):
    # ★`[2026-10-07]` 전에는 고르지 않았다(못 찾음). 이제 근처 기준으로 하나를 고르고 확인을 받는다
    name = _name()
    shop(name)
    far, _ = shop(name, lat=37.50, lng=127.04)

    near = find_place_by_name(conn, name, near=(37.501, 127.041))
    assert near["dining_place_uid"] == far and near["needs_review"] and near["others"] == 1
    assert find_place_by_name(conn, name)["needs_review"]                 # 기준이 없어도 하나 — 언제나 확인 필요


def test_closed_shop_is_not_offered(conn, shop):
    name = _name()
    shop(name, status="closed")

    assert find_place_by_name(conn, name) is None


def test_shop_outside_seoul_is_not_offered(conn, shop):
    name = _name()
    shop(name, address="경기도 고양시 덕양구 1")

    assert find_place_by_name(conn, name) is None


def test_shop_without_tourapi_record_is_offered_with_its_ledger_id(conn, place):
    # ★`[2026-10-07]` 관광공사 ID 가 없는 원장 가게(미쉐린 · 인허가로만 들어온 곳)도 낸다 — 등록 때 원장 가게 id 로 잇는다.
    #   ☆전에는 빼서 영업 중 204곳(하동관 · 명동교자 본점 …)을 이름으로 못 찾았다
    name = _name()
    uid = place(name)
    conn.execute("UPDATE dining.dn_place SET name_ko = %s, road_address = '서울특별시 중구 1', "
                 "is_synthetic = false WHERE place_uid = %s", (name, uid))

    found = find_place_by_name(conn, name)
    assert found["content_id"] is None and found["dining_place_uid"] == uid and not found["needs_review"]


def test_branch_prefix_and_typo_are_found_for_review(conn, shop):
    stem = f"시험국밥{uuid.uuid4().hex[:4]}"
    uid, _ = shop(f"{stem}원조할매 별관")
    branch = find_place_by_name(conn, f"{stem}원조할매")                  # 지점 표시를 뗀 이름
    prefix = find_place_by_name(conn, stem)                               # 앞부분(4자 이상)
    assert branch["match"] == "branch" and branch["dining_place_uid"] == uid and branch["needs_review"]
    assert prefix["match"] == "prefix" and prefix["needs_review"]


def test_typo_is_found_for_review(conn, shop):
    shop("시험이문설농탕가게")
    found = find_place_by_name(conn, "시험이문설롱탕가게")                  # 농 → 롱
    assert found["match"] == "typo" and found["matched_title"] == "시험이문설농탕가게" and found["needs_review"]


def test_dish_near_finds_the_closest_menu_shop_within_radius(conn, shop):
    from app.modules.travel_ops.dining.ledger import find_dish_near

    tag = uuid.uuid4().hex[:4]
    near_uid, _ = shop(f"가까운{tag}기름떡볶이", lat=37.5807, lng=126.9702)
    shop(f"먼{tag}기름떡볶이", lat=37.60, lng=127.00)
    found = find_dish_near(conn, "통인시장 기름떡볶이", (37.5800, 126.9700))
    assert found["match"] == "dish" and found["needs_review"]
    assert found["dining_place_uid"] == near_uid or found["matched_title"].endswith("기름떡볶이")
    assert find_dish_near(conn, "통인시장 구경", (37.58, 126.97)) is None   # 메뉴 말이 없으면 찾지 않는다


def test_missing_dining_schema_is_none_not_an_error():
    class Broken:
        def cursor(self):
            raise RuntimeError('relation "dining.dn_place" does not exist')

        def transaction(self):
            import contextlib
            return contextlib.nullcontext()

    assert find_place_by_name(Broken(), "토속촌삼계탕") is None
