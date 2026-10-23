"""Dining에 전달된 자유문의 조건·대상·누락. 사용자 요청으로 작성만 하며 실행하지 않는다."""
from copy import deepcopy
from contextlib import nullcontext
import json

import pytest

from app.domains.travel_ops.instances.dining.agent import judge_day
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools
from app.domains.travel_ops.instances.dining.customer_requests import audit_requests
from app.domains.travel_ops.instances.dining.judge import plans_from_review
from app.infrastructure.llm.tool_chat import ToolTurn


UID = "11111111-1111-1111-1111-111111111111"
NOTES = "점심은 채식이면 좋겠어요. 저녁은 할랄이 필수예요. 카드는 필요 없어요."


def plan(notes=NOTES):
    return {"date": "2026-10-25", "customer_notes": notes, "items": [
        {"item_id": "lunch", "kind": "dining", "title": "점심", "start": "2026-10-25T12:00", "place": {"place_uid": UID}},
        {"item_id": "dinner", "kind": "dining", "title": "저녁", "start": "2026-10-25T18:00", "place": {"place_uid": UID}},
        {"item_id": "museum", "kind": "activity", "title": "박물관"}],
        "itinerary_context": [{"item_id": "next-lunch", "kind": "dining", "date": "2026-10-26", "day": 2, "title": "둘째 날 점심"}]}


def request(rid="r1", attribute="halal", targets=None, required=True, state="active", quote="저녁은 할랄이 필수예요."):
    return {"request_id": rid, "quote": quote, "attribute": attribute, "item_ids": ["dinner"] if targets is None else targets,
            "required": required, "state": state}


def condition(rid="r1", code="dietary", attribute="halal", required=True, verdict="bad"):
    return {"check": code, "request_id": rid, "required": required, "verdict": verdict,
            "evidence": [{"call_id": "c3", "path": f"attributes.{attribute}.state", "value": "no"}]}


def test_long_original_notes_and_other_days_remain_available_inside_dining():
    notes = "여행 이야기가 길어요. " * 400 + "둘째 날 저녁은 할랄이 필수예요."
    review = {"items": [
        {"id": "first", "kind": "dining", "day": 1, "date": "2026-10-25", "title": "첫날 점심", "starts_at": "12:00", "place": {"name": "첫 식당"}},
        {"id": "second", "kind": "dining", "day": 2, "date": "2026-10-26", "title": "둘째 날 저녁", "starts_at": "18:00", "place": {"name": "둘째 식당"}}]}
    original = deepcopy(review)
    plans = plans_from_review(review, notes)
    assert [p["customer_notes"] for p in plans] == [notes, notes]
    assert [i["item_id"] for i in plans[0]["itinerary_context"]] == ["first", "second"]
    assert plans[0]["itinerary_context"][1]["day"] == 2
    assert plans[0]["itinerary_context"][1]["date"] == "2026-10-26"
    assert review == original


@pytest.mark.parametrize("raw, failure", [(None, "request_inventory_missing"), ({}, "request_inventory_malformed")])
def test_reading_is_not_reported_as_complete_without_a_condition_inventory(raw, failure):
    assert {i["failure"] for i in audit_requests(plan(), raw).issues} == {failure}


def test_empty_notes_preserve_existing_callers_without_inventing_a_customer_request():
    audit = audit_requests(plan(""), None)
    assert not audit.enabled and audit.issues == []
    assert audit.validate("lunch", condition()) is None


@pytest.mark.parametrize("patch,failure", [
    ({"quote": "원문에 없는 할랄 필수"}, "request_quote_not_in_source"),
    ({"item_ids": ["invented"]}, "request_unknown_item"),
    ({"item_ids": ["museum"]}, "request_not_a_meal"),
    ({"item_ids": []}, "request_scope_unclear"),
    ({"required": "true"}, "request_invalid_requirement"),
    ({"attribute": "vegan"}, "request_unsupported_attribute"),
    ({"state": "unclear", "item_ids": []}, "request_scope_unclear"),
])
def test_invalid_or_unclear_request_metadata_is_visible(patch, failure):
    audit = audit_requests(plan(), [{**request(), **patch}])
    assert failure in {i["failure"] for i in audit.issues}


def test_a_dinner_condition_cannot_be_used_for_lunch_or_have_its_requirement_softened():
    audit = audit_requests(plan(), [request()])
    assert audit.validate("dinner", condition()) is None
    assert audit.validate("lunch", condition()) == "request_other_item"
    assert audit.validate("dinner", condition(required=False)) == "request_requirement_mismatch"
    assert audit.validate("dinner", condition(attribute="vegetarian")) == "request_wrong_attribute"


def test_preference_is_not_promoted_to_a_requirement():
    req = request(attribute="vegetarian", targets=["lunch"], required=False, quote="점심은 채식이면 좋겠어요.")
    audit = audit_requests(plan(), [req])
    assert audit.validate("lunch", condition(attribute="vegetarian", required=False)) is None
    assert audit.validate("lunch", condition(attribute="vegetarian", required=True)) == "request_requirement_mismatch"


def test_negated_or_cancelled_conditions_do_not_activate_a_check():
    req = request(attribute="card", required=False, state="excluded", targets=[], quote="카드는 필요 없어요.")
    audit = audit_requests(plan(), [req])
    assert audit.issues == [] and audit.missing([]) == []
    assert audit.validate("dinner", condition(code="payment", attribute="card", required=False)) == "request_not_active"


def test_effective_correction_uses_its_complete_original_context():
    notes = "할랄 필수라고 했는데 취소할게요. 저녁은 채식이면 좋겠어요."
    excluded = request(state="excluded", required=False, targets=[], quote="할랄 필수라고 했는데 취소할게요.")
    preferred = request("r2", "vegetarian", required=False, quote="저녁은 채식이면 좋겠어요.")
    audit = audit_requests(plan(notes), [excluded, preferred])
    assert audit.validate("dinner", condition()) == "request_not_active"
    assert audit.validate("dinner", condition("r2", attribute="vegetarian", required=False)) is None


def test_other_day_is_valid_context_but_not_a_condition_for_todays_meals():
    notes = "둘째 날 점심만 할랄이 필수예요."
    req = request(targets=["next-lunch"], quote=notes)
    audit = audit_requests(plan(notes), [req])
    assert audit.issues == [] and audit.missing([]) == []
    assert audit.validate("lunch", condition()) == "request_other_item"


def test_halal_and_vegetarian_have_independent_coverage_even_under_one_check_name():
    notes = "저녁은 할랄과 채식 둘 다 필수예요."
    reqs = [request(quote=notes), request("r2", "vegetarian", quote=notes)]
    audit = audit_requests(plan(notes), reqs)
    answered = [{"item_id": "dinner", "checks": [condition()]}]
    gaps = audit.missing(answered)
    assert [(g["item_id"], g["attribute"], g["request_id"]) for g in gaps] == [("dinner", "vegetarian", "r2")]


def test_ambiguous_duplicate_ids_or_conflicting_effective_requirements_are_not_guessed():
    duplicate = audit_requests(plan(), [request(), request()])
    conflict = audit_requests(plan(), [request(), request("r2", required=False)])
    assert "request_duplicate_id" in {i["failure"] for i in duplicate.issues}
    assert "request_conflict" in {i["failure"] for i in conflict.issues}
    assert duplicate.validate("dinner", condition()) == "request_unknown_id"
    assert conflict.validate("dinner", condition()) == "request_unknown_id"


class Tools(DiningTools):
    def _find_place(self, name, lat=None, lng=None):
        return {"verdict": "ok", "found": True, "place_uid": UID, "name": name}

    def _check_open_at(self, place_uid, start, end=None):
        return {"verdict": "bad", "reason": "그날 휴무"}

    def _check_attributes(self, place_uid, wanted):
        return {"attributes": {attr: {"state": "no"} for attr in wanted}}


class Script:
    def __init__(self, final):
        self.turns = [ToolTurn(content=None, tool_calls=[
            {"id": "t1", "name": "find_place", "arguments": {"name": "시험 식당"}},
            {"id": "t2", "name": "check_open_at", "arguments": {"place_uid": UID, "start": "2026-10-25T18:00"}},
            {"id": "t3", "name": "check_attributes", "arguments": {"place_uid": UID, "wanted": ["halal", "vegetarian"]}}]),
            ToolTurn(content=json.dumps(final, ensure_ascii=False))]
        self.calls = 0

    def step(self, messages, tools, final_json=False):
        self.calls += 1
        return self.turns.pop(0)


def run_with_requests(requests, checks=None, notes=NOTES):
    current = plan(notes)
    current["items"] = [current["items"][1]]
    checks = checks or []
    base = [{"check": "found", "verdict": "ok", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]},
            {"check": "open_at", "verdict": "bad", "evidence": [{"call_id": "c2", "path": "verdict", "value": "bad"}]}]
    final = {"items": [{"item_id": "dinner", "place": {"place_uid": UID}, "checks": base + checks}]}
    if requests is not None:
        final["requests"] = requests
    chat = Script(final)
    result = judge_day(current, tools=Tools(lambda: nullcontext(None)), chat=chat)
    return result, chat


def test_missing_customer_condition_is_reported_without_discarding_a_proven_closed_restaurant():
    result, chat = run_with_requests([request()])
    assert result.failure is None and chat.calls == 2
    assert result.items[0]["checks"][1]["verdict"] == "bad"
    assert result.missing == [{"item_id": "dinner", "check": "dietary", "attribute": "halal", "request_id": "r1",
                               "quote": "저녁은 할랄이 필수예요.", "required": True, "failure": "missing_customer_request"}]


def test_a_grounded_condition_keeps_its_original_request_and_needs_no_extra_model_turn():
    result, chat = run_with_requests([request()], [condition()])
    assert result.failure is None and result.missing == [] and chat.calls == 2
    check = result.items[0]["checks"][2]
    assert "failure" not in check and check["customer_request"]["quote"] == "저녁은 할랄이 필수예요."


def test_a_condition_answer_without_an_inventory_is_not_silently_accepted():
    result, _ = run_with_requests(None, [condition()])
    assert result.items[0]["checks"][2]["verdict"] == "unknown"
    assert any(gap["failure"] == "request_inventory_missing" for gap in result.missing)


@pytest.mark.parametrize("request_id", [None, [], {}, 1])
def test_malformed_request_ids_are_visible_without_breaking_other_verified_checks(request_id):
    result, _ = run_with_requests([request()], [{**condition(), "request_id": request_id}])
    assert result.failure is None and result.items[0]["checks"][1]["verdict"] == "bad"
    assert result.items[0]["checks"][2]["failure"] == "request_invalid_id"
    assert all(g["request_id"] is None or isinstance(g["request_id"], str) for g in result.missing)


def save_result(monkeypatch, result, notes=NOTES):
    """저장 경계는 가짜로 두고 Dining run이 넘기는 근거 기록과 합친 결과를 확인한다."""
    from app.domains.travel_ops.components.intake import review as review_module
    from app.domains.travel_ops.instances.dining import judge

    inserted, saved = [], []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            inserted.append(params)

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def transaction(self):
            return nullcontext(self)

        def cursor(self):
            return Cursor()

    review = {"ready": True, "items": [{"id": "dinner", "date": "2026-10-25", "kind": "dining", "title": "저녁",
              "starts_at": "18:00", "status": "keep", "place": {"name": "시험 식당"}, "rows": [
                  {"row": "place", "result": "ok", "text": "확인"}, {"row": "hours", "result": "ok", "text": "확인"}]}]}
    monkeypatch.setattr(judge, "judge_day", lambda *args, **kwargs: result)
    monkeypatch.setattr(review_module, "intake_state", lambda *args: ("review", 1))
    monkeypatch.setattr(review_module, "load", lambda *args: deepcopy(review))
    monkeypatch.setattr(review_module, "store", lambda conn, tenant, intake, revision, payload: saved.append(payload))
    counts = judge.run(Conn, tenant_id="t", intake_id="i", revision=1, review=review, notes=notes,
                       chat=None, model="fake", tools_factory=lambda connect: None)
    return counts, inserted, saved


def test_dining_persistence_keeps_a_verified_bad_when_the_customer_condition_was_not_checked(monkeypatch):
    result, _ = run_with_requests([request()])
    counts, records, saved = save_result(monkeypatch, result)
    assert counts["missing"] == 1 and counts["used"] == 2
    hours = next(r for r in saved[0]["items"][0]["rows"] if r["row"] == "hours")
    assert hours["result"] == "bad" and hours["blocks_registration"] is True
    gap = next(r for r in records if r[5] == "dietary" and r[9] == "missing_customer_request")
    assert json.loads(gap[10])["quote"] == "저녁은 할랄이 필수예요."


def test_request_ids_remain_separate_when_persisting_two_missing_dietary_attributes(monkeypatch):
    notes = "저녁은 할랄과 채식 모두 필수예요."
    result, _ = run_with_requests([request(quote=notes), request("r2", "vegetarian", quote=notes)], notes=notes)
    counts, records, _ = save_result(monkeypatch, result, notes=notes)
    assert counts["missing"] == 2
    gaps = [json.loads(r[10]) for r in records if r[5] == "dietary" and r[9] == "missing_customer_request"]
    assert {(g["request_id"], g["attribute"]) for g in gaps} == {("r1", "halal"), ("r2", "vegetarian")}


def test_multiple_inventory_errors_keep_their_request_and_failure_details(monkeypatch):
    result, _ = run_with_requests([request(quote="원문에 없는 문장"), request("r2", targets=["unknown-meal"])])
    counts, records, saved = save_result(monkeypatch, result)
    assert counts["missing"] == 2
    gaps = [(r[9], json.loads(r[10])) for r in records if r[5] == "_request"]
    assert {(failure, detail["request_id"]) for failure, detail in gaps} == {
        ("request_quote_not_in_source", "r1"), ("request_unknown_item", "r2")}
    assert next(detail for failure, detail in gaps if failure == "request_unknown_item")["item_ids"] == ["unknown-meal"]
    assert next(r for r in saved[0]["items"][0]["rows"] if r["row"] == "hours")["result"] == "bad"
