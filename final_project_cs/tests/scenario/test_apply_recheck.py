# -*- coding: utf-8 -*-
"""자동으로 바꾸기 전에 **일정 전체를 다시 판정한다** — D-017 「전체 일정 재검증」. `[2026-10-03 사용자 결정]`

☆왜: 대체 후보는 **항목 하나**만 점검(영업시간 · 날씨 · 같은 사건)해 고른다. 통과한 대체가 앞뒤 항목과 시간이 겹치거나 이동이 안 닿거나 예산 · 결제 조건을 깨는 것은 항목 점검이 못 본다 —
적용기는 그대로 새 버전을 썼다(등록 때만 같은 판정기로 전체를 봤다).

★지키려는 것: ①바꾼 뒤 **새로** 생긴 위반이 하나라도 있으면 적용하지 않고 `ActionRejected("itinerary re-check failed: …")` ②바꾸기 전에 이미 있던 위반은 이 변경의 탓이 아니라 막지 않는다
③고객이 고른 변경 · 되돌리기는 이 문을 안 지난다 ④감시는 이 거절을 고객에게 알린다(다른 `action_rejected` 는 운영자 몫이라 알리지 않는다).

재현:

    python -m pytest tests/scenario/test_apply_recheck.py tests/e2e/test_watch_failures.py -v
"""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.actions import ActionRejected
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.actions.itinerary_actions import (ACTION_TYPE, RECHECK_FAILED, ItineraryApply, change_arguments,
                                                      introduced_violations)
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange

from .test_case_version_day import case_world  # noqa: F401 — 픽스처를 그대로 쓴다


def _trip(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def _activity_followed_by_something(items):
    ordered = sorted(items, key=lambda i: (i.starts_at, i.seq))
    for earlier, later in zip(ordered, ordered[1:]):
        if earlier.kind == "activity" and earlier.place is not None and later.kind != "mobility":
            return earlier, later
    raise AssertionError("시나리오에 활동 바로 뒤에 다른 항목이 오는 곳이 없다")


def _overlapping_replacement(item, later):
    """같은 장소 · 같은 시작이지만 **다음 항목이 시작한 뒤까지** 끝나는 대체 — 앞뒤와 겹친다."""
    return item.replaced_by(place=item.place, title=item.title + "(대체)",
                            ends_at=later.starts_at + timedelta(minutes=30))


def test_introduced_violations_are_only_the_ones_the_change_created(case_world):
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    replacement = _overlapping_replacement(item, later)
    changed = [replacement if i.item_id == item.item_id else i for i in items]

    introduced = introduced_violations(trip, items, changed)
    assert [v.code for v in introduced] == ["overlap"]
    assert introduced[0].seq == (item.seq, later.seq)
    # 이미 겹쳐 있던 일정에서 같은 겹침을 만든 것은 이 변경의 탓이 아니다 — 새 위반이 아니다
    assert introduced_violations(trip, changed, changed) == []
    # 겹치지 않는 변경(제목만)은 새 위반이 없다
    harmless = [i.replaced_by(place=i.place, title="이름만") if i.item_id == item.item_id else i for i in items]
    assert introduced_violations(trip, items, harmless) == []


# invariant: INV-CS-ACT-004
def test_an_automatic_change_that_breaks_the_whole_itinerary_is_not_applied(case_world):
    trip, items = _trip(case_world)
    item, later = _activity_followed_by_something(items)
    change = ItineraryChange(reason="auto_adjusted", causes=[{"category": "traffic_control", "kind": "road_closed"}],
                             notice={"text": "대체했어요"}, replacements={item.item_id: _overlapping_replacement(item, later)},
                             summary={"from": item.title, "to": item.title + "(대체)"})
    arguments = change_arguments(trip_id=case_world["trip_id"], base_version=trip["version"], change=change)
    assert arguments["reason"] == "auto_adjusted"

    with get_connection() as conn, conn.transaction():
        with pytest.raises(ActionRejected) as refused:
            ItineraryApply().apply(conn, tenant_id=case_world["tenant"], customer_id=case_world["customer"],
                                   case_id=uuid4(), arguments=arguments)
    assert str(refused.value).startswith(RECHECK_FAILED) and "겹친다" in str(refused.value)
    assert _trip(case_world)[0]["version"] == trip["version"]                       # ★아무것도 안 바뀌었다


def test_the_customer_chosen_reasons_do_not_go_through_the_gate():
    """고객이 직접 고른 변경(다른 안으로 · 되돌리기 · 제안 고르기)은 그 자체가 답이다 — 문 목록이 코드에 그대로 있다."""
    from app.domains.travel_ops.components.actions.itinerary_actions import CHOSEN_BY_CUSTOMER

    assert CHOSEN_BY_CUSTOMER == {"customer_request", "rollback", "customer_choice"}
    import inspect

    source = inspect.getsource(ItineraryApply.apply)
    assert 'str(arguments["reason"]) not in CHOSEN_BY_CUSTOMER' in source and "introduced_violations" in source
    assert ACTION_TYPE == "itinerary.apply"
