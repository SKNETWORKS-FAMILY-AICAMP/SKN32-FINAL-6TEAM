"""고객 고정(`detail.customer_pinned`)도 채팅 「다른 곳으로 바꿔」(apply_change) · 근처 식당 바꾸기 · 적용기 안전망이 지킨다. `[2026-10-27 B 채팅 전수검사]`

☆등록한 여행에서 고객이 「이 일정은 고정해 주세요」(접수) · 채팅 「○○ 고정해줘」로 고정한 일정은 `locked=False` ·
  `detail.customer_pinned=True` 로 저장된다(`intake.assemble` · `reopen.plan_edit`). T16 보호(`test_protected_chat_change.py`)는
  `locked` · `booking_id` 만 봐서, 고객이 고정한 일정이 「다른 데로 바꿔줘」에 서버가 고른 대안으로 바뀌고 고정 표시도 사라졌다
  (범위 옮기기는 064208bd 에서 같은 칸을 보도록 고쳤다). Codex 검토(codex/q1.out 2-1): 세 경로 모두 고객 고정을 보호 대상으로.
★이름을 직접 말한 바꾸기 · 빼기 · 시각 옮기기(`chat_edit`)의 「나중에 한 직접 요청이 이긴다」(10-15 결정)는 그대로다(2-2 — 이 시험 밖).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.actions import ActionRejected
from app.core.contracts import ContextPack, NextAction, TeamTask
from app.domains.travel_ops.components.actions.itinerary_actions import ItineraryApply
from app.domains.travel_ops.components.itinerary.itinerary import Item, item_to_dict
from app.domains.travel_ops.instances.activity.team import ActivityTeam
from app.domains.travel_ops.instances.dining.team import DiningTeam

from .test_protected_chat_change import HOME, START, Tools, applier_world, arguments_for, run

PINNED = {"customer_pinned": True}


def pinned_world(team_cls, *, action="apply_change"):
    kind = team_cls.manifest.team_id
    trip_id, case_id = uuid4(), uuid4()
    home = {**HOME, "place_id": str(uuid4()), "kind": kind}
    item = Item(uuid4(), 1, kind, "원래 곳", UUID(home["place_id"]), START, START + timedelta(hours=1), detail=dict(PINNED), place=home)
    candidate = {**home, "place_id": str(uuid4()), "name": "새 곳", "latitude": 37.5705}
    view = {"trip": {"trip_id": str(trip_id), "version": 1}, "items": [item_to_dict(item) | {"place": home}]}
    state = {"customer_id": str(uuid4()), "subject_ref": {
        "kind": "trip", "id": str(trip_id), "base_version": 1, "part_id": str(item.item_id),
        "request": {"type": "conversation", "action": action, "at": START.isoformat()}}}
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id=kind, tenant_id="travel_unit",
                          knowledge_scope=[], current_state=state, estimated_input_tokens=0)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id=kind,
                    capability=f"{kind}.itinerary", case_version=1, input_text="원래 곳 다른 데로 바꿔줘",
                    context=context, allowed_tools=team_cls.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(minutes=1))
    tools = Tools(view)
    tools.catalog = [home, candidate]
    return team_cls(tools), task


@pytest.mark.parametrize("team_cls", [ActivityTeam, DiningTeam])
@pytest.mark.parametrize("action", ["apply_change", "propose_alternatives"])
def test_team_refuses_chat_change_of_customer_pinned_item(team_cls, action):
    work, task = pinned_world(team_cls, action=action)
    result = run(work, task)
    assert not result.action_proposals                     # 일정 · 보류 제안 어느 쪽도 쓰지 않는다
    assert result.next_action == NextAction.RESPOND
    assert result.decisions[0]["itinerary"] == "edit_refused"
    assert result.decisions[0]["reason"] == "item_locked"
    assert "고정한 일정이라 바꾸지 않았어요" in result.answer and "고정 풀어줘" in result.answer


def test_applier_rejects_customer_request_replacing_customer_pinned_item(monkeypatch):
    store, customer_id, trip_id, current, replacement = applier_world(monkeypatch)
    current.detail = dict(PINNED)
    with pytest.raises(ActionRejected) as refused:
        ItineraryApply().apply(object(), tenant_id="travel_unit", customer_id=customer_id, case_id=uuid4(),
                               arguments=arguments_for(trip_id, current, replacement, "customer_request"))
    assert "item_locked" in str(refused.value)
    assert store.appended == []


def test_applier_keeps_customer_choice_on_customer_pinned_item(monkeypatch):
    store, customer_id, trip_id, current, replacement = applier_world(monkeypatch)
    current.detail = dict(PINNED)
    applied = ItineraryApply().apply(object(), tenant_id="travel_unit", customer_id=customer_id, case_id=uuid4(),
                                     arguments=arguments_for(trip_id, current, replacement, "customer_choice"))
    assert applied.result_ref == f"trip:{trip_id}:v2"


def test_near_dining_change_refuses_customer_pinned_meal(monkeypatch):
    from types import SimpleNamespace

    from app.domains.travel_ops.components.conversation.trip_desk import TripDesk

    meal = SimpleNamespace(item_id=uuid4(), kind="dining", locked=False, booking_id=None, detail=dict(PINNED),
                           starts_at=START, ends_at=START + timedelta(hours=1), title="점심")
    desk = TripDesk.__new__(TripDesk)
    desk._read = lambda trip_id: ({"version": 3}, [meal], [])
    out = desk.near_alternate(trip_id=uuid4(), item_id=meal.item_id, base_version=3,
                              origin={"latitude": 37.5, "longitude": 127.0})
    assert out["status"] == "edit_refused" and out["reason"] == "locked_item"
