"""라우팅 감사 12 — 분류 에이전트 계획(`classify_plan`)이 묶음 항목을 모두 덮게 하는 답 모양(`assignments`)과 스키마.

★실측(2026-10-26, 로컬 E4B): 자유 JSON 의 `steps` 배열로 묻자 활동·식사 2항목 중 활동 1단계만 냈다 → `plan_coverage_invalid`.
  항목 id 를 스키마의 필수 키로 묶은 뒤 2·4·6항목 모두 `validate_plan` 을 지났다. 여기서는 모델 없이 그 경계만 본다.
  `validate_plan` 기준은 바꾸지 않는다 — 스키마를 무시한 답(OpenAI json_object 등)도 그대로 막혀야 한다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator

from app.domains.travel_ops.components.core_hooks import feedback
from app.domains.travel_ops.components.planning import execution_plan as ep
from tests.unit.travel.activity.test_watch_batch_unit import _item, _place

TEAMS = {"activity": {"tools": ["read.itinerary", "read.disruptions", "read.place_candidates"], "max_calls": 12},
         "dining": {"tools": ["read.itinerary", "read.dining_state"], "max_calls": 12}}


def _batch():
    a, d = _place("서울 전시관"), _place("서울 식당", 1)
    items = [_item(1, "activity", "관람", 10, a), _item(2, "dining", "식사", 13, d)]
    issues = [{"item_id": str(i.item_id), "categories": ["traffic_control"]} for i in items]
    return items, issues


def _assignment(team, order, depends=(), tools=None, calls=12):
    return {"team_id": team, "order": order, "priority": 2, "depends_on": list(depends),
            "tools": tools or ["read.disruptions" if team == "activity" else "read.dining_state"],
            "max_calls": calls, "reason": "통제 구간 확인"}


def _keyed(items, orders=(1, 2)):
    return {"schema_version": "1.0", "base_version": 3, "assignments": {
        str(i.item_id): _assignment(i.kind, o) for i, o in zip(items, orders)}}


def _plan(items, issues, answer, seen=None):
    def model(system, body, **kw):
        if seen is not None:
            seen.append((system, body, kw))
        return answer
    return ep.classify_plan(query="[감시] 2건이 겹침 — 관람, 식사", trip={"version": 3}, items=items, issues=issues,
                            teams=TEAMS, llm=model)


def test_schema_requires_every_issue_once_with_only_its_owner_values():
    items, issues = _batch()
    enriched = [{**e, "kind": i.kind} for e, i in zip(issues, items)]
    schema = ep.plan_schema(version=3, issues=enriched, teams=TEAMS, max_priority=10)
    keyed = schema["properties"]["assignments"]
    ids = [str(i.item_id) for i in items]
    assert keyed["required"] == ids and set(keyed["properties"]) == set(ids)
    assert keyed["additionalProperties"] is False
    activity = keyed["properties"][ids[0]]["properties"]
    assert activity["team_id"]["enum"] == ["activity"]
    assert activity["tools"]["items"]["enum"] == TEAMS["activity"]["tools"]
    assert activity["depends_on"]["items"]["enum"] == [ids[1]]          # 자기 자신에게 기대지 못한다
    assert activity["order"] == {"type": "integer", "minimum": 1, "maximum": 2}
    assert schema["properties"]["base_version"]["enum"] == [3]
    validator = Draft202012Validator(schema)
    assert validator.is_valid(_keyed(items))
    dropped = _keyed(items)
    dropped["assignments"].pop(ids[1])                                # 실측 결함 모양: 둘째 항목 누락
    assert not validator.is_valid(dropped)
    extra = _keyed(items)
    extra["assignments"][str(uuid4())] = _assignment("activity", 2)
    assert not validator.is_valid(extra)


def test_classifier_call_carries_the_schema_and_an_answer_budget():
    items, issues = _batch()
    seen = []
    plan = _plan(items, issues, _keyed(items), seen)
    _, _, kw = seen[0]
    assert set(kw["schema"]["properties"]["assignments"]["required"]) == {str(i.item_id) for i in items}
    assert kw["num_predict"] >= 160 * len(items)
    assert [s.item_id for s in plan.steps] == [str(i.item_id) for i in items]
    assert plan.evidence()["prompt_version"] == ep.PROMPT_VERSION != "travel-execution-plan-2026-10-12.v1"


def test_model_decides_the_order_and_dependencies():
    items, issues = _batch()
    answer = _keyed(items, orders=(2, 1))
    answer["assignments"][str(items[0].item_id)]["depends_on"] = [str(items[1].item_id)]
    plan = _plan(items, issues, answer)
    assert [s.team_id for s in plan.steps] == ["dining", "activity"]
    assert [s.order for s in plan.steps] == [1, 2]
    assert plan.steps[1].depends_on == [str(items[1].item_id)]


@pytest.mark.parametrize("mutate,code", [
    # 같은 순서 둘 — 다시 번호를 매기지 않는다
    (lambda a, ids: a["assignments"][ids[1]].update(order=1), "plan_order_invalid"),
    # 스키마를 안 지킨 답(OpenAI json_object 경로 등): 빠진 항목 · 남는 항목은 그대로 coverage 로 막힌다
    (lambda a, ids: a["assignments"].pop(ids[1]), "plan_coverage_invalid"),
    (lambda a, ids: a["assignments"].update({str(uuid4()): _assignment("activity", 3)}), "plan_coverage_invalid"),
    # 키 밖의 item_id 로 다른 항목을 가리키지 못한다
    (lambda a, ids: a["assignments"][ids[0]].update(item_id=ids[1]), "plan_schema_invalid"),
    (lambda a, ids: a.update(steps=[]), "plan_schema_invalid"),
    (lambda a, ids: a.update(assignments=[]), "plan_schema_invalid"),
    # 앞선 항목이 아닌 것에 기대면 그대로 막힌다
    (lambda a, ids: a["assignments"][ids[0]].update(depends_on=[ids[1]]), "plan_dependencies_invalid"),
    (lambda a, ids: a["assignments"][ids[0]].update(team_id="dining"), "plan_team_forbidden"),
    (lambda a, ids: a["assignments"][ids[0]].update(tools=["write.payment"]), "plan_tools_forbidden"),
    (lambda a, ids: a["assignments"][ids[0]].update(order="1"), "plan_schema_invalid"),
])
def test_keyed_answers_still_pass_through_the_unchanged_validator(mutate, code):
    items, issues = _batch()
    answer = _keyed(items)
    mutate(answer, [str(i.item_id) for i in items])
    with pytest.raises(ep.PlanFailed, match=code):
        _plan(items, issues, answer)


def test_recorded_v1_answer_that_dropped_the_second_issue_is_rejected():
    """실측 v1 원문 모양(합성 id): 2항목 묶음에 활동 1단계만. 새 경로에서도, 옛 검증에서도 통과하지 못한다."""
    items, issues = _batch()
    v1 = {"schema_version": "1.0", "base_version": 3, "steps": [
        {"item_id": str(items[0].item_id), "team_id": "activity", "order": 1, "priority": 2, "depends_on": [],
         "tools": ["read.disruptions"], "max_calls": 1, "reason": "Check for disruptions affecting the first activity"}]}
    with pytest.raises(ep.PlanFailed, match="plan_schema_invalid"):
        _plan(items, issues, v1)
    with pytest.raises(ep.PlanFailed, match="plan_coverage_invalid"):
        ep.validate_plan(v1, version=3, issues=[{**e, "kind": i.kind} for e, i in zip(issues, items)], teams=TEAMS)


def test_ask_json_sends_the_schema_to_the_local_model_with_the_plan_timeout(monkeypatch):
    calls = []

    class Chat:
        def structured(self, system, user, schema, *, num_predict):
            calls.append((system, user, schema, num_predict))
            return {"ok": True}

        def json(self, *_):
            raise AssertionError("free JSON must not be used when a schema is given")

    built = []
    real = feedback.get_settings()
    monkeypatch.setattr(feedback, "get_settings", lambda: real.model_copy(update={"ollama_base_url": "http://127.0.0.1:9"}))
    monkeypatch.setattr("app.infrastructure.ollama_chat.from_settings", lambda s, *a, **k: built.append(s) or Chat())
    schema = {"type": "object"}
    assert feedback.ask_json("SYS", "본문", schema=schema, num_predict=480) == {"ok": True}
    assert calls == [("SYS", "본문", schema, 480)]
    timeout = float(ep.get_guardrails().get("travel.watch.plan_timeout_seconds"))
    assert built[0].ollama_timeout_seconds == timeout == built[0].llm_failover_total_seconds


def test_ask_json_provider_error_is_a_classification_failure(monkeypatch):
    from app.infrastructure.ollama_chat import OllamaError

    class Chat:
        def structured(self, *a, **k):
            raise OllamaError("timed out")

    real = feedback.get_settings()
    monkeypatch.setattr(feedback, "get_settings", lambda: real.model_copy(update={"ollama_base_url": "http://127.0.0.1:9"}))
    monkeypatch.setattr("app.infrastructure.ollama_chat.from_settings", lambda *a, **k: Chat())
    with pytest.raises(feedback.ClassificationFailed):
        feedback.ask_json("SYS", "본문", schema={"type": "object"})


def test_plan_timeout_covers_measured_local_six_item_plan_and_stays_inside_the_batch_window():
    """실측 6항목(batch_max_items) 유휴 42.3초. 계획도 묶음 시간(team_timeout × batch_time_ratio) 안에서 쓴다."""
    guard = ep.get_guardrails()
    timeout = float(guard.get("travel.watch.plan_timeout_seconds"))
    window = float(guard.get("reliability.team_timeout_seconds")) * float(guard.get("travel.watch.batch_time_ratio"))
    assert int(guard.get("travel.watch.batch_max_items")) == 6
    assert 42.3 < timeout < window
