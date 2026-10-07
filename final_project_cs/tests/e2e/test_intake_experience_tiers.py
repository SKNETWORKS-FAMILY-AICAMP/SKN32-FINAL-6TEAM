# -*- coding: utf-8 -*-
"""후보 고르기의 **단계** — 같은 종류 → 비슷한 경험 → (취향 추천은 아직 없다). 단계 값(`basis`)과 사실로 된 이유(`reason`). `[2026-10-07 사용자]`

사용자: 「유사한 대안이 없을 수가 있나 — 경복궁을 못 가면 공원을 간다던가 할 거 아니냐 … 추천 이유를 잘 쓰면 된다」.

★지키려는 것
 ①같은 종류(분류 나무)가 모자라면 **같은 경험 갈래**(야외에서 걷고 둘러보기 · 실내에서 전시 보기)의 곳이 이어진다 — 쇼핑 · 약국 · 박물관(다른 갈래)은 안 나온다
 ②같은 종류가 이미 있으면 그것이 **먼저**다(더 멀어도) · 비슷한 경험은 그 뒤
 ③후보마다 `basis`(same_kind · similar_experience · meal_inferred · None)와 `reason`(사실만 — 아는 값만 적고 모르면 쓰지 않거나 모른다고 쓴다)이 실린다
 ④둘 다 없으면 지어내지 않고 `no_alternative` 로 알린다
 ⑤거기서 밥을 먹는 일정(끼니 시간의 시장)은 시장만 셋이 아니라 **식당이 둘까지** 보인다

재현:

    python -m pytest tests/e2e/test_intake_experience_tiers.py -v
"""
from __future__ import annotations

import pytest

from app.domains.travel_ops.components.intake import candidates
from app.domains.travel_ops.components.intake.candidates import EXPERIENCE_GROUPS, _experience_of, _reason
from app.infrastructure.db.session import get_connection

from .test_intake_review import rv  # noqa: F401
from .test_intake_similar_places import MARKET, NOW, PALACE, _item, _review, _row, market_world  # noqa: F401
from .test_trip_api import api  # noqa: F401


def _palace_review():
    place = {"name": "경복궁", "latitude": PALACE[0], "longitude": PALACE[1], "kind": "activity", "source": "places",
             "content_id": "960001", "content_type_id": None, "ref": "place:abc"}
    item = {**_item("palace", "activity", "10:30"), "ends_at": "12:00", "title": "경복궁", "place": place, "place_state": "found", "parts": None}
    return {"items": [item]}, item


def _alternatives(world, review, item):
    with get_connection() as conn:
        return candidates.alternatives(conn, tenant_id=world["tenant"], review=review, item=item, kakao=None, use_engine=False, now=NOW)


@pytest.fixture()
def park_world(rv):  # noqa: F811
    """경복궁(역사 › 고궁)에 같은 종류가 없고, 공원 · 둘레길 · 약국 · 박물관만 있다."""
    _row(rv, "960001", "12", "경복궁", *PALACE, "HS", "HS01", "HS010100")
    _row(rv, "960002", "14", "광화문 어린이공원", 37.5760, 126.9760, "VE", "VE03", "VE030100")
    _row(rv, "960003", "14", "북악 둘레길", 37.5850, 126.9700, "VE", "VE04", "VE040100")
    _row(rv, "960004", "38", "우정약국 종로", 37.5797, 126.9771, "SH", "SH04", "SH040100")          # 가장 가깝다 — 쇼핑
    _row(rv, "960005", "14", "가까운 박물관", 37.5798, 126.9772, "VE", "VE07", "VE070100")         # 다른 갈래(실내 전시)
    yield rv


def test_without_the_same_kind_the_palace_continues_with_outdoor_walks_and_never_drugstores_or_museums(park_world):
    review, item = _palace_review()
    got = _alternatives(park_world, review, item)
    names = [c["place"]["name"] for c in got["candidates"]]
    assert set(names) == {"광화문 어린이공원", "북악 둘레길"}, got                                # 공원 · 둘레길 — 야외에서 걷고 둘러보기
    assert "similar_experience" in got["notes"] and "no_alternative" not in got["notes"]
    assert {c["basis"] for c in got["candidates"]} == {"similar_experience"} and all(c["similarity"] is None for c in got["candidates"])
    for c in got["candidates"]:
        assert c["experience"] == "outdoor_walk"
        assert c["reason"].startswith("경복궁와 같은 종류는 가까이에 마땅한 곳이 없어, 야외에서 걷고 둘러보기을 하는 곳 중 가까운 곳을 골랐어요"), c["reason"]
        assert f"{c['distance_m']}m" in c["reason"]                                            # 아는 값(거리)만 적는다


def test_the_same_kind_comes_first_even_when_farther_and_the_experience_fills_after(park_world):
    _row(park_world, "960006", "12", "창덕궁", 37.5794, 126.9910, "HS", "HS01", "HS010100")    # 같은 소분류 — 공원보다 멀다
    review, item = _palace_review()
    got = _alternatives(park_world, review, item)
    ranked = [(c["place"]["name"], c["basis"]) for c in got["candidates"]]
    assert ranked[0] == ("창덕궁", "same_kind")                                              # 같은 종류가 먼저
    assert {basis for _name, basis in ranked[1:]} == {"similar_experience"}
    first = got["candidates"][0]
    assert first["similarity"] == 3 and first["reason"].startswith("경복궁와 같은 소분류(관광공사 분류)의 곳이에요")


def test_nothing_alike_anywhere_says_so_instead_of_inventing(rv):  # noqa: F811
    _row(rv, "960001", "12", "경복궁", *PALACE, "HS", "HS01", "HS010100")
    _row(rv, "960004", "38", "우정약국 종로", 37.5797, 126.9771, "SH", "SH04", "SH040100")
    review, item = _palace_review()
    got = _alternatives(rv, review, item)
    assert got["candidates"] == [] and "no_alternative" in got["notes"] and "no_same_kind" in got["notes"]


def test_an_indoor_exhibit_continues_with_other_exhibits(rv):  # noqa: F811
    _row(rv, "970001", "14", "작은 박물관", *PALACE, "EX", "EX06", "EX060100")                # 원래 장소 — 체험 박물관 갈래
    _row(rv, "970002", "14", "시립 미술관", 37.5800, 126.9780, "VE", "VE07", "VE070100")
    _row(rv, "970003", "14", "광화문 어린이공원", 37.5760, 126.9760, "VE", "VE03", "VE030100")   # 야외 — 다른 갈래
    place = {"name": "작은 박물관", "latitude": PALACE[0], "longitude": PALACE[1], "kind": "activity", "source": "places",
             "content_id": "970001", "content_type_id": None, "ref": "place:x"}
    item = {**_item("m", "activity", "15:00"), "ends_at": "16:00", "title": "작은 박물관", "place": place, "place_state": "found", "parts": None}
    got = _alternatives(rv, {"items": [item]}, item)
    names = [c["place"]["name"] for c in got["candidates"]]
    assert names == ["시립 미술관"] and got["candidates"][0]["experience"] == "indoor_exhibit"
    assert "실내에서 전시 보기" in got["candidates"][0]["reason"]


def test_a_market_meal_shows_up_to_two_restaurants_not_only_markets(market_world):
    for number, (name, lat, lon) in enumerate([("마장 시장", 37.5710, 127.0000), ("중부 시장", 37.5690, 126.9980), ("동대문 시장", 37.5700, 127.0020)]):
        _row(market_world, f"95100{number}", "38", name, lat, lon, "SH", "SH06", "SH060200")
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for name, lat in (("시장 국밥집", 37.5704), ("시장 칼국수집", 37.5705)):
            cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, attributes) "
                        "VALUES (%s,%s,'dining',%s,126.9994,'dining_ledger','{\"source\": \"dining_ledger\"}')", (market_world["tenant"], name, lat))
    review, item = _review()
    got = _alternatives(market_world, review, item)
    kinds = [c["place"]["kind"] for c in got["candidates"]]
    assert len(got["candidates"]) == 3 and kinds.count("dining") == 2 and kinds.count("activity") == 1, kinds           # 시장 하나 + 식당 둘
    assert all(c["basis"] in ("same_kind", "meal_inferred") for c in got["candidates"])
    eating = [c for c in got["candidates"] if c["basis"] == "meal_inferred"]
    assert all(c["reason"].startswith("식사 시간이고 그 시간대에 식사 일정이 따로 없어 식당도 후보로 넣었어요") for c in eating)


# ── 이유 문장은 아는 값만 ───────────────────────────────────────────
def _candidate(**over):
    base = {"place": {"name": "탑골공원"}, "basis": "same_kind", "similarity": 2, "distance_m": 420, "reference": "경복궁", "experience": None,
            "rows": [{"row": "hours", "result": "ok", "text": "09:00~18:00 영업"}], "slack": {"before": 5, "after": 25}}
    return {**base, **over}


def test_the_reason_uses_only_values_that_are_known():
    full = _reason(_candidate(), "경복궁")
    assert full == "경복궁와 같은 중분류(관광공사 분류)의 곳이에요 · 경복궁에서 420m · 09:00~18:00 영업 · 다음 일정까지 25분 여유가 있어요"
    unknown_hours = _reason(_candidate(rows=[{"row": "hours", "result": "unknown", "text": "?"}], slack={"before": None, "after": None}), "경복궁")
    assert unknown_hours == "경복궁와 같은 중분류(관광공사 분류)의 곳이에요 · 경복궁에서 420m · 영업시간은 확인하지 못했어요"          # 모르면 모른다고, 여유는 안 쓴다
    late = _reason(_candidate(slack={"before": 5, "after": -10}), "경복궁")
    assert "여유" not in late                                                              # 늦는 후보에 여유가 있다고 쓰지 않는다
    assert _reason(_candidate(basis=None, rows=[], slack=None, distance_m=None, reference=None), "경복궁") is None   # 쓸 사실이 없으면 문장을 지어내지 않는다


def test_the_experience_groups_hold_no_shops_and_each_middle_class_belongs_to_one_group():
    assert _experience_of("VE03") == "outdoor_walk" and _experience_of("VE07") == "indoor_exhibit" and _experience_of("SH04") is None
    every = [code for group in EXPERIENCE_GROUPS.values() for code in group["lcls2"]]
    assert len(every) == len(set(every))                                                    # 한 중분류가 두 갈래에 걸치지 않는다
    assert not any(code.startswith(("SH", "FD", "AC")) for code in every)                   # 쇼핑 · 음식 · 숙박 가지는 경험 갈래에 없다
