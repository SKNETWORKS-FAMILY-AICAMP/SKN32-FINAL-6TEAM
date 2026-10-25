"""W03·W06·W08·W12: 모델 출력 경계와 실제 조립 계산 경로의 격리 인수 시험."""
from copy import deepcopy
from datetime import date
import json
from uuid import uuid4

import pytest

from app import composition
from app.domains.travel_ops.components.planning import execution_plan as ep
from app.domains.travel_ops.components.planning import guardian, pending, survey
from app.domains.travel_ops.components.itinerary.itinerary_changes import NoChange
from app.domains.travel_ops.components.watch import trip_watch_batch as batch
from app.domains.travel_ops.components.watch.batch_executor import TravelBatchExecutor
from tests.unit.travel.activity.test_watch_batch_unit import _item, _place, _world, ROAD
from tests.unit.travel.execution_plan_fixture import fixture_plan


def _contract():
    ids = [str(uuid4()), str(uuid4())]
    teams = {k: {"tools": ["read.itinerary", "read.disruptions"], "max_calls": 12} for k in ("activity", "dining")}
    issues = [{"item_id": ids[0], "kind": "activity"}, {"item_id": ids[1], "kind": "dining"}]
    raw = {"schema_version": "1.0", "base_version": 7, "steps": [
        {"item_id": ids[i], "team_id": issues[i]["kind"], "order": i+1, "priority": 1,
         "depends_on": [] if i == 0 else [ids[0]], "tools": teams[issues[i]["kind"]]["tools"],
         "max_calls": 12, "reason": "선행 변경의 최신 초안이 필요함"} for i in range(2)]}
    return raw, issues, teams


def test_complete_plan_is_strictly_validated_and_hash_is_stable():
    raw, issues, teams = _contract()
    plan = ep.validate_plan(raw, version=7, issues=issues, teams=teams)
    assert plan.steps[1].depends_on == [plan.steps[0].item_id]
    assert plan.evidence() == ep.validate_plan(deepcopy(raw), version=7, issues=issues, teams=teams).evidence()
    assert plan.evidence()["prompt_sha256"] == ep.PROMPT_HASH


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(base_version=6),
    lambda r: r.update(unexpected="execute payment"),
    lambda r: r["steps"][0].update(team_id="booking"),
    lambda r: r["steps"][0].update(team_id="dining"),
    lambda r: r["steps"][0].update(item_id=str(uuid4())),
    lambda r: r["steps"].pop(),
    lambda r: r["steps"].append(deepcopy(r["steps"][0])),
    lambda r: r["steps"][0].update(order=2),
    lambda r: r["steps"][0].update(order=True),
    lambda r: r["steps"][0].update(priority=0),
    lambda r: r["steps"][0].update(priority=11),
    lambda r: r["steps"][0].update(depends_on=[r["steps"][1]["item_id"]]),
    lambda r: r["steps"][0].update(depends_on=[r["steps"][0]["item_id"]]),
    lambda r: r["steps"][1].update(depends_on=[r["steps"][0]["item_id"]]*2),
    lambda r: r["steps"][0].update(tools=["write.payment"]),
    lambda r: r["steps"][0].update(tools=[]),
    lambda r: r["steps"][0].update(tools=["read.itinerary"]*2),
    lambda r: r["steps"][0].update(max_calls=13),
    lambda r: r["steps"][0].update(max_calls="12"),
    lambda r: r["steps"][0].update(reason="  "),
    lambda r: r["steps"][0].update(action="apply"),
])
def test_untrusted_model_output_cannot_expand_authority(mutation):
    raw, issues, teams = _contract()
    mutation(raw)
    with pytest.raises(ep.PlanFailed):
        ep.validate_plan(raw, version=7, issues=issues, teams=teams)


def test_aggregate_budget_is_enforced(monkeypatch):
    raw, issues, teams = _contract()
    actual = ep.get_guardrails()
    class Limit:
        def get(self, key):
            return 23 if key == "travel.watch.plan_max_tool_calls" else actual.get(key)
    monkeypatch.setattr(ep, "get_guardrails", lambda: Limit())
    with pytest.raises(ep.PlanFailed, match="budget"):
        ep.validate_plan(raw, version=7, issues=issues, teams=teams)


def test_classifier_receives_query_latest_itinerary_situation_and_only_recorded_preferences():
    item = _item(1, "activity", "서울 관람", 10, _place("서울 전시관"))
    issue = {"item_id": str(item.item_id), "categories": ["traffic_control"]}
    teams = {"activity": {"tools": ["read.itinerary"], "max_calls": 1}}
    trip = {"version": 8, "constraints": {"survey": {"priority": ["food"], "theme": "박물관", "pace": "default"},
                                         "survey_answered": ["priority", "theme"]}}
    observed = []
    def model(system, body, **_):
        observed.append((system, json.loads(body)))
        # ★`[2026-10-26]` 답 모양 — 항목 id 를 키로 하는 `assignments`(test_execution_plan_assignments.py).
        #   12c: 도구·호출 상한은 답에 없다(담당 Team 선언에서 채운다)
        return {"schema_version": "1.0", "base_version": 8, "assignments": {str(item.item_id): {
            "team_id": "activity", "order": 1, "priority": 1,
            "depends_on": [], "reason": "기록된 선호와 통제 구간"}}}
    plan = ep.classify_plan(query="관람 전에 점검해 주세요", trip=trip, items=[item], issues=[issue], teams=teams, llm=model)
    body = observed[0][1]
    assert body["query"] == "관람 전에 점검해 주세요" and body["base_version"] == plan.base_version == 8
    assert body["recorded_preferences"] == {"priority": ["food"], "theme": "박물관"}
    assert body["issues"][0]["categories"] == ["traffic_control"]
    assert "customer_id" not in body


@pytest.mark.parametrize("failure", [TimeoutError(), ValueError(), RuntimeError()])
def test_provider_failure_is_explicit(failure):
    item = _item(1, "activity", "서울 관람", 10, _place("서울 전시관"))
    def broken(*_):
        raise failure
    with pytest.raises(ep.PlanFailed, match="provider_failed"):
        ep.classify_plan(query="점검", trip={"version": 1}, items=[item],
                         issues=[{"item_id": str(item.item_id)}],
                         teams={"activity": {"tools": ["read.itinerary"], "max_calls": 1}}, llm=broken)


@pytest.mark.asyncio
@pytest.mark.parametrize("include_customer_id", [True, False])
async def test_composition_executes_model_order_with_each_teams_own_scope(monkeypatch, include_customer_id):
    a, d = _place("서울 전시관"), _place("서울 식당", 1)
    first, second = _item(1, "activity", "관람", 10, a), _item(2, "dining", "식사", 13, d)
    tools, task = _world([first, second], [], {a["place_id"]: ROAD, d["place_id"]: ROAD})
    if not include_customer_id:
        tools.values["read.itinerary"]["trip"].pop("customer_id")
    registry = composition.build_registry(tools=tools, llm=object())
    seen = []
    def planner(**kwargs):
        plan = fixture_plan(**kwargs)
        raw = plan.model_dump()
        raw["steps"].reverse()
        for i, step in enumerate(raw["steps"], 1):
            step["order"] = i
            step["reason"] = "식사 우선 성향에 따른 분류 에이전트 배정"
        return ep.ExecutionPlan.model_validate(raw)
    def calculate(work, scoped, ctx, item):
        seen.append((item.kind, work.manifest.team_id, scoped.team_id, scoped.context.team_id, scoped.allowed_tools))
        assert work.manifest.max_steps == registry.require_runnable(item.kind).manifest.max_steps
        return NoChange("clear")
    monkeypatch.setattr(batch, "_planner", lambda _: calculate)
    executor = composition.build_team_executor(registry, execution_planner=planner)
    assert isinstance(executor, TravelBatchExecutor)
    result = await executor.execute(task)
    assert [r[0] for r in seen] == ["dining", "activity"]
    assert all(len(set(r[:4])) == 1 for r in seen)
    assert seen[0][4] == registry.require_runnable("dining").manifest.allowed_tools
    assert result.decisions[-1]["execution_plan"]["plan"]["steps"][0]["team_id"] == "dining"


@pytest.mark.asyncio
async def test_failed_prerequisite_defers_only_its_dependant(monkeypatch, caplog):
    places = [_place(name, i) for i, name in enumerate(("서울 전시관", "서울 정원", "서울 박물관"))]
    items = [_item(i+1, "activity", p["name"], 10+i*2, p) for i,p in enumerate(places)]
    tools, task = _world(items, [], {p["place_id"]: ROAD for p in places})
    registry = composition.build_registry(tools=tools, llm=object())
    called = []
    def planner(**kwargs):
        raw = fixture_plan(**kwargs).model_dump()
        raw["steps"][1]["depends_on"] = [str(items[0].item_id)]
        return ep.ExecutionPlan.model_validate(raw)
    def calculate(work, scoped, ctx, item):
        called.append(item.item_id)
        if item.item_id == items[0].item_id:
            return work._escalate(scoped, "fatal_source_failure")
        return NoChange("clear")
    monkeypatch.setattr(batch, "_planner", lambda _: calculate)
    result = await composition.build_team_executor(registry, execution_planner=planner).execute(task)
    assert called == [items[0].item_id, items[2].item_id]
    assert result.failure_code == "fatal_source_failure"
    assert f"retry:{items[1].item_id}" in result.warnings
    diagnostics = [r.diagnostic for r in caplog.records if hasattr(r, "diagnostic")]
    assert {d["code"] for d in diagnostics} >= {"source_failed", "retry"}
    assert all(d["checked_at"] and d["plan_sha256"] for d in diagnostics)


@pytest.mark.asyncio
async def test_invalid_plan_never_calls_a_team_calculator(monkeypatch):
    p = _place("서울 전시관")
    item = _item(1, "activity", "관람", 10, p)
    tools, task = _world([item], [], {p["place_id"]: ROAD})
    registry = composition.build_registry(tools=tools, llm=object())
    def invalid(**kwargs):
        plan = fixture_plan(**kwargs)
        plan.steps[0].tools = ["write.payment"]
        return plan
    monkeypatch.setattr(batch, "_planner", lambda _: pytest.fail("invalid plan was executed"))
    result = await composition.build_team_executor(registry, execution_planner=invalid).execute(task)
    assert result.failure_code == "classification_failed" and not result.action_proposals
    assert tools.calls == [("read.itinerary", {"trip_id": task.context.current_state["subject_ref"]["id"]})]


@pytest.mark.asyncio
async def test_cross_customer_itinerary_response_is_rejected_before_planning():
    p = _place("서울 전시관")
    item = _item(1, "activity", "관람", 10, p)
    tools, task = _world([item], [], {p["place_id"]: ROAD})
    tools.values["read.itinerary"]["trip"]["customer_id"] = str(uuid4())
    registry = composition.build_registry(tools=tools, llm=object())
    result = await composition.build_team_executor(registry, execution_planner=lambda **_: pytest.fail("other customer")).execute(task)
    assert result.failure_code == "action_target_changed"


def _operator_switch(monkeypatch, value):
    """관리 콘솔의 항로 지킴이 값을 이 시험 안에서만 정한다(`value` None = 운영자가 바꾼 값 없음 → 가드레일 기본, 꺼짐).

    ★`[2026-10-23]` 판정은 운영자 값을 먼저 읽는다(`settings_hook.guardian_enabled`). 가드레일 기본값만 바꾸면, 같은 일꾼에서 앞 시험이
    남긴 운영자 값(꺼짐)을 읽어 실행 순서에 따라 실패했다(main CI 전체 시험). 끝나면 원래 읽기 함수로 돌아간다."""
    from app.domains.travel_ops.components import settings_hook
    monkeypatch.setattr(settings_hook, "_reader", None if value is None else (lambda tenant, name: value if name == settings_hook.GUARDIAN else None))


def test_the_guardian_is_off_by_default_even_when_the_customer_chose_replace(monkeypatch):
    """`[2026-10-23 사용자 결정]` 항로 지킴이는 기본 꺼짐 — 관리 콘솔에서 켜지 않으면 고객이 「바꿔 줘」를 골라도 꺼짐이고 먼저 묻는다."""
    _operator_switch(monkeypatch, None)
    enabled = {"survey": {"on_disruption": "replace"}, "survey_answered": ["on_disruption"]}
    item = _item(1, "activity", "서울 관람", 10, _place("서울 전시관"))
    assert guardian.is_on(enabled) is False
    assert pending.decide(constraints=enabled, item=item).action == "ask"


@pytest.mark.parametrize("constraints,on", [
    ({}, False), ({"survey": {"on_disruption": "replace"}}, False),
    ({"survey": {"on_disruption": "replace"}, "survey_answered": []}, False),
    ({"survey": {"on_disruption": "ask_first"}, "survey_answered": ["on_disruption"]}, False),
    ({"survey": {"on_disruption": "replace"}, "survey_answered": ["on_disruption"]}, True),
])
def test_guardian_display_and_decision_share_the_explicit_setting(constraints, on, monkeypatch):
    _operator_switch(monkeypatch, True)   # 관리 콘솔에서 켠 상태에서 고객 설정을 본다(기본은 꺼짐 — 2026-10-23)
    item = _item(1, "activity", "서울 관람", 10, _place("서울 전시관"))
    assert guardian.is_on(constraints) is on
    assert (pending.decide(constraints=constraints, item=item).action == "apply") is on


def test_omitted_answer_is_off_and_booking_metadata_does_not_pin_an_item(monkeypatch):
    _operator_switch(monkeypatch, True)   # 관리 콘솔에서 켠 상태에서 고객 설정을 본다(기본은 꺼짐 — 2026-10-23)
    value = survey.apply_survey({"survey": {"version": survey.SURVEY_VERSION, "pace": "moderate"}}, [date(2026,10,12)])
    assert value["survey"]["on_disruption"] == "ask_first" and not guardian.is_on(value)
    item = _item(1, "activity", "서울 관람", 10, _place("서울 전시관"), booking={"number": "demo"})
    enabled = {"survey": {"on_disruption": "replace"}, "survey_answered": ["on_disruption"]}
    assert pending.decide(constraints=enabled, item=item).action == "apply"
    item.detail["customer_pinned"] = True
    assert pending.decide(constraints=enabled, item=item).reason == "protected"


def test_final_recheck_defers_dependent_proposal_and_nochange_after_prerequisite_removed():
    places = [_place(f"서울 관람 {i}", i) for i in range(4)]
    items = [_item(i+1, "activity", p['name'], 10+i*2, p) for i,p in enumerate(places)]
    teams = {'activity':{'tools':['read.itinerary'], 'max_calls':1}}
    issues = [{'item_id':str(i.item_id), 'kind':'activity'} for i in items]
    plan = fixture_plan(query='점검', trip={'version':1}, items=items, issues=issues, teams=teams)
    plan.steps[1].depends_on = [str(items[0].item_id)]
    plan.steps[2].depends_on = [str(items[1].item_id)]
    work = batch.WatchBatch(None, None, {})
    work.plan = plan
    outcomes = [batch.Outcome(items[0], 'recheck_failed'), batch.Outcome(items[1], 'asked'),
                batch.Outcome(items[2], 'nothing'), batch.Outcome(items[3], 'nothing')]
    assert [o.kind for o in work._final_recheck({'version':1}, items, outcomes)] == [
        'recheck_failed','retry','retry','nothing']


@pytest.mark.asyncio
async def test_planned_tool_budget_is_enforced_in_the_actual_team_calculator(caplog):
    p = _place('서울 전시관')
    item = _item(1,'activity','관람',10,p)
    tools, task = _world([item], [_place('서울 박물관',1)], {p['place_id']:ROAD})
    registry = composition.build_registry(tools=tools, llm=object())
    def limited(**kwargs):
        plan = fixture_plan(**kwargs)
        plan.steps[0].max_calls = 1
        return plan
    result = await composition.build_team_executor(registry, execution_planner=limited).execute(task)
    assert not result.action_proposals
    assert any(getattr(row, 'diagnostic', {}).get('error_code') == 'ToolBudgetExceeded'
               for row in caplog.records)
    assert len(tools.calls) == 2  # 일정 진입 조회 + 해당 단계의 허용 호출 한 번.


@pytest.mark.asyncio
async def test_classification_failure_reaches_injected_collector_without_changing_result(caplog):
    p = _place('서울 전시관')
    item = _item(1, 'activity', '관람', 10, p)
    tools, task = _world([item], [], {p['place_id']: ROAD})
    registry = composition.build_registry(tools=tools, llm=object())
    collected = []

    def failure(**kwargs):
        raise ep.PlanFailed('plan_provider_failed')

    def collect(payload):
        collected.append(payload)
        return {'status': 'spooled', 'event_id': str(uuid4())}

    result = await composition.build_team_executor(registry, execution_planner=failure,
                                                   diagnostic_recorder=collect).execute(task)
    assert result.failure_code == 'classification_failed' and not result.action_proposals
    assert len(collected) == 1 and collected[0]['code'] == 'classification_failed'
    assert collected[0]['customer_id'] == task.context.current_state['customer_id']
    assert collected[0]['trip_id'] == task.context.current_state['subject_ref']['id']
    assert any(getattr(row, 'collection', {}).get('status') == 'spooled'
               for row in caplog.records if getattr(row, 'collection', None))


def test_batch_collector_failure_is_visible_and_does_not_replace_original_failure(caplog):
    from types import SimpleNamespace
    trip_id, customer_id, case_id = uuid4(), uuid4(), uuid4()
    task = SimpleNamespace(context=SimpleNamespace(tenant_id='travel-unit', current_state={'customer_id': str(customer_id)}), case_id=case_id)

    def broken(payload):
        raise OSError('private collector error')

    work = batch.WatchBatch(None, task, {'trip': {'trip_id': trip_id}}, diagnostic_recorder=broken)
    assert work._diagnostic('source_failed')['status'] == 'collection_degraded'
    assert 'status=collection_degraded' in caplog.text
    assert 'private collector error' not in caplog.text
