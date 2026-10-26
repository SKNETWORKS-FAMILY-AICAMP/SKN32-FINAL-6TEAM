"""고정 · 예약 일정은 채팅 「다른 곳으로 바꿔」(apply_change)로 우회해 바꾸지 않는다 — D-020 「고정 항목은 우회하지 않는다」.

☆T16(normal49): 보류 제안이 없는데 「네, 제안한 일정 변경을 승인해요」가 apply_change(target=고정 N서울타워)로 해석되자
  Team 의 공용 「다른 안으로」 계산이 그대로 대체안을 만들고, 적용기는 `customer_request` 라 판정 문(`pending.decide`)을 건너뛰어
  고정 항목을 덕수궁으로 바꿨다(새 항목은 `replaced_by` 라 locked=False — 고정 표시도 사라졌다).
★지키는 것: ①Team 입구가 고정 · 예약 대상의 apply_change / propose_alternatives 를 `edit_refused` 로 닫는다(제안 0 · 후보 읽기 0)
  ②적용기는 `customer_request` 교체가 지금 판의 고정 · 예약 항목을 가리키면 쓰지 않고 거절한다(마지막 안전망 — 다른 경로 · 경합)
  ③고정 아닌 항목은 그대로 바뀐다 ④고객이 보류 제안을 고른 것(`customer_choice`)은 막지 않는다(그 자체가 답이다).
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.actions import ActionRejected
from app.core.contracts import ContextPack, NextAction, TeamTask
from app.domains.travel_ops.components.actions import itinerary_actions
from app.domains.travel_ops.components.actions.itinerary_actions import ItineraryApply
from app.domains.travel_ops.components.itinerary.itinerary import Item, item_to_dict
from app.domains.travel_ops.instances.activity.team import ActivityTeam
from app.domains.travel_ops.instances.dining.team import DiningTeam


class Tools:
    def __init__(self, view):
        self.view = view
        self.catalog = []
        self.calls = []

    def call(self, name, context, arguments, allowed_tools, seen, *, budget):
        self.calls.append(name)
        if name == "read.itinerary":
            return self.view
        if name in ("read.place_catalog", "read.place_candidates"):
            return self.catalog
        if name in ("read.dining_states", "read.place_price", "read.dining_state"):
            return None
        return None


START = datetime(2030, 1, 2, 6, tzinfo=UTC)
HOME = {"name": "원래 곳", "latitude": 37.57, "longitude": 126.98,
        "attributes": {"hours": ["00:00", "23:59"], "payment": ["card", "cash"]}}


def world(team_cls, *, locked=False, booked=False, action="apply_change", alternates=None):
    kind = team_cls.manifest.team_id
    trip_id, case_id = uuid4(), uuid4()
    home = {**HOME, "place_id": str(uuid4()), "kind": kind}
    item = Item(uuid4(), 1, kind, "원래 곳", UUID(home["place_id"]), START, START + timedelta(hours=1),
                locked=locked, booking_id=uuid4() if booked else None,
                detail={"alternates": alternates} if alternates else {}, place=home)
    candidate = {**home, "place_id": str(uuid4()), "name": "새 곳", "latitude": 37.5705}
    view = {"trip": {"trip_id": str(trip_id), "version": 1}, "items": [item_to_dict(item) | {"place": home}]}
    state = {"customer_id": str(uuid4()), "subject_ref": {
        "kind": "trip", "id": str(trip_id), "base_version": 1, "part_id": str(item.item_id),
        "request": {"type": "conversation", "action": action, "at": START.isoformat()}}}
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id=kind, tenant_id="travel_unit",
                          knowledge_scope=[], current_state=state, estimated_input_tokens=0)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id=kind,
                    capability=f"{kind}.itinerary", case_version=1, input_text="네, 제안한 일정 변경을 승인해요",
                    context=context, allowed_tools=team_cls.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(minutes=1))
    tools = Tools(view)
    tools.catalog = [home, candidate]
    return team_cls(tools), task, item, candidate


def run(work, task):
    return asyncio.run(work.execute(task))


@pytest.mark.parametrize("team_cls", [ActivityTeam, DiningTeam])
@pytest.mark.parametrize("action", ["apply_change", "propose_alternatives"])
@pytest.mark.parametrize("protection", ["locked", "booked"])
def test_team_refuses_chat_change_of_protected_item(team_cls, action, protection):
    work, task, item, _ = world(team_cls, locked=protection == "locked", booked=protection == "booked", action=action)
    result = run(work, task)
    assert not result.action_proposals                     # 일정 · 보류 제안 어느 쪽도 쓰지 않는다
    assert result.next_action == NextAction.RESPOND
    assert result.decisions[0]["itinerary"] == "edit_refused"
    assert result.decisions[0]["reason"] == ("item_locked" if protection == "locked" else "item_booked")
    assert "바꾸지 않았어요" in result.answer
    # 후보를 찾지도 않는다 — 대상 확인만으로 닫는다
    assert [c for c in work.tools.calls if c not in ("read.itinerary", "read.booking")] == []


def test_team_refuses_stored_alternate_swap_of_locked_item():
    alternates = [{"key": "alt1", "name": "저장된 다른 곳", "place_id": str(uuid4())}]
    work, task, _, _ = world(DiningTeam, locked=True, alternates=alternates)
    result = run(work, task)
    assert not result.action_proposals
    assert result.decisions[0]["itinerary"] == "edit_refused"


@pytest.mark.parametrize("team_cls", [ActivityTeam, DiningTeam])
def test_unprotected_item_still_changes_with_customer_request(team_cls):
    work, task, item, candidate = world(team_cls)
    result = run(work, task)
    assert len(result.action_proposals) == 1
    arguments = result.action_proposals[0].arguments
    assert arguments["reason"] == "customer_request"
    assert arguments["replacements"][0]["item_id"] == str(item.item_id)


# ── 적용기(마지막 안전망) ─────────────────────────────────────────
class FakeStore:
    def __init__(self, trip, items, places):
        self.trip, self.items, self.places_rows = trip, items, places
        self.appended = []

    def __call__(self, tenant_id):
        return self

    def lock_trip(self, conn, trip_id):
        return self.trip["version"]

    def latest(self, conn, trip_id):
        return self.trip, list(self.items)

    def places(self, conn, trip_id=None, **_):
        return self.places_rows

    def message_exists(self, conn, **_):
        return False

    def append_version(self, conn, **kw):
        self.appended.append(kw)
        return self.trip["version"] + 1


class NoPause:
    def __init__(self, tenant_id):
        pass

    def active(self, conn, trip_id):
        return False


def applier_world(monkeypatch, *, locked=False, booked=False):
    from app.domains.travel_ops.components.watch import safety_pause

    customer_id, trip_id = uuid4(), uuid4()
    old_place, new_place = {**HOME, "place_id": str(uuid4()), "kind": "activity"}, \
        {**HOME, "place_id": str(uuid4()), "kind": "activity", "name": "새 곳"}
    current = Item(uuid4(), 1, "activity", "원래 곳", UUID(old_place["place_id"]), START,
                   START + timedelta(hours=1), locked=locked, booking_id=uuid4() if booked else None, place=old_place)
    replacement = current.replaced_by(place=new_place, title="새 곳")
    trip = {"trip_id": str(trip_id), "customer_id": str(customer_id), "version": 1, "constraints": {}}
    store = FakeStore(trip, [current], [old_place, new_place])
    monkeypatch.setattr(itinerary_actions, "TripStore", store)
    monkeypatch.setattr(safety_pause, "SafetyPauses", NoPause)
    return store, customer_id, trip_id, current, replacement


def arguments_for(trip_id, current, replacement, reason):
    return {"trip_id": str(trip_id), "base_version": 1, "reason": reason, "causes": [],
            "notice": {"text": "바꿨습니다"}, "summary": {},
            "replacements": [{"item_id": str(current.item_id), "item": item_to_dict(replacement)}]}


@pytest.mark.parametrize("protection", ["locked", "booked"])
def test_applier_rejects_customer_request_replacing_protected_item(monkeypatch, protection):
    store, customer_id, trip_id, current, replacement = applier_world(
        monkeypatch, locked=protection == "locked", booked=protection == "booked")
    with pytest.raises(ActionRejected) as refused:
        ItineraryApply().apply(object(), tenant_id="travel_unit", customer_id=customer_id, case_id=uuid4(),
                               arguments=arguments_for(trip_id, current, replacement, "customer_request"))
    assert ("item_locked" if protection == "locked" else "item_booked") in str(refused.value)
    assert store.appended == []                           # 새 판을 쓰지 않는다


def test_applier_still_applies_unprotected_customer_request(monkeypatch):
    store, customer_id, trip_id, current, replacement = applier_world(monkeypatch)
    applied = ItineraryApply().apply(object(), tenant_id="travel_unit", customer_id=customer_id, case_id=uuid4(),
                                     arguments=arguments_for(trip_id, current, replacement, "customer_request"))
    assert applied.result_ref == f"trip:{trip_id}:v2"
    assert len(store.appended) == 1


def test_applier_keeps_customer_choice_of_proposal_on_locked_item(monkeypatch):
    """보류 제안을 고객이 `/proposals/{id}/choose` 로 고른 것은 그 자체가 답이다 — 막지 않는다."""
    store, customer_id, trip_id, current, replacement = applier_world(monkeypatch, locked=True)
    applied = ItineraryApply().apply(object(), tenant_id="travel_unit", customer_id=customer_id, case_id=uuid4(),
                                     arguments=arguments_for(trip_id, current, replacement, "customer_choice"))
    assert applied.result_ref == f"trip:{trip_id}:v2"
    assert len(store.appended) == 1
