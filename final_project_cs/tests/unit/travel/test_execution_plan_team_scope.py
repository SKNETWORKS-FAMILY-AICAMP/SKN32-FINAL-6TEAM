"""라우팅 감사 12c — 분류 에이전트 계획의 도구 범위·호출 상한은 담당 Team 등록 선언에서 온다.

★실측(2026-10-26, 로컬 E4B): 도구·예산을 모델이 고르게 하자 모든 항목에 `tools=["read.disruptions"]`·`max_calls=1` 을 줬다.
  `validate_plan` 은 통과했지만 Team 계산이 첫 조회에서 예산을 다 써 대체 후보를 볼 수 없었다(제안 0).
  D-017: 분류 에이전트는 담당·순서·우선순위·이유·의존을 정하고, 실행 장치가 권한·도구/시간 예산을 검증한다.
  그래서 모델 답에서 `tools`·`max_calls` 를 빼고, 모델이 고른 `team_id` 의 선언(`allowed_tools`·`max_steps`)으로 채운다.
  모델이 그 필드를 내면 덮어쓰지 않고 거절한다. `validate_plan` 은 바꾸지 않는다.
"""
from __future__ import annotations

import json

import pytest

from app import composition
from app.domains.travel_ops.components.planning import execution_plan as ep
from app.domains.travel_ops.components.watch import trip_watch_batch as batch
from tests.unit.travel.activity.test_watch_batch_unit import ROAD, _item, _place, _world

TEAMS = {"activity": {"tools": ["read.itinerary", "read.disruptions", "read.place_candidates"], "max_calls": 12},
         "dining": {"tools": ["read.itinerary", "read.dining_state"], "max_calls": 9}}
MODEL_FIELDS = {"team_id", "order", "priority", "depends_on", "reason"}


def _batch():
    a, d = _place("서울 전시관"), _place("서울 식당", 1)
    items = [_item(1, "activity", "관람", 10, a), _item(2, "dining", "식사", 13, d)]
    return items, [{"item_id": str(i.item_id), "categories": ["traffic_control"]} for i in items]


def _answer(items, version=3, **extra):
    return {"schema_version": "1.0", "base_version": version, "assignments": {
        str(i.item_id): {"team_id": i.kind, "order": n, "priority": 1, "depends_on": [], "reason": "통제 구간 확인", **extra}
        for n, i in enumerate(items, 1)}}


def _classify(items, issues, answer, seen=None, teams=TEAMS):
    def model(system, body, **kw):
        if seen is not None:
            seen.append((system, json.loads(body), kw))
        return answer
    return ep.classify_plan(query="[감시] 2건이 겹침 — 관람, 식사", trip={"version": 3}, items=items, issues=issues,
                            teams=teams, llm=model)


def test_schema_asks_only_owner_order_priority_dependencies_and_reason():
    items, issues = _batch()
    enriched = [{**e, "kind": i.kind} for e, i in zip(issues, items)]
    schema = ep.plan_schema(version=3, issues=enriched, teams=TEAMS, max_priority=10)
    for value in schema["properties"]["assignments"]["properties"].values():
        assert set(value["properties"]) == MODEL_FIELDS == set(value["required"])
        assert value["additionalProperties"] is False


def test_each_step_gets_its_owner_teams_declared_tools_and_budget():
    items, issues = _batch()
    plan = _classify(items, issues, _answer(items))
    assert [(s.team_id, s.tools, s.max_calls) for s in plan.steps] == [
        ("activity", TEAMS["activity"]["tools"], 12), ("dining", TEAMS["dining"]["tools"], 9)]


@pytest.mark.parametrize("extra", [
    # 실측 v2 원문 모양 — 모든 항목에 read.disruptions 1회
    {"tools": ["read.disruptions"], "max_calls": 1},
    {"tools": ["read.itinerary"]},
    {"max_calls": 12},
])
def test_a_model_that_still_chooses_tools_or_budget_is_refused_not_overwritten(extra):
    items, issues = _batch()
    with pytest.raises(ep.PlanFailed, match="plan_schema_invalid"):
        _classify(items, issues, _answer(items, **extra))


def test_a_team_outside_the_active_list_is_forbidden():
    items, issues = _batch()
    answer = _answer(items)
    answer["assignments"][str(items[1].item_id)]["team_id"] = "lodging"
    with pytest.raises(ep.PlanFailed, match="plan_team_forbidden"):
        _classify(items, issues, answer)


def test_model_input_lists_active_team_ids_without_tool_lists():
    items, issues = _batch()
    seen = []
    _classify(items, issues, _answer(items), seen)
    system, body, kw = seen[0]
    assert body["teams"] == ["activity", "dining"]
    assert "read.place_candidates" not in json.dumps(body) and "max_tool_calls" not in body
    assert '"tools"' not in system and "max_calls" not in system
    assert kw["num_predict"] >= 120 * len(items)


def _model_from_body(order=None):
    def model(system, body, **_):
        data = json.loads(body)
        ids = [issue["item_id"] for issue in data["issues"]]
        kinds = {issue["item_id"]: issue["kind"] for issue in data["issues"]}
        return {"schema_version": "1.0", "base_version": data["base_version"], "assignments": {
            item_id: {"team_id": kinds[item_id], "order": n, "priority": 1, "depends_on": [], "reason": "통제 구간"}
            for n, item_id in enumerate(order(ids) if order else ids, 1)}}
    return model


@pytest.mark.asyncio
async def test_classified_plan_lets_the_real_team_calculator_find_alternatives():
    """계획 → 실제 조립 Team 계산 → 일정 조정 제안. v2 실측 답(1회 예산)이면 같은 세계에서 제안이 0이었다."""
    a1, a2 = _place("가나다 전망대", 0), _place("마바사 정원", 1)
    items = [_item(1, "activity", "전망대 관람", 10, a1), _item(2, "activity", "정원 산책", 13, a2)]
    cands = [_place("아자 박물관", 2), _place("차카 갤러리", 3), _place("타파 공원", 4)]
    tools, task = _world(items, cands, {a1["place_id"]: ROAD, a2["place_id"]: ROAD})
    registry = composition.build_registry(tools=tools, llm=object())
    model = _model_from_body()
    planned = []

    def planner(**kwargs):
        plan = ep.classify_plan(**kwargs, llm=model)
        planned.append(plan)
        return plan
    result = await composition.build_team_executor(registry, execution_planner=planner).execute(task)

    declared = registry.require_runnable("activity").manifest
    assert [(s.tools, s.max_calls) for s in planned[0].steps] == [(list(declared.allowed_tools), declared.max_steps)] * 2
    assert result.outcome == "completed"
    [proposal] = result.action_proposals
    assert len(proposal.arguments["replacements"]) == 2 and len(proposal.arguments["batch"]["applied"]) == 2
    assert sum(1 for name, _ in tools.calls if name == "read.disruptions") > 2      # 후보도 점검했다(1회 예산이면 못 한다)
    evidence = next(d["execution_plan"] for d in result.decisions if "execution_plan" in d)
    assert evidence["tool_scope"] == evidence["budget_source"] == "team_declaration"
    assert evidence["prompt_version"] == ep.PROMPT_VERSION and ep.PROMPT_VERSION.endswith(".v3")


def test_injected_planner_evidence_does_not_claim_the_team_declaration_source():
    items, issues = _batch()
    enriched = [{**e, "kind": i.kind} for e, i in zip(issues, items)]
    raw = ep.plan_from_assignments(_answer(items), TEAMS)
    plan = ep.validate_plan(raw, version=3, issues=enriched, teams=TEAMS)
    assert "tool_scope" not in plan.evidence() and "budget_source" not in plan.evidence()


@pytest.mark.asyncio
async def test_recorded_v2_answer_with_one_call_is_refused_before_any_team_call():
    p = _place("서울 전시관")
    item = _item(1, "activity", "관람", 10, p)
    tools, task = _world([item], [_place("서울 박물관", 1)], {p["place_id"]: ROAD})
    registry = composition.build_registry(tools=tools, llm=object())

    def v2_model(system, body, **_):
        data = json.loads(body)
        return {"schema_version": "1.0", "base_version": data["base_version"], "assignments": {
            data["issues"][0]["item_id"]: {"team_id": "activity", "order": 1, "priority": 2, "depends_on": [],
                                           "tools": ["read.disruptions"], "max_calls": 1, "reason": "통제 확인"}}}
    result = await composition.build_team_executor(
        registry, execution_planner=lambda **kw: ep.classify_plan(**kw, llm=v2_model)).execute(task)
    assert result.failure_code == "classification_failed" and not result.action_proposals
    assert [name for name, _ in tools.calls] == ["read.itinerary"]


def test_declared_watch_team_budgets_fit_the_aggregate_plan_budget():
    """묶음 상한 × 감시 Team 최대 선언 예산 ≤ 계획 총예산 — 선언으로 채운 계획이 `plan_budget_exceeded` 로 막히지 않는다."""
    item = _item(1, "activity", "관람", 10, _place("서울 전시관"))
    tools, task = _world([item], [], {})
    registry = composition.build_registry(tools=tools, llm=object())
    teams = batch.WatchBatch(None, task, {}, registry=registry)._teams()
    assert {"activity", "dining"} <= set(teams)
    guard = ep.get_guardrails()
    assert (int(guard.get("travel.watch.batch_max_items")) * max(t["max_calls"] for t in teams.values())
            <= int(guard.get("travel.watch.plan_max_tool_calls")))
