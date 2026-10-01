# -*- coding: utf-8 -*-
"""check_feasible → 대체 장소 연결 — 불가 판정이 **장소 때문일 때만** 후보를 읽어 추천한다.

흐름: 코어가 준 예약의 장소 → 불가(휴무 요일·위급재난) → `read.place_candidates` → `rank_alternatives`
      → `decisions[].alternatives`(status: ranked · unknown · withheld) 와 답변 문장으로 코어에 돌려준다.
규칙의 정본은 wiki/teams/activity.md 「Team 연결」 — 위급재난이면 안내하지 않고, 운영 여부를 모르는 후보는 안내문에 싣지 않는다.
후보 풀 조회 자체는 `test_db_search_place_candidates.py`, 순위 계산은 `test_activity_alternatives.py` 담당.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.modules.travel_ops.activity import ActivityTeam

from .helpers import FakeTools, pack, task

KST = timezone(timedelta(hours=9))
ALLOWED = ActivityTeam.manifest.allowed_tools


def _next_monday() -> datetime:
    """30일 뒤쯤의 월요일 10시(KST) — 이미 시작된 예약이 되지 않게."""
    base = datetime.now(KST) + timedelta(days=30)
    base += timedelta(days=(0 - base.weekday()) % 7)
    return base.replace(hour=10, minute=0, second=0, microsecond=0)


def _row(cid, title, *, l1="HS", l2="HS01", l3="HS010100", sgg="23", x="126.9770", y="37.5796",
         closed="연중무휴", hours=None):
    return {"contentid": cid, "title": title, "contenttypeid": "12", "lclsSystm1": l1,
            "lclsSystm2": l2, "lclsSystm3": l3, "sigungucode": sgg, "brand": None,
            "mapx": x, "mapy": y, "closed_days": closed, "business_hours": hours}


ORIGIN_ROW = _row("126511", "창경궁", closed="매주 월요일")
POOL = {"origin": ORIGIN_ROW,
        "candidates": [_row("far", "먼 궁궐", x="127.05"), _row("near", "가까운 궁궐", x="126.9780"),
                       _row("closed", "월요일 휴무 궁궐", closed="매주 월요일")],
        "source": "place_catalog:tour_api+oliveyoung", "confirmed_at": "2026-09-28T00:00:00+00:00"}


def _values(*, starts_at=None, restdate="매주 월요일 휴무", content_id="126511", pool=POOL,
            disaster=None, party=2, capacity=4):
    starts_at = starts_at or _next_monday()
    place = {"place_id": "p1", "name": "창경궁", "weather_sensitive": False,
             "latitude": 37.5796, "longitude": 126.9770,
             "operating": {"usetime_text": "09:00~18:00", "restdate_text": restdate,
                           "source": "tour_api", "confirmed_at": "2026-09-22T00:00:00+00:00"}}
    if content_id:
        place["source_content_id"] = content_id
    return {
        "read.booking": {"booking_id": "b1", "place_id": "p1", "starts_at": starts_at,
                         "party_size": party, "capacity": capacity},
        "read.policy": [{"cancel_deadline_hours": 24}],
        "read.place": place, "read.weather": None, "read.disaster": disaster,
        "read.place_candidates": pool,
    }


async def _run(values, *, state=None):
    tools = FakeTools(values)
    ctx = pack("activity", scope=["activity"], state=state)
    result = await ActivityTeam(tools).execute(task("activity", "activity.check_feasible", ctx, ALLOWED))
    return result, tools


def _alt(result):
    return result.decisions[0]["alternatives"]


def test_place_candidates_is_a_declared_tool():
    assert "read.place_candidates" in ALLOWED


@pytest.mark.asyncio
async def test_closed_weekday_recommends_alternatives_in_distance_order():
    result, tools = await _run(_values())
    alt = _alt(result)
    assert result.decisions[0]["feasible"] is False
    assert alt["status"] == "ranked"
    assert result.decisions[0]["status"] == "problem"
    # ★휴무 요일(월요일) 후보는 빠지고, 가까운 순이다
    assert [i["contentid"] for i in alt["alternatives"]] == ["near", "far"]
    assert "대체 장소 후보" in result.answer and "가까운 궁궐" in result.answer
    assert ("read.place_candidates", {"content_id": "126511"}) in tools.calls
    assert "read.place_candidates" in [e.source_id for e in result.evidence]


@pytest.mark.asyncio
async def test_evidence_summarizes_the_pool_instead_of_dumping_it():
    result, _ = await _run(_values())
    ev = next(e for e in result.evidence if e.source_id == "read.place_candidates")
    assert ev.value["pool_size"] == 3 and ev.value["origin"]["title"] == "창경궁"
    assert "candidates" not in ev.value


@pytest.mark.asyncio
async def test_critical_disaster_withholds_alternatives_and_reads_nothing():
    """★위급재난이면 대체 장소를 안내하지 않는다 — 재난문자가 전국 목록이라 후보도 같은 판정이다."""
    disaster = {"for_region": [{"step": "위급재난", "kind": "지진"}],
                "confirmed_at": "2026-09-28T10:00:00+00:00", "source": "disaster_api"}
    result, tools = await _run(_values(restdate="연중무휴", disaster=disaster))
    assert result.decisions[0]["feasible"] is False
    assert _alt(result) == {"status": "withheld", "reason": "disaster_blocks"}
    assert "가까운 궁궐" not in result.answer and "대체 장소를 안내하지 않았습니다" in result.answer
    assert "read.place_candidates" not in [n for n, _ in tools.calls]


@pytest.mark.asyncio
async def test_disaster_and_closed_weekday_together_still_withhold():
    disaster = {"for_region": [{"step": "위급재난", "kind": "지진"}],
                "confirmed_at": "2026-09-28T10:00:00+00:00", "source": "disaster_api"}
    result, tools = await _run(_values(disaster=disaster))     # 휴무 요일(월요일)도 겹친다
    assert _alt(result)["status"] == "withheld"
    assert "read.place_candidates" not in [n for n, _ in tools.calls]


@pytest.mark.asyncio
async def test_feasible_booking_does_not_read_candidates():
    result, tools = await _run(_values(restdate="매주 화요일 휴무"))
    assert result.decisions[0]["feasible"] is True
    assert "alternatives" not in result.decisions[0]
    assert "read.place_candidates" not in [n for n, _ in tools.calls]


@pytest.mark.asyncio
async def test_failures_a_new_place_cannot_fix_do_not_read_candidates():
    """정원 초과·이미 시작됨은 장소를 바꿔도 안 풀린다."""
    for kwargs in ({"party": 9, "capacity": 4},
                   {"starts_at": datetime.now(KST) - timedelta(hours=3)}):
        result, tools = await _run(_values(**kwargs))
        assert result.decisions[0]["feasible"] is False
        assert "read.place_candidates" not in [n for n, _ in tools.calls]


@pytest.mark.asyncio
async def test_origin_missing_from_catalog_is_unknown_not_empty():
    """★카탈로그에 원래 장소가 없으면 「대체 장소 없음」이 아니라 「조회 못 함」이다."""
    result, _ = await _run(_values(pool=None))
    alt = _alt(result)
    assert alt["status"] == "unknown" and alt["reason"] == "pool_unavailable"
    assert "조회하지 못했습니다" in result.answer
    assert any("후보 풀을 받지 못했다" in w for w in result.warnings)
    assert result.outcome == "completed"


@pytest.mark.asyncio
async def test_place_without_content_id_is_unknown_and_reads_nothing():
    result, tools = await _run(_values(content_id=None))
    assert _alt(result) == {"status": "unknown", "reason": "no_content_id"}
    assert "read.place_candidates" not in [n for n, _ in tools.calls]


@pytest.mark.asyncio
async def test_no_candidate_left_is_ranked_with_no_items():
    pool = {**POOL, "candidates": [_row("closed", "월요일 휴무 궁궐", closed="매주 월요일")]}
    result, _ = await _run(_values(pool=pool))
    alt = _alt(result)
    assert alt["status"] == "ranked" and alt["alternatives"] == []
    assert "찾지 못했습니다" in result.answer


@pytest.mark.asyncio
async def test_survey_priority_sets_the_preference():
    """같은 풀이어도 이동 우선(시군구 고정)이면 다른 구 후보가 안 나오고, 활동 우선이면 나온다."""
    pool = {**POOL, "candidates": [_row("other_gu", "다른 구 궁궐", sgg="1", x="126.99")]}
    mobility, _ = await _run(_values(pool=pool), state={"survey": {"priority": ["mobility", "activity"]}})
    activity, _ = await _run(_values(pool=pool), state={"survey": {"priority": ["food", "activity"]}})
    no_survey, _ = await _run(_values(pool=pool))
    assert _alt(mobility)["preference"] == "mobility" and _alt(mobility)["alternatives"] == []
    assert _alt(activity)["preference"] == "activity" and _alt(activity)["alternatives"]
    assert "sigungucode" in " ".join(activity.warnings)             # 완화한 조건을 밝힌다
    assert _alt(no_survey)["preference"] is None and _alt(no_survey)["alternatives"] == []


@pytest.mark.asyncio
async def test_constraints_survey_shape_is_read_too():
    pool = {**POOL, "candidates": [_row("other_gu", "다른 구 궁궐", sgg="1")]}
    result, _ = await _run(_values(pool=pool), state={"constraints": {"survey": {"priority": ["activity"]}}})
    assert _alt(result)["preference"] == "activity"


@pytest.mark.asyncio
async def test_unconfirmed_candidate_stays_in_decisions_but_not_in_the_answer():
    """★운영 여부를 모르는 후보는 안내문에 싣지 않는다 — `decisions` 에만 `revalidated: False` 로 남는다."""
    pool = {**POOL, "candidates": [_row("u", "운영 미확인 궁궐", closed=None),
                                   _row("ok", "확인된 궁궐", x="127.05")]}
    result, _ = await _run(_values(pool=pool))
    items = {i["contentid"]: i for i in _alt(result)["alternatives"]}
    assert items["u"]["revalidated"] is False and items["u"]["availability"] == "unconfirmed"
    assert items["ok"]["revalidated"] is True
    assert "운영 미확인 궁궐" not in result.answer and "확인된 궁궐" in result.answer
    

@pytest.mark.asyncio
async def test_only_unconfirmed_candidates_say_so_instead_of_listing_them():
    pool = {**POOL, "candidates": [_row("u", "운영 미확인 궁궐", closed=None)]}
    result, _ = await _run(_values(pool=pool))
    assert _alt(result)["alternatives"][0]["revalidated"] is False
    assert "운영 미확인 궁궐" not in result.answer
    assert "운영 여부를 확인하지 못해 안내하지 않았습니다" in result.answer


@pytest.mark.asyncio
async def test_answer_says_capacity_was_not_checked():
    result, _ = await _run(_values())
    assert _alt(result)["revalidation"]["not_checked"] == ["capacity"]
    assert "정원은 확인하지 않았습니다" in result.answer
    assert "business_hours" in _alt(result)["revalidation"]["checked"]


@pytest.mark.asyncio
async def test_activity_preference_key_is_read_and_wins_over_survey():
    pool = {**POOL, "candidates": [_row("other_gu", "다른 구 궁궐", sgg="1", x="126.99")]}
    state = {"activity_preference": "activity", "survey": {"priority": ["mobility"]}}
    result, _ = await _run(_values(pool=pool), state=state)
    assert _alt(result)["preference"] == "activity" and _alt(result)["alternatives"]


@pytest.mark.asyncio
async def test_unknown_activity_preference_is_warned_and_ignored():
    """★모르는 값은 짐작하지 않는다 — 경고를 남기고 선호도 없음(폴백 없음)으로 처리한다."""
    pool = {**POOL, "candidates": [_row("other_gu", "다른 구 궁궐", sgg="1", x="126.99")]}
    result, _ = await _run(_values(pool=pool), state={"activity_preference": "food"})
    assert _alt(result)["preference"] is None and _alt(result)["alternatives"] == []
    assert any("알 수 없는 선호도" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_status_has_three_branches():
    ok, _ = await _run(_values(restdate="매주 화요일 휴무"))
    problem, _ = await _run(_values())
    started, _ = await _run(_values(starts_at=datetime.now(KST) - timedelta(hours=3)))
    over, _ = await _run(_values(party=9, capacity=4))
    unknown_place, _ = await _run({**_values(), "read.place": None})
    assert ok.decisions[0]["status"] == "ok"
    assert problem.decisions[0]["status"] == "problem"
    assert started.decisions[0]["status"] == "problem"
    assert over.decisions[0]["status"] == "problem"
    assert unknown_place.decisions[0]["status"] == "insufficient_info"
