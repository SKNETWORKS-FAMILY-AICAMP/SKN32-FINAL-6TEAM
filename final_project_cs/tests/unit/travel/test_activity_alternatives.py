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
from app.modules.travel_ops.activity.alternatives import closed_on, rank_alternatives

from .helpers import FakeTools, pack, task

UTC = timezone.utc
MONDAY = datetime(2026, 10, 5, 10, tzinfo=UTC)
SATURDAY = datetime(2026, 10, 3, 10, tzinfo=UTC)

CSV_PATH = (Path(__file__).resolve().parents[3]
            / "app" / "modules" / "travel_ops" / "activity" / "data_processing"
            / "activities_candidates_seoul_merged.csv")


def _place(cid, *, l1="HS", l2="HS01", l3="HS010100", ctype="12", sgg="23",
           x=126.9770, y=37.5796, closed="연중무휴", title=None):
    return {"contentid": cid, "title": title or f"장소{cid}", "contenttypeid": ctype,
            "lclsSystm1": l1, "lclsSystm2": l2, "lclsSystm3": l3, "sigungucode": sgg,
            "mapx": str(x), "mapy": str(y), "closed_days": closed,
            "business_hours": "09:00~18:00"}


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


# ══════════════════════════════════════════════════════════════════
# ②③ 유사도 + 선호도 폴백
# ══════════════════════════════════════════════════════════════════

def test_preference_none_uses_all_fields_and_never_falls_back():
    pool = [_place("x", ctype="14")]            # 관광타입만 다르다
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference=None)
    assert result["alternatives"] == []
    assert result["dropped_fields"] == []


def test_fallback_drops_lowest_priority_first():
    pool = [_place("x", ctype="14")]
    result = rank_alternatives(ORIGIN, pool, SATURDAY, preference="activity")
    assert result["dropped_fields"] == ["contenttypeid"]
    assert [a["contentid"] for a in result["alternatives"]] == ["x"]


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
    starts_at = starts_at or datetime.now(UTC) + timedelta(days=30)
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
    disaster = {"messages": [{"EMRG_STEP_NM": "위급재난", "DST_SE_NM": "지진"}]}
    result = await ActivityTeam(FakeTools(_values(disaster=disaster))).execute(_feasible_task())
    assert result.decisions[0]["feasible"] is False
    assert result.decisions[0]["disaster"]["blocks"] is True
