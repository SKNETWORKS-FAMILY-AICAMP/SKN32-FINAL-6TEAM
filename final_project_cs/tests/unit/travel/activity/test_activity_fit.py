# -*- coding: utf-8 -*-
"""걸리면 **그 일정만 다음 후보로** — 최고 안이 일정 전체 재판정에 걸리면 담당이 뽑아 둔 다음 순위 안을 차례로 넣는다. `[2026-10-03 사용자 지시]`

☆결함: 최고 안이 앞뒤 항목과 안 맞아(구가 다른데 이동 시간이 0분 …) 전체 재판정(d6101790)에 걸리면 **다른 안을 시험해 보지도 않고** 「그대로 두었어요」로 끝났다 —
Team 이 이미 뽑아 둔 2·3순위 안은 버려졌다.

★지키려는 것: ①순위 순으로 시험해 통과하는 **첫** 안을 쓴다(제안·알림·「다른 안」이 모두 그 안 기준) ②다른 안을 쓰면 알림에 왜 1순위가 아닌지 적는다 ③걸린 안은 고객에게 다른 안으로 안 보인다
④다 걸리면 쓰지 않고 `itinerary_recheck_failed`(예외 아님) ⑤고객이 고른 변경은 이 문을 안 지난다.

재현:

    python -m pytest tests/unit/travel/activity/test_activity_fit.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.contracts import NextAction
from app.domains.travel_ops.instances.activity import ActivityTeam
from app.domains.travel_ops.components.itinerary.itinerary import Item, item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, _with_fallbacks
from app.domains.travel_ops.components.itinerary.itinerary_fit import fit_change

from ..helpers import pack, task
from .test_activity_trigger_budget import ALLOWED, _Tools

KST = ZoneInfo("Asia/Seoul")
START = datetime(2026, 10, 6, 14, 0, tzinfo=KST)


def _place(name, district, index=0):
    return {"place_id": str(uuid4()), "name": name, "kind": "activity", "latitude": 37.5 + 0.001 * index,
            "longitude": 127.0, "weather_sensitive": False, "attributes": {"hours": ["09:00", "22:00"], "district": district}}


def _world(candidates, constraints=None):
    """앞 항목(종로구)이 끝나자마자(간격 0분) 이 항목(종로구)이 시작한다 — 후보가 다른 구면 이동 시간 0분이라 `no_transfer_time` 위반이 **새로** 생긴다."""
    origin = _place("원래 활동", "종로구")
    before = Item(item_id=uuid4(), seq=1, kind="activity", title="앞 활동", place_id=uuid4(),
                  starts_at=START - timedelta(minutes=60), ends_at=START, place=_place("앞 활동 장소", "종로구"))
    item = Item(item_id=uuid4(), seq=2, kind="activity", title="원래 활동", place_id=uuid4(),
                starts_at=START, ends_at=START + timedelta(minutes=90), place=origin)
    trip = {"trip_id": str(uuid4()), "version": 1, "customer_id": str(uuid4()), "constraints": constraints or {}, "party_size": 2}
    places = [origin] + candidates
    values = {"read.itinerary": {"trip": trip, "items": [item_to_dict(before), item_to_dict(item)]},
              "read.place_catalog": places}
    tools = _Tools(values, original_id=origin["place_id"])
    context = pack("activity", state={
        "subject_ref": {"kind": "trip", "id": trip["trip_id"]}, "trigger_source": "schedule",
        "trigger": {"item_id": str(item.item_id), "at": START.isoformat(), "detected": "place", "categories": ["disaster"]}})
    return tools, task("activity", "activity.itinerary", context, ALLOWED), item


async def _run(candidates, constraints=None):
    tools, work, item = _world(candidates, constraints)
    return await ActivityTeam(tools).execute(work), item


@pytest.mark.asyncio
async def test_when_the_best_fails_the_whole_check_the_next_ranked_one_is_applied_and_the_notice_says_so():
    # 가까운 쪽(1순위)은 다른 구(중구) — 앞 항목과 0분 간격이라 이동 시간이 없다. 조금 먼 쪽(2순위)은 같은 구(종로구)
    first, second = _place("남산공원(중구)", "중구", 1), _place("북촌길(종로)", "종로구", 3)
    result, item = await _run([first, second])

    assert result.outcome == "completed" and result.action_proposals, result
    [proposal] = result.action_proposals
    [replacement] = proposal.arguments["replacements"]
    assert replacement["item"]["place"]["name"] == "북촌길(종로)"                         # 2순위가 적용됐다
    assert "북촌길(종로)" in result.answer and "1순위(남산공원(중구))" in result.answer and "2순위로 골랐어요" in result.answer
    assert proposal.arguments["summary"]["fit_rank"] == 2 and proposal.arguments["summary"]["skipped"] == ["남산공원(중구)"]
    # 걸린 1순위는 고객에게 「다른 안」으로 보이지 않는다 — 적용된 안의 다른 안 목록에 없다
    names = [a["name"] for a in replacement["item"]["detail"]["alternates"]]
    assert "남산공원(중구)" not in names


@pytest.mark.asyncio
async def test_the_best_that_fits_is_used_as_it_is_without_a_note():
    first, second = _place("낙산공원(종로)", "종로구", 1), _place("청계광장(중구)", "중구", 3)
    result, _ = await _run([first, second])

    [proposal] = result.action_proposals
    assert proposal.arguments["replacements"][0]["item"]["place"]["name"] == "낙산공원(종로)"
    assert "순위로 골랐어요" not in result.answer and "fit_rank" not in proposal.arguments["summary"]


@pytest.mark.asyncio
async def test_when_every_ranked_option_fails_nothing_is_applied_and_it_is_not_an_exception():
    result, _ = await _run([_place("남산공원(중구)", "중구", 1), _place("서울숲(성동)", "성동구", 3)])

    assert not result.action_proposals
    assert result.outcome == "escalated" and result.next_action is NextAction.ESCALATE
    assert result.failure_code == "itinerary_recheck_failed"
    assert any("일정 전체 재판정" in w and "1순위 남산공원(중구)" in w and "2순위 서울숲(성동)" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_a_trip_with_a_density_target_goes_through_the_same_path_end_to_end():
    """밀도 목표가 있어도 같은 길을 지난다 — 같은 시간대 맞바꿈은 하루 점유를 안 바꾸므로(이 일정은 바꾸기 전부터 이동 시간을 몰라 잴 수 없다) 걸리지 않는다."""
    density = {"level": "normal", "days": {"2026-10-06": {"starts_at": "2026-10-06T10:00:00+09:00",
                                                           "ends_at": "2026-10-06T22:00:00+09:00", "buffer_minutes": 0}}}
    result, _ = await _run([_place("낙산공원(종로)", "종로구", 1)], constraints={"density": density})
    assert result.outcome == "completed" and result.action_proposals
    assert "순위" not in result.answer


# ── 순수 함수 단위 ─────────────────────────────────────────────

def _items_pair():
    first = Item(item_id=uuid4(), seq=1, kind="activity", title="A", place_id=uuid4(), starts_at=START, ends_at=START + timedelta(minutes=60),
                 place=_place("A", "종로구"))
    second = Item(item_id=uuid4(), seq=2, kind="activity", title="B", place_id=uuid4(),
                  starts_at=START + timedelta(minutes=90), ends_at=START + timedelta(minutes=150), place=_place("B", "종로구"))
    return first, second


def _change(replaced: Item, name: str, ends_after: int) -> ItineraryChange:
    repl = replaced.replaced_by(place=_place(name, "종로구"), title=name, ends_at=START + timedelta(minutes=ends_after))
    return ItineraryChange(reason="auto_adjusted", causes=[], notice={"text": f"{name}(으)로 바꿨어요"},
                           replacements={replaced.item_id: repl}, summary={"to": name})


def test_fit_change_returns_the_first_rank_that_passes_and_records_what_it_skipped():
    first, second = _items_pair()
    overlapping_1 = _change(first, "1순위", 120)      # B(90분 시작)와 겹친다
    overlapping_2 = _change(first, "2순위", 100)      # 역시 겹친다
    fits_3 = _change(first, "3순위", 70)              # 겹치지 않는다
    best = _with_fallbacks(lambda c, _others: c, [overlapping_1, overlapping_2, fits_3])
    trip = {"constraints": {}, "party_size": 2}

    fit = fit_change(best, trip=trip, items=[first, second])
    fitted = fit.change
    assert fit.rank == 3 and [s.rank for s in fit.skipped] == [1, 2] and [s.name for s in fit.skipped] == ["1순위", "2순위"]
    assert all("겹친다" in s.reasons[0] and s.why == "schedule" for s in fit.skipped)
    assert fitted.summary["to"] == "3순위" and fitted.summary["skipped"] == ["1순위", "2순위"]
    assert "1·2순위(1순위 1순위, 2순위 2순위)은(는) 일정과 안 맞아 3순위로 골랐어요" in fitted.notice["text"]


def test_fit_change_returns_none_when_all_fail_and_untouched_when_the_best_fits():
    first, second = _items_pair()
    trip = {"constraints": {}, "party_size": 2}
    bad = _with_fallbacks(lambda c, _o: c, [_change(first, "가", 120), _change(first, "나", 110)])
    assert fit_change(bad, trip=trip, items=[first, second]).change is None
    good = _change(first, "다", 60)
    fit = fit_change(good, trip=trip, items=[first, second])
    assert fit.change is good and fit.rank == 1 and fit.skipped == [] and fit.accepted == []
