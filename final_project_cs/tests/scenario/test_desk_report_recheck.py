# -*- coding: utf-8 -*-
"""고객 신고(「늦어요」 · 「문 닫았대요」)로 **자동 고른 대체**도 쓰기 전에 일정 전체를 다시 판정한다 — D-017, 체크리스트 T5의 세 번째 자리. `[2026-10-03 적대 검토]`

☆왜: Case 버전의 적용기와 시나리오 감시 · 새벽 확인(`pending.apply_or_ask`)은 자동 변경 전에 일정 전체를 다시 판정하는데, 채팅 신고 경로(`TripDesk._outcome(gate=True)`)만
판정 없이 바로 새 버전을 썼다 — 신고로 고른 대체가 앞뒤 항목과 겹치거나 이동이 안 닿아도 그대로 들어갔다.

★지키려는 것: ①걸리면 쓰지 않고 「일정은 그대로 두었어요」를 **답 문장으로** 돌려준다(채팅 답이다 — 알림 큐에 따로 쌓지 않는다) ②맞는 변경은 그대로 쓴다 ③최고 안이 걸리면 다음 순위 안을 쓴다
④고객이 **직접 고른** 길(`gate=False` — 다른 안으로 바꿔 줘 · 되돌려 줘)은 지나지 않는다 — 고르는 것 자체가 답이다.

재현:

    python -m pytest tests/scenario/test_desk_report_recheck.py -v
"""
from __future__ import annotations

from datetime import timedelta

from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.itinerary_changes import ItineraryChange
from app.modules.travel_ops.trip_desk import TripDesk

from .test_case_version_day import case_world  # noqa: F401 — 픽스처를 그대로 쓴다

CAUSES = [{"category": "customer_report", "type": "delay", "minutes": 30, "message": "30분 늦어요", "evidence": "고객 신고"}]


def _desk(world):
    return TripDesk(store=world["store"], connection_factory=get_connection, dining_ledger=False)


def _trip(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _activity_followed_by_something(items):
    ordered = sorted(items, key=lambda i: (i.starts_at, i.seq))
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.kind == "activity" and earlier.place is not None and later.kind != "mobility":
            return earlier, later
    raise AssertionError("시나리오에 활동 바로 뒤에 다른 항목이 오는 곳이 없다")


def _change(item, replacement, *, to, fallbacks=()):
    return ItineraryChange(reason="auto_adjusted", causes=CAUSES, notice={"text": f"{to} 로 바꿨어요"},
                           replacements={item.item_id: replacement}, summary={"from": item.title, "to": to},
                           fallbacks=list(fallbacks))


def _overlapping(item, later):
    return item.replaced_by(place=item.place, title=item.title + "(겹침)", ends_at=later.starts_at + timedelta(minutes=30))


def test_a_reported_change_that_breaks_the_whole_itinerary_is_not_written_and_the_answer_says_so(case_world):
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    outcome = _desk(case_world)._outcome(case_world["trip_id"], trip["version"], items,
                                         _change(item, _overlapping(item, later), to=item.title + "(겹침)"), gate=True)
    assert outcome["status"] == "rechecked" and "일정은 그대로 두었어요" in outcome["text"] and outcome["item"] == item.title
    assert outcome["skipped"] and outcome["skipped"][0]["why"] == "schedule"
    assert _trip(case_world)[0]["version"] == trip["version"]                           # ★아무것도 안 바뀌었다


def test_a_reported_change_that_fits_is_still_written(case_world):
    trip, items = _trip(case_world)
    item, _ = _activity_followed_by_something(items)
    harmless = item.replaced_by(place=item.place, title=item.title + "(대체)")
    outcome = _desk(case_world)._outcome(case_world["trip_id"], trip["version"], items,
                                         _change(item, harmless, to=harmless.title), gate=True)
    assert outcome["status"] == "adjusted" and outcome["version"] == trip["version"] + 1


def test_when_the_best_reported_option_fails_the_next_ranked_one_is_written(case_world):
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    second = item.replaced_by(place=item.place, title=item.title + "(2순위)")
    change = _change(item, _overlapping(item, later), to=item.title + "(겹침)", fallbacks=[_change(item, second, to=second.title)])
    outcome = _desk(case_world)._outcome(case_world["trip_id"], trip["version"], items, change, gate=True)
    assert outcome["status"] == "adjusted" and outcome["fit_rank"] == 2
    assert any(i.title == second.title for i in _trip(case_world)[1])


def test_a_change_the_customer_chose_themselves_is_not_rechecked(case_world):
    """다른 안으로 바꿔 줘(`swap_alternate`) · 되돌려 줘는 `gate=False` 다 — 고객이 고른 것 자체가 답이라 이 문을 지나지 않는다(전과 같다)."""
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    outcome = _desk(case_world)._outcome(case_world["trip_id"], trip["version"], items,
                                         _change(item, _overlapping(item, later), to=item.title + "(겹침)"))
    assert outcome["status"] == "adjusted"
