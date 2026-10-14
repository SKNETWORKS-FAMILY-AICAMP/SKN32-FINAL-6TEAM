"""결정 단위가 「대상 없음」이라고 판단한 읽기 질문은 답을 쓸 때 문장을 다시 읽어 대상을 덮지 않는다(`fact_reply(retarget=False)`).

전에는 08:40 에 「다음 일정 뭐야?」라고 물었는데 답을 쓰는 단계가 문장을 다시 읽어 마지막 일정을 짚고
「성수동 저녁(18:30) 뒤로는 남은 일정이 없어요」라고 답했다(x600 서버 웹 채팅 시험 2026-10-13, 처리 기록 435번).
"""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.conversation import trip_facts
from app.domains.travel_ops.instances._shared import itinerary_team

KST = ZoneInfo("Asia/Seoul")


def _item(seq, day, hour, title, kind="activity"):
    return SimpleNamespace(item_id=uuid4(), seq=seq, kind=kind, title=title, place={"name": title}, detail={},
                           starts_at=datetime(2026, 10, day, hour, 0, tzinfo=KST),
                           ends_at=datetime(2026, 10, day, hour + 1, 0, tzinfo=KST))


ITEMS = [_item(1, 13, 9, "서울역 도착"), _item(2, 13, 12, "점심", "dining"), _item(3, 14, 18, "성수동 저녁", "dining")]
NOW = datetime(2026, 10, 13, 8, 40, tzinfo=KST)


@pytest.fixture()
def pointer_picks_the_last_item():
    """문장을 다시 읽으면 마지막 일정을 짚는 상황(일정 짚기 모델의 오답)을 흉내 낸다."""
    itinerary_team.set_item_pointer(lambda items, text, rule: items[-1] if items else None)
    yield
    itinerary_team.set_item_pointer(None)


def test_without_retarget_the_next_item_is_counted_from_now(pointer_picks_the_last_item):
    text, basis = trip_facts.fact_reply("next", message="다음 일정 뭐야?", items=ITEMS, now=NOW, retarget=False)
    assert "서울역 도착" in text and "남은 일정이 없어요" not in text, text
    assert basis["item"] is None


def test_the_old_retargeting_path_is_kept_for_callers_that_have_no_decision(pointer_picks_the_last_item):
    text, _ = trip_facts.fact_reply("next", message="다음 일정 뭐야?", items=ITEMS, now=NOW)
    assert "성수동 저녁" in text                                # 결정 단위가 없는 옛 경로는 그대로다


def test_a_named_item_given_by_the_decision_is_still_used():
    text, basis = trip_facts.fact_reply("next", message="점심 다음은?", items=ITEMS, now=NOW, item=ITEMS[1], retarget=False)
    assert "성수동 저녁" in text and basis["item"] == "점심"
