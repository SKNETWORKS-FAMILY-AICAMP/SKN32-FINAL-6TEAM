# -*- coding: utf-8 -*-
"""「A에서 B까지 어떻게 가요?」 — 물은 두 곳 사이로 답한다. `[2026-09-28]`

★전에는 먼저 나온 A 하나만 짚어 **A 의 다음 일정** 기준으로 답했다(ui 세션 실서버 시험 — 「경복궁에서 창덕궁까지」에
  북촌손만두 기준 답 + 「이동 항목이 없어요」). 이동 항목이 없으면 좌표로 **추정**하고 [추정]이라 적는다."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary import Item
from app.domains.travel_ops.components.conversation.trip_facts import fact_question, fact_reply

KST = ZoneInfo("Asia/Seoul")


def _stop(seq, hour, title, kind, lat, lon):
    return Item(item_id=uuid4(), seq=seq, kind=kind, title=title, place_id=uuid4(),
                starts_at=datetime(2026, 10, 5, hour, tzinfo=KST), ends_at=None,
                place={"name": title, "kind": kind, "latitude": lat, "longitude": lon})


ITEMS = [_stop(1, 8, "광장시장", "activity", 37.5700, 126.9996),
         _stop(2, 10, "경복궁 관람", "activity", 37.5796, 126.9770),
         _stop(3, 13, "북촌손만두", "dining", 37.5790, 126.9850),
         _stop(4, 15, "창덕궁 관람", "activity", 37.5794, 126.9910)]
NOW = datetime(2026, 9, 28, 12, tzinfo=KST)


def test_the_asked_destination_is_used_not_the_next_stop():
    message = "경복궁에서 창덕궁까지 어떻게 가요?"
    assert fact_question(message) == "move"
    answer, basis = fact_reply("move", message=message, items=ITEMS, now=NOW)
    assert basis["item"] == "경복궁 관람 → 창덕궁 관람"
    assert "경복궁 관람(10:00) → 창덕궁 관람(15:00)" in answer
    assert "북촌손만두" not in answer
    assert "[추정]" in answer and "약 " in answer                 # 모른다고 끝내지 않는다 — 추정이라고 적는다


def test_a_pair_asked_backwards_says_which_comes_first():
    answer, _ = fact_reply("move", message="창덕궁에서 광장시장으로 가는 방법", items=ITEMS, now=NOW)
    assert answer.startswith("창덕궁 관람(15:00) → 광장시장(08:00)")
    assert "광장시장(08:00) 쪽이 먼저" in answer


def test_one_place_still_gets_the_old_answer():
    answer, basis = fact_reply("move", message="경복궁 어떻게 가요?", items=ITEMS, now=NOW)
    assert basis["item"] == "경복궁 관람" and answer.startswith("경복궁 관람(10:00) 이동 정보예요.")


def test_a_delay_before_the_trip_starts_is_answered_not_replanned():
    """★「30분 늦어요」를 여행 전(9-28)에 받으면 일주일 뒤 점심을 늦춰 판정했고 사람 대기로 끝났다(ui 세션 실서버 시험)."""
    from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange, plan_delay

    plan = plan_delay(trip={"constraints": {}}, items=ITEMS, places=[], at=NOW, minutes=30,
                      message="30분 늦을 것 같아요", request_id=None)
    assert isinstance(plan, NoChange) and plan.status == "not_today"
    assert plan.detail["text"].startswith("오늘(9월 28일)은 이 여행의 일정이 없어서 바꾸지 않았어요.")
    assert "10월 5일 08:00 광장시장" in plan.detail["text"]
