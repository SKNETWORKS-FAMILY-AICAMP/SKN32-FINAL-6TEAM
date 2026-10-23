"""같은 여행 업무의 고객 답변을 실제 Team 입구에서 검증한다."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, NextAction, TeamTask
from app.domains.travel_ops.components.itinerary.itinerary import Item, item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange
from app.domains.travel_ops.instances._shared import conversation_work
from app.domains.travel_ops.instances.dining.team import DiningTeam


class Tools:
    def __init__(self, view, report=None):
        self.view, self.report = view, report
        self.catalog = []
        self.calls = []

    def call(self, name, context, arguments, allowed_tools, seen, *, budget):
        self.calls.append((name, arguments))
        if name == "read.itinerary":
            return self.view
        if name == "read.customer_report":
            return self.report
        if name == "read.place_catalog":
            return self.catalog
        if name in ("read.dining_states", "read.place_price"):
            return None
        raise AssertionError(f"unexpected tool: {name}")


def task_for(request, *, reply=None, history=None, schema=None, items=None, tools_report=None):
    case_id, trip_id = uuid4(), uuid4()
    start = datetime(2026, 10, 12, 12, tzinfo=UTC)
    items = items or [Item(uuid4(), 1, "dining", "점심 식당", uuid4(), start, start + timedelta(hours=1),
                           place={"place_id": str(uuid4()), "name": "점심 식당"})]
    view = {"trip": {"trip_id": str(trip_id), "version": 1}, "items": [item_to_dict(i) for i in items]}
    state = {"customer_id": str(uuid4()), "subject_ref": {"kind": "trip", "id": str(trip_id),
              "base_version": 1, "request": {"type": "conversation", "at": start.isoformat(), **request}}}
    if reply is not None:
        state["customer_input"] = reply
    if history is not None:
        state["customer_input_history"] = history
    if schema is not None:
        state["required_input_schema"] = schema
    context = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="dining", tenant_id="travel_unit",
                          knowledge_scope=[], current_state=state, estimated_input_tokens=0)
    task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="dining",
                    capability="dining.itinerary", case_version=1, input_text="식사 일정 변경 요청",
                    context=context, allowed_tools=DiningTeam.manifest.allowed_tools,
                    deadline_at=datetime.now(UTC) + timedelta(minutes=1))
    tools = Tools(view, tools_report)
    return DiningTeam(tools), task, items


def run(work, task):
    return asyncio.run(work.execute(task))


def test_missing_minutes_waits_with_question_and_evidence_before_catalog():
    work, task, _ = task_for({"action": "report_delay"})
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert "몇 분" in result.answer
    assert result.required_input_schema["required"] == ["minutes"]
    assert result.evidence and not result.action_proposals
    assert [name for name, _ in work.tools.calls] == ["read.itinerary"]


@pytest.mark.parametrize("reply", ["조금", "-30분", "1.5분", "20~30분", "0분", "010-1234-5678",
                                  "01012345678", "1441분", "24시간 1분", "25시간"])
def test_unusable_minutes_preserve_waiting_without_writes(reply):
    work, task, _ = task_for({"action": "report_delay"}, reply=reply)
    assert run(work, task).next_action == NextAction.WAIT_FOR_INPUT


@pytest.mark.parametrize("value", [True, False, 0, -1, 1441, 1.5, "30"])
def test_request_minutes_requires_integer_in_supported_range(value):
    work, task, _ = task_for({"action": "report_delay", "minutes": value})
    assert run(work, task).next_action == NextAction.WAIT_FOR_INPUT


@pytest.mark.parametrize("text, expected", [("1", 1), ("1440분", 1440), ("24시간", 1440),
                                          (True, None), (False, None), (None, None)])
def test_delay_parser_supported_range_and_non_text_input(text, expected):
    assert conversation_work.delay_minutes(text) == expected


def test_valid_reply_reaches_existing_dining_calculator(monkeypatch):
    import app.domains.travel_ops.instances.dining.team as dining

    received = []
    monkeypatch.setattr(dining, "plan_delay", lambda **kw: (received.append(kw), NoChange("still_fits"))[1])
    work, task, _ = task_for({"action": "report_delay"}, reply="30분이요")
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND
    assert received[0]["minutes"] == 30
    assert not result.action_proposals


def test_old_typed_delay_request_also_waits_for_customer_input():
    work, task, _ = task_for({"type": "delay"})
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert "몇 분" in result.answer


def test_old_typed_delay_request_resumes_with_answer(monkeypatch):
    import app.domains.travel_ops.instances.dining.team as dining

    received = []
    monkeypatch.setattr(dining, "plan_delay", lambda **kw: (received.append(kw), NoChange("still_fits"))[1])
    work, task, _ = task_for({"type": "delay"}, reply="30분이요")
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["minutes"] == 30


def test_target_answer_uses_previous_wait_choices(monkeypatch):
    work, task, items = task_for({"action": "apply_change"}, reply="1번")
    task.context.current_state["required_input_schema"] = {
        "choices": [{"item_id": str(items[0].item_id), "action": "apply_change"}]}
    received = []
    monkeypatch.setattr(conversation_work, "plan_fresh_alternate",
                        lambda **kw: (received.append(kw), NoChange("still_fits"))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["item_id"] == items[0].item_id


def test_ambiguous_item_name_does_not_choose_first_item():
    work, task, items = task_for({"action": "apply_change"}, reply="점심 식당")
    extra = Item(uuid4(), 2, "dining", items[0].title, uuid4(), items[0].starts_at, items[0].ends_at,
                 place=items[0].place)
    work.tools.view["items"].append(item_to_dict(extra))
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert len(result.required_input_schema["choices"]) == 2


def test_rollback_confirmation_declined_returns_no_proposal():
    work, task, _ = task_for({"action": "rollback", "to_version": 1, "confirmed": False}, reply="아니요")
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND
    assert result.answer == "일정은 그대로 두었어요."
    assert not result.action_proposals


def test_unrelated_confirmation_reply_waits():
    work, task, _ = task_for({"action": "rollback", "to_version": 1, "confirmed": False}, reply="언제요?")
    assert run(work, task).next_action == NextAction.WAIT_FOR_INPUT


def test_confirmation_sentence_resumes_rollback(monkeypatch):
    work, task, _ = task_for({"action": "rollback", "to_version": 1, "confirmed": False}, reply="네, 되돌려 줘")
    received = []
    monkeypatch.setattr(work, "_rollback", lambda task, ctx: (received.append(ctx["report"]),
        work.settle(task, ctx, NoChange("still_fits")))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["to_version"] == 1


def test_rollback_version_reply_reaches_existing_rollback(monkeypatch):
    work, task, _ = task_for({"action": "rollback"}, reply="v2")
    received = []
    monkeypatch.setattr(work, "_rollback", lambda task, ctx: (received.append(ctx["report"]),
        work.settle(task, ctx, NoChange("still_fits")))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["to_version"] == 2


def test_missing_rollback_version_preserves_existing_explanation():
    question = "「호텔 조식」은 처음 일정 그대로라 되돌릴 변경이 없어요."
    work, task, _ = task_for({"action": "rollback", "to_version": None, "question": question})
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert result.answer == question
    assert result.required_input_schema["required"] == ["to_version"]
    assert result.evidence and not result.action_proposals


def test_clarify_typed_choice_can_supply_action_and_target(monkeypatch):
    work, task, items = task_for({"action": "clarify"}, reply="1번")
    task.context.current_state["subject_ref"]["request"]["choices"] = [
        {"action": "apply_change", "item_id": str(items[0].item_id)}]
    received = []
    monkeypatch.setattr(conversation_work, "plan_fresh_alternate",
                        lambda **kw: (received.append(kw), NoChange("still_fits"))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["item_id"] == items[0].item_id


def test_unresolved_clarification_keeps_waiting():
    work, task, _ = task_for({"action": "clarify", "question": "어느 식사인가요?"}, reply="글쎄요")
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert result.answer == "어느 식사인가요?"


def test_numeric_choice_is_not_minutes_but_minutes_reply_can_be_numeric(monkeypatch):
    import app.domains.travel_ops.instances.dining.team as dining

    work, task, items = task_for({"action": "clarify"}, reply="1")
    task.context.current_state["subject_ref"]["request"]["choices"] = [
        {"action": "report_delay", "item_id": str(items[0].item_id)}]
    first = run(work, task)
    assert first.next_action == NextAction.WAIT_FOR_INPUT
    assert first.required_input_schema["required"] == ["minutes"]
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="1", customer_input_history=["1", "1"])
    received = []
    monkeypatch.setattr(dining, "plan_delay", lambda **kw: (received.append(kw), NoChange("still_fits"))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["minutes"] == 1


def test_two_questions_preserve_interpreted_action_on_second_resume(monkeypatch):
    import app.domains.travel_ops.instances.dining.team as dining

    work, task, _ = task_for({"action": "clarify"}, reply="식사에 늦어요",
                             tools_report={"type": "delay"})
    first = run(work, task)
    assert first.required_input_schema["required"] == ["minutes"]
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="30분이요", customer_input_history=["식사에 늦어요", "30분이요"])
    received = []
    monkeypatch.setattr(dining, "plan_delay", lambda **kw: (received.append(kw), NoChange("still_fits"))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["minutes"] == 30


def test_clarification_fact_choice_reads_itinerary_without_change():
    work, task, items = task_for({"action": "clarify"}, reply="1번")
    task.context.current_state["subject_ref"]["request"]["choices"] = [
        {"action": "answer_fact", "fact": "time", "item_id": str(items[0].item_id)}]
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND
    assert items[0].title in result.answer
    assert not result.action_proposals


def test_missing_rollback_version_then_confirmation_keeps_version(monkeypatch):
    work, task, _ = task_for({"action": "rollback", "confirmed": False}, reply="v2")
    first = run(work, task)
    assert first.required_input_schema["required"] == ["confirmed"]
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="네", customer_input_history=["v2", "네"])
    received = []
    monkeypatch.setattr(work, "_rollback", lambda task, ctx: (received.append(ctx["report"]),
        work.settle(task, ctx, NoChange("still_fits")))[1])
    assert run(work, task).next_action == NextAction.RESPOND
    assert received[0]["to_version"] == 2


def test_fresh_alternate_returns_real_proposal_without_mutating_read_model():
    work, task, items = task_for({"action": "apply_change"})
    item = items[0]
    home = {"place_id": str(item.place_id), "name": "원래 식당", "kind": "dining",
            "latitude": 37.57, "longitude": 126.98,
            "attributes": {"hours": ["09:00", "23:00"], "payment": ["card", "cash"]}}
    candidate = {**home, "place_id": str(uuid4()), "name": "새 식당", "latitude": 37.5705}
    item.place = home
    work.tools.view["items"] = [item_to_dict(item)]
    work.tools.catalog = [home, candidate]
    task.context.current_state["subject_ref"]["part_id"] = str(item.item_id)
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND
    assert len(result.action_proposals) == 1
    proposal = result.action_proposals[0]
    assert proposal.action_type == "itinerary.apply" and not proposal.approval_required
    assert proposal.arguments["replacements"][0]["item"]["place_id"] == candidate["place_id"]
    assert work.tools.view["trip"]["version"] == 1
    assert work.tools.view["items"][0]["place_id"] == home["place_id"]


def option_request():
    work, task, items = task_for({"action": "propose_alternatives"})
    item = items[0]
    home = {"place_id": str(item.place_id), "name": "원래 식당", "kind": "dining",
            "latitude": 37.57, "longitude": 126.98,
            "attributes": {"hours": ["09:00", "23:00"], "payment": ["card", "cash"]}}
    candidates = [{**home, "place_id": str(uuid4()), "name": "가까운 식당", "latitude": 37.5705},
                  {**home, "place_id": str(uuid4()), "name": "다른 식당", "latitude": 37.5712}]
    item.place = home
    work.tools.view["items"] = [item_to_dict(item)]
    work.tools.catalog = [home, *candidates]
    task.context.current_state["subject_ref"]["part_id"] = str(item.item_id)
    return work, task, item, candidates


def test_proposing_alternatives_waits_and_never_offers_original():
    work, task, item, _ = option_request()
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert result.decisions[0]["itinerary"] == "asked"
    assert len(result.decisions[0]["options"]) == 2
    assert all(o["place_id"] != str(item.place_id) for o in result.decisions[0]["options"])
    assert not result.action_proposals
    assert "바꾸지 않았어요" in result.answer


def test_selecting_second_proposed_option_returns_its_proposal_once():
    work, task, item, _ = option_request()
    first = run(work, task)
    chosen = first.decisions[0]["options"][1]
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="2번", customer_input_history=["2번"])
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND
    assert len(result.action_proposals) == 1
    replacement = result.action_proposals[0].arguments["replacements"][0]["item"]
    assert replacement["place_id"] == chosen["place_id"]
    assert replacement["starts_at"] == chosen["starts_at"]
    assert work.tools.view["items"][0]["place_id"] == str(item.place_id)


def test_changed_proposed_option_is_asked_again_instead_of_silent_substitution():
    work, task, _, candidates = option_request()
    first = run(work, task)
    first_key = first.decisions[0]["options"][0]["place_id"]
    work.tools.catalog = [p for p in work.tools.catalog if p["place_id"] != first_key]
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="1번", customer_input_history=["1번"])
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT
    assert not result.action_proposals
    assert all(o["place_id"] != first_key for o in result.decisions[0]["options"])


def test_relaxed_option_resume_uses_option_key_and_keeps_chosen_time(monkeypatch):
    work, task, item, candidates = option_request()
    task.context.current_state["subject_ref"]["request"]["action"] = "apply_change"
    candidate = candidates[0]
    starts = item.starts_at + timedelta(minutes=30)
    ends = item.ends_at + timedelta(minutes=30)
    option = {"key": candidate["place_id"], "place_id": candidate["place_id"], "name": candidate["name"],
              "starts_at": starts.isoformat(), "ends_at": ends.isoformat()}
    monkeypatch.setattr(conversation_work, "plan_fresh_alternate", lambda **kw:
                        NoChange("relaxed", {"text": "30분 늦추면 갈 수 있어요. 고르시겠어요?", "options": [option]}))
    first = run(work, task)
    assert first.next_action == NextAction.WAIT_FOR_INPUT
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="1번", customer_input_history=["1번"])
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND
    replacement = result.action_proposals[0].arguments["replacements"][0]["item"]
    assert replacement["place_id"] == candidate["place_id"]
    assert replacement["starts_at"] == starts.isoformat()
    assert replacement["ends_at"] == ends.isoformat()
