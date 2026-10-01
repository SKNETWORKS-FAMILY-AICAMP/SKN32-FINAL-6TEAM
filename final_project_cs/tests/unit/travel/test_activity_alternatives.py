# -*- coding: utf-8 -*-
"""대체 장소 후보(`alternatives.py`) + `check_feasible` 3분기 status.

wiki/teams/activity.md 「에이전트 유스케이스 검토」 — 작업자 B 범위:
  2단계 문제 판정 3분기(problem / insufficient_info / ok)
  4단계 대체 장소 후보(① 가용성 → ② 유사도 → ③ 선호도 폴백 → ④ 거리 순위)
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.modules.travel_ops.activity import ActivityTeam
from app.modules.travel_ops.activity.alternatives import closed_on, open_at, rank_alternatives

from .helpers import FakeTools, pack, task

KST = timezone(timedelta(hours=9))        # ★요청 시각은 전부 한국 시간으로 다룬다(2026-10-01)
MONDAY = datetime(2026, 10, 5, 10, tzinfo=KST)
SATURDAY = datetime(2026, 10, 3, 10, tzinfo=KST)

CSV_PATH = (Path(__file__).resolve().parents[3]
            / "app" / "modules" / "travel_ops" / "activity" / "data_processing"
            / "activity_total_data.csv")


def _place(cid, *, l1="HS", l2="HS01", l3="HS010100", ctype="12", sgg="23",
           x=126.9770, y=37.5796, closed="연중무휴", title=None, brand=None, hours=None):
    return {"brand": brand, "contentid": cid, "title": title or f"장소{cid}", "contenttypeid": ctype,
            "lclsSystm1": l1, "lclsSystm2": l2, "lclsSystm3": l3, "sigungucode": sgg,
            "mapx": str(x), "mapy": str(y), "closed_days": closed,
            "business_hours": hours}


ORIGIN = _place("origin", title="경복궁", closed="매주 화요일")


# ══════════════════════════════════════════════════════════════════
# ① 가용성 — closed_on
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("text, at, expected", [
    ("매주 월요일", MONDAY, True),
    ("매주 월요일", SATURDAY, False),
    ("연중무휴", MONDAY, False),
    ("매주 토요일~일요일 / 법정공휴일", SATURDAY, True),
    ("매주 토요일~일요일 / 법정공휴일", MONDAY, False),
    ("매주 일요일~월요일", MONDAY, True),           # 주를 넘는 범위
    ("주말", SATURDAY, True),
    ("매주 월요일 / 1월 1일 / 설·추석 당일", MONDAY, True),
    ("설·추석 당일", MONDAY, False),                 # 날짜 휴무는 요일 판정에 안 넣는다
    ("", MONDAY, None),
    (None, MONDAY, None),
    ("점포별 상이", MONDAY, None),
    ("홈페이지 참조", MONDAY, None),
])
def test_closed_on(text, at, expected):
    assert closed_on(text, at) is expected


def test_closed_candidates_are_dropped_unknown_kept_but_marked():
    pool = [_place("a", closed="매주 월요일"),
            _place("b", closed="점포별 상이"),
            _place("c", closed="연중무휴")]
    result = rank_alternatives(ORIGIN, pool, MONDAY)
    ids = [a["contentid"] for a in result["alternatives"]]
    assert ids == ["c", "b"]            # 확인된 곳이 먼저, 모름은 뒤
    assert result["alternatives"][1]["availability"] == "unconfirmed"


def test_origin_itself_is_never_an_alternative():
    result = rank_alternatives(ORIGIN, [dict(ORIGIN, closed_days="연중무휴")], SATURDAY)
    assert result["alternatives"] == []


# ── 운영시간 — open_at ─────────────────────────────────────────

def _at(weekday_offset, hour, minute=0):
    """2026-10-05(월) 기준 KST 시각. 요일은 offset 으로(0=월)."""
    return datetime(2026, 10, 5 + weekday_offset, hour, minute, tzinfo=KST)


@pytest.mark.parametrize("text, at, expected", [
    ("상시 개방", _at(0, 3), True),
    ("24시간 운영", _at(2, 3), True),
    ("09:00~18:00", _at(0, 10), True),
    ("09:00~18:00", _at(0, 18), False),                         # 끝 시각은 닫힌 것
    ("09:00 ~ 18:00(입장마감 17:00)", _at(0, 17, 30), True),     # 괄호 설명은 뗀다
    ("10:00~02:00", _at(0, 1), True),                           # 자정 넘김
    ("10:00~02:00", _at(0, 5), False),
    ("00:00~24:00", _at(0, 23, 59), True),
    ("평일·금·토·일·휴일 10:00 ~ 22:00", _at(5, 21), True),      # 사실상 매일
    ("평일·금·토·일·휴일 10:00 ~ 22:00", _at(0, 22, 30), False),
    ("평일 09:00~18:00 / 주말 10:00~20:00", _at(5, 19), True),   # 토요일은 주말 구간
    ("평일 09:00~18:00 / 주말 10:00~20:00", _at(0, 19), False),
    ("월~금 09:00~18:00", _at(0, 10), True),                    # 요일 범위
    ("월~금 09:00~18:00", _at(5, 10), None),                    # 토요일 구간이 없다 — 모름
    ("금~월 10:00~20:00", _at(6, 12), True),                    # 주를 넘는 범위
    ("", _at(0, 10), None),
    (None, _at(0, 10), None),
    ("점포별 상이함", _at(0, 10), None),
    ("[한국영상자료원]<br>10:00~19:00", _at(0, 10), None),       # 시설이 둘 — 모름
    ("10:00~22:00 (브레이크타임 15:00~16:00)", _at(0, 15, 30), None),
    ("평일 09:00~18:00", _at(5, 10), None),                     # 토요일 구간이 없다 — 모름
    ("평일 11:00~20:00 / 휴일 09:00~22:00", _at(0, 10), None),   # 공휴일 시간이 따로 있다 — 오늘이 공휴일인지 몰라 단정 안 함
])
def test_open_at(text, at, expected):
    assert open_at(text, at) is expected


def test_open_at_reads_utc_input_as_korean_time():
    """UTC 10:00 = KST 19:00 — 09:00~18:00 은 닫힌 시각이다."""
    assert open_at("09:00~18:00", datetime(2026, 10, 5, 10, tzinfo=timezone.utc)) is False
    assert open_at("09:00~18:00", datetime(2026, 10, 5, 0, 30, tzinfo=timezone.utc)) is True


def test_candidates_closed_at_that_hour_are_dropped_before_similarity():
    pool = [_place("closed_now", closed=None, hours="09:00~12:00"),
            _place("open_now", closed=None, hours="09:00~20:00"),
            _place("unknown_hours", closed=None, hours=None)]
    result = rank_alternatives(ORIGIN, pool, _at(0, 14))
    ids = [a["contentid"] for a in result["alternatives"]]
    assert ids == ["open_now", "unknown_hours"]                  # 확인된 곳이 먼저, 모름은 뒤
    assert result["alternatives"][0]["availability"] == "open_at_time"   # 휴무는 모르지만 운영시간 안
    assert result["alternatives"][1]["availability"] == "unconfirmed"
    assert result["total_matched"] == 2


def test_hours_filter_runs_before_fallback_so_closed_places_never_reach_the_fallback():
    pool = [_place("closed_now", l3="X", hours="09:00~12:00")]
    result = rank_alternatives(ORIGIN, pool, _at(0, 14), preference="activity")
    assert result["alternatives"] == [] and result["total_matched"] == 0


# ══════════════════════════════════════════════════════════════════
# ②③ 유사도 + 선호도 폴백
# ══════════════════════════════════════════════════════════════════

def test_preference_none_uses_all_fields_and_never_falls_back():
    pool = [_place("x", ctype="14")]            # 관광타입만 다르다
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference=None)
    assert result["alternatives"] == []
    assert result["dropped_fields"] == []


def test_fallback_drops_lowest_class_first():
    """★1순위로 소분류부터 뺀다. 타입은 대분류와 한 묶음이라 따로 먼저 풀리지 않는다."""
    pool = [_place("x", l3="HS019999")]          # 소분류만 다르다
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference="activity")
    assert result["dropped_fields"] == ["lclsSystm3"]
    assert [a["contentid"] for a in result["alternatives"]] == ["x"]


@pytest.mark.parametrize("preference, diff, dropped", [
    ("mobility", dict(l3="X"), ["lclsSystm3"]),
    ("mobility", dict(l3="X", l2="HS02"), ["lclsSystm3", "lclsSystm2"]),
    ("mobility", dict(l3="X", l2="NA01", l1="NA", ctype="14"),
     ["lclsSystm3", "lclsSystm2", "lclsSystm1", "contenttypeid"]),
    ("activity", dict(l3="X"), ["lclsSystm3"]),
    ("activity", dict(l3="X", l2="HS02"), ["lclsSystm3", "lclsSystm2"]),
    ("activity", dict(l3="X", l2="HS02", sgg="1"), ["lclsSystm3", "lclsSystm2", "sigungucode"]),
])
def test_fallback_order_per_preference(preference, diff, dropped):
    """이동: 소분류→중분류→대분류(+타입). 활동: 소분류→중분류→시군구. 단계마다 그 단계에서만 맞는 후보를 둔다."""
    result = rank_alternatives(ORIGIN, [_place("x", **diff)], SATURDAY, preference=preference)
    assert result["dropped_fields"] == dropped
    assert [a["contentid"] for a in result["alternatives"]] == ["x"]


def test_activity_never_drops_large_class_or_type():
    pool = [_place("other_type", ctype="14", l3="X", l2="HS02", sgg="1")]
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference="activity")
    assert result["alternatives"] == []


def test_mobility_keeps_sigungu_fixed():
    pool = [_place("other_gu", sgg="1")]         # 분류는 같고 구만 다르다
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference="mobility")
    assert result["alternatives"] == []
    assert result["matched_fields"] == ["sigungucode"]


def test_activity_keeps_large_class_fixed_but_drops_sigungu():
    pool = [_place("other_gu", sgg="1"), _place("other_class", l1="VE")]
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference="activity")
    assert [a["contentid"] for a in result["alternatives"]] == ["other_gu"]
    assert "sigungucode" in result["dropped_fields"]


def test_unknown_preference_is_rejected():
    with pytest.raises(ValueError):
        rank_alternatives(ORIGIN, [], SATURDAY, preference="food")


# ══════════════════════════════════════════════════════════════════
# ④ 거리 순위
# ══════════════════════════════════════════════════════════════════

def test_ranks_by_distance_top_three():
    pool = [_place(str(i), x=126.9770 + 0.01 * i) for i in (4, 1, 3, 2)]
    result = rank_alternatives(ORIGIN, pool, SATURDAY)
    assert [a["contentid"] for a in result["alternatives"]] == ["1", "2", "3"]
    assert [a["rank"] for a in result["alternatives"]] == [1, 2, 3]
    assert result["total_matched"] == 4


# ── 브랜드: 같은 브랜드·같은 시군구가 먼저, 시군구 밖 같은 브랜드는 거리로만 겨룬다 ──

SHOP = dict(l1="SH", l2="SH04", l3="SH040300", ctype="38")
BRAND_ORIGIN = _place("o", brand="올리브영", sgg="24", **SHOP)


def _shop(cid, brand, *, sgg="24", x=126.9770, **kw):
    return _place(cid, brand=brand, sgg=sgg, x=x, **SHOP, **kw)


def test_same_brand_in_same_gu_beats_a_closer_other_brand():
    pool = [_shop("daiso_near", "다이소", x=126.9771),          # 가장 가깝지만 다른 브랜드
            _shop("oy_far", "올리브영", x=126.9900)]             # 같은 브랜드·같은 구
    result = rank_alternatives(BRAND_ORIGIN, pool, SATURDAY)
    assert [a["contentid"] for a in result["alternatives"]] == ["oy_far", "daiso_near"]


def test_same_brand_outside_the_gu_does_not_beat_a_closer_other_brand():
    """★같은 구에 후보가 없어 시군구가 폴백으로 풀리면, 같은 브랜드라도 거리로만 겨룬다."""
    pool = [_shop("oy_other_gu", "올리브영", sgg="1", x=127.1),
            _shop("daiso_near", "다이소", sgg="2", x=126.9775)]
    result = rank_alternatives(BRAND_ORIGIN, pool, SATURDAY, preference="activity")
    assert "sigungucode" in result["dropped_fields"]
    assert [a["contentid"] for a in result["alternatives"]] == ["daiso_near", "oy_other_gu"]


def test_same_brand_in_gu_are_ordered_by_distance_among_themselves():
    pool = [_shop("oy_b", "올리브영", x=126.99), _shop("oy_a", "올리브영", x=126.98)]
    result = rank_alternatives(BRAND_ORIGIN, pool, SATURDAY)
    assert [a["contentid"] for a in result["alternatives"]] == ["oy_a", "oy_b"]


def test_origin_without_brand_ranks_by_distance_only():
    origin = _place("o", sgg="24", **SHOP)                      # 브랜드 모름
    pool = [_shop("far_oy", "올리브영", x=126.99), _shop("near_daiso", "다이소", x=126.9772)]
    result = rank_alternatives(origin, pool, SATURDAY)
    assert [a["contentid"] for a in result["alternatives"]] == ["near_daiso", "far_oy"]


def test_missing_coordinates_go_last():
    pool = [_place("nocoord", x=""), _place("far", x=127.05)]
    result = rank_alternatives(ORIGIN, pool, SATURDAY)
    assert [a["contentid"] for a in result["alternatives"]] == ["far", "nocoord"]
    assert result["alternatives"][1]["distance_km"] is None


@pytest.mark.skipif(not CSV_PATH.exists(), reason="후보 CSV 없음")
def test_real_catalog_changgyeonggung_on_monday():
    """실 CSV(서울 후보)로 — 창경궁(매주 월요일 휴무)을 월요일에 대체하면 같은
    역사관광(HS) 대안이 나오고, 그 대안도 월요일 휴무가 아니다."""
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        pool = list(csv.DictReader(fh))
    origin = next(r for r in pool if r["contentid"] == "126511")   # 창경궁
    assert closed_on(origin["closed_days"], MONDAY) is True
    result = rank_alternatives(origin, pool, MONDAY, preference="activity")
    assert 1 <= len(result["alternatives"]) <= 3
    assert all(a["contentid"] != origin["contentid"] for a in result["alternatives"])
    by_id = {r["contentid"]: r for r in pool}
    assert all(by_id[a["contentid"]]["lclsSystm1"] == origin["lclsSystm1"]
               for a in result["alternatives"])
    assert all(closed_on(a["closed_days"], MONDAY) is not True
               for a in result["alternatives"])


# ══════════════════════════════════════════════════════════════════
# check_feasible 3분기 status
# ══════════════════════════════════════════════════════════════════

def _feasible_task():
    context = pack("activity", scope=["activity"])
    return task("activity", "activity.check_feasible", context,
                ActivityTeam.manifest.allowed_tools)


def _values(*, place="default", starts_at=None, party=2, capacity=4, disaster=None):
    starts_at = starts_at or datetime.now(KST) + timedelta(days=30)
    if place == "default":
        place = {"place_id": "p1", "weather_sensitive": False,
                 "latitude": 37.5796, "longitude": 126.9770}
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": starts_at,
                         "party_size": party, "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place,
        "read.weather": None,
        "read.disaster": disaster,
    }


@pytest.mark.asyncio
async def test_feasible_ok():
    result = await ActivityTeam(FakeTools(_values())).execute(_feasible_task())
    assert result.decisions[0]["feasible"] is True


@pytest.mark.asyncio
async def test_feasible_place_unknown_returns_infeasible():
    """place=None → feasible=False + place_confirmed=False (장소를 모르면 성립 단정 안 함)."""
    result = await ActivityTeam(FakeTools(_values(place=None))).execute(_feasible_task())
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["place_confirmed"] is False


@pytest.mark.asyncio
async def test_feasible_problem_on_capacity():
    result = await ActivityTeam(FakeTools(_values(party=5, capacity=4))).execute(_feasible_task())
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["reason"] == "party_over_capacity"


@pytest.mark.asyncio
async def test_feasible_disrupted_by_critical_disaster():
    """위급재난 발령 → feasible=False + disaster.blocks=True."""
    disaster = {"for_region": [{"step": "위급재난", "kind": "지진"}]}
    result = await ActivityTeam(FakeTools(_values(disaster=disaster))).execute(_feasible_task())
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["disaster"]["blocks"] is True
