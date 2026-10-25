"""모호한 식사 조건 → 질문 → 고객 답 → 현재 판 재검증."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.intake.dining_review import fingerprint
from app.domains.travel_ops.instances.dining.customer_requests import audit_requests
from app.domains.travel_ops.instances.dining.judge import plans_from_review
from tests.unit.travel.test_dining_customer_requests import request


QUOTE = "그 식당은 할랄이어야 해요."


def review():
    return {"revision": 2, "ready": True, "dining_judge": {"revision": 2, "run_id": "run-1", "status": "failed"},
            "items": [{"id": "lunch", "kind": "dining", "date": "2026-10-25", "starts_at": "12:00", "title": "점심",
                       "place": {"name": "점심식당"}, "rows": []},
                      {"id": "dinner", "kind": "dining", "date": "2026-10-25", "starts_at": "18:00", "title": "저녁",
                       "place": {"name": "저녁식당"}, "rows": []},
                      {"id": "museum", "kind": "activity", "date": "2026-10-25", "title": "박물관", "rows": []}]}


def questioned():
    from app.domains.travel_ops.components.intake import dining_questions as dq
    payload = review()
    gap = {"check": "_request", "failure": "request_scope_unclear", "attribute": "halal", "required": True,
           "quote": QUOTE, "request_id": "r1"}
    dq.merge_questions(payload, [gap, {**gap, "item_id": "dinner"}], QUOTE)
    return payload


def answer(payload, ids=None, excluded=False, **kw):
    from app.domains.travel_ops.components.intake import dining_questions as dq
    return dq.apply_answer(payload, revision=2, run_id="run-1", question_id=payload["dining_questions"][0]["id"],
                           item_ids=["dinner"] if ids is None else ids, excluded=excluded, notes=QUOTE, **kw)


def test_question_keeps_the_quote_deduplicates_days_and_only_offers_meals():
    q = questioned()["dining_questions"][0]
    assert q["quote"] == QUOTE and q["attribute"] == "halal" and q["required"] is True
    assert {c["item_id"] for c in q["choices"]} == {"lunch", "dinner"}
    assert q["answer"] is None


def test_answer_is_saved_with_original_condition_and_changes_input_signature():
    payload = questioned()
    changed = answer(payload)
    q = changed["dining_questions"][0]
    assert q["answer"] == {"item_ids": ["dinner"], "excluded": False}
    assert payload["dining_questions"][0]["answer"] is None
    assert fingerprint(payload, QUOTE) != fingerprint(changed, QUOTE)
    assert plans_from_review(changed, QUOTE)[0]["customer_clarifications"][0]["quote"] == QUOTE


def test_explicit_customer_scope_wins_over_a_still_ambiguous_model_inventory():
    changed = answer(questioned())
    current = plans_from_review(changed, QUOTE)[0]
    raw = [request(quote=QUOTE, state="unclear", targets=[])]
    audit = audit_requests(current, raw)
    assert audit.issues == []
    assert audit.requests[0]["item_ids"] == ["dinner"] and audit.requests[0]["state"] == "active"
    assert audit.missing([])[0]["item_id"] == "dinner"


def test_answered_condition_cannot_disappear_when_model_omits_the_inventory_entry():
    current = plans_from_review(answer(questioned()), QUOTE)[0]
    audit = audit_requests(current, [])
    assert audit.requests and audit.missing([])[0]["attribute"] == "halal"


def test_customer_can_cancel_the_condition_without_an_active_check():
    current = plans_from_review(answer(questioned(), ids=[], excluded=True), QUOTE)[0]
    audit = audit_requests(current, [request(quote=QUOTE, targets=["dinner"])])
    assert audit.issues == [] and audit.requests[0]["state"] == "excluded"
    assert audit.missing([]) == []


@pytest.mark.parametrize("targets,excluded", [([], False), (["museum"], False), (["other-customer"], False), (["dinner"], True)])
def test_invalid_answers_do_not_modify_stored_questions(targets, excluded):
    from app.domains.travel_ops.components.intake import dining_questions as dq
    payload = questioned()
    original = deepcopy(payload)
    with pytest.raises(dq.QuestionError) as caught:
        answer(payload, ids=targets, excluded=excluded)
    assert caught.value.status == 422 and payload == original


@pytest.mark.parametrize("patch", [{"run_id": "new-run"}, {"revision": 3}, {"status": "running"}])
def test_old_or_busy_question_tokens_are_rejected(patch):
    from app.domains.travel_ops.components.intake import dining_questions as dq
    payload = questioned()
    payload["dining_judge"].update(patch)
    with pytest.raises(dq.QuestionError) as caught:
        answer(payload)
    assert caught.value.status == 409


def test_quote_must_still_belong_to_the_current_source():
    from app.domains.travel_ops.components.intake import dining_questions as dq
    payload = questioned()
    with pytest.raises(dq.QuestionError):
        dq.apply_answer(payload, revision=2, run_id="run-1", question_id=payload["dining_questions"][0]["id"],
                        item_ids=["dinner"], excluded=False, notes="다른 원문")


def test_questions_do_not_accept_unverified_or_fabricated_quotes():
    from app.domains.travel_ops.components.intake import dining_questions as dq
    payload = review()
    dq.merge_questions(payload, [{"failure": "request_scope_unclear", "quote": "원문에 없음", "attribute": "halal", "required": True}], QUOTE)
    assert payload.get("dining_questions", []) == []


def test_cancelling_a_previously_failed_condition_restores_the_rule_status_only():
    from app.domains.travel_ops.instances.dining import judge
    payload = questioned()
    for item in payload["items"]:
        item.update(status="keep", can_lock=True)
    source = {"quote": QUOTE, "attribute": "halal", "required": True}
    decided = {"dinner": [{"check": "dietary", "verdict": "bad", "required": True, "validated": True,
                           "customer_request": source, "evidence": [{"tool": "check_attributes", "path": "attributes.halal.state", "value": "no"}]}]}
    blocked, _ = judge.merge(payload, decided)
    assert blocked["ready"] is False
    changed = answer(blocked, ids=[], excluded=True)
    assert changed["ready"] is True
    assert next(i for i in changed["items"] if i["id"] == "dinner")["status"] == "keep"


def test_correcting_a_condition_keeps_independent_bad_and_original_rule_issues():
    from app.domains.travel_ops.instances.dining import judge
    payload = questioned()
    payload["ready"] = False
    for item in payload["items"]:
        item.update(status="keep", can_lock=True)
    payload["items"][0].update(status="review", can_lock=False)
    source = {"quote": QUOTE, "attribute": "halal", "required": True}
    blocked, _ = judge.merge(payload, {"dinner": [
        {"check": "dietary", "verdict": "bad", "required": True, "validated": True, "customer_request": source,
         "evidence": [{"tool": "check_attributes", "path": "attributes.halal.state", "value": "no"}]}]})
    changed = answer(blocked, ids=[], excluded=True)
    assert changed["ready"] is False and changed["items"][0]["status"] == "review"


def test_cancel_cannot_remove_an_availability_bad_even_with_a_misattached_request():
    from app.domains.travel_ops.instances.dining import judge
    payload = questioned()
    for item in payload["items"]:
        item.update(status="keep", can_lock=True)
    payload["items"][1]["rows"] = [{"row": "hours", "result": "unknown", "text": "미확인"}]
    source = {"quote": QUOTE, "attribute": "halal", "required": True}
    blocked, _ = judge.merge(payload, {"dinner": [
        {"check": "open_at", "verdict": "bad", "validated": True, "customer_request": source,
         "evidence": [{"tool": "check_open_at", "path": "verdict", "value": "bad"}]}]})
    changed = answer(blocked, ids=[], excluded=True)
    assert changed["ready"] is False
    assert next(i for i in changed["items"] if i["id"] == "dinner")["rows"][0]["result"] == "bad"


def test_availability_checks_do_not_inherit_customer_condition_identity():
    current = plans_from_review(answer(questioned()), QUOTE)[0]
    audit = audit_requests(current, [request(quote=QUOTE, targets=["dinner"])])
    assert audit.source_for({"check": "open_at", "request_id": "r1"}) is None


def test_an_actual_agent_scope_gap_becomes_a_saved_customer_question(monkeypatch):
    from tests.unit.travel.test_dining_customer_requests import run_with_requests, save_result
    result, _ = run_with_requests([request(quote=QUOTE, state="unclear", targets=[])], notes=QUOTE)
    assert any(g["failure"] == "request_scope_unclear" for g in result.missing)
    _, _, saved = save_result(monkeypatch, result, notes=QUOTE)
    q = saved[0]["dining_questions"][0]
    assert q["quote"] == QUOTE and q["answer"] is None
    assert {c["item_id"] for c in q["choices"]} == {"dinner"}


def test_a_customer_answer_for_another_day_does_not_create_checks_for_today():
    from app.domains.travel_ops.components.intake import dining_questions as dq
    payload = review()
    payload["items"][1]["date"] = "2026-10-26"
    dq.merge_questions(payload, [{"failure": "request_scope_unclear", "quote": QUOTE,
                                 "attribute": "halal", "required": True}], QUOTE)
    changed = answer(payload)
    today, tomorrow = plans_from_review(changed, QUOTE)
    assert audit_requests(today, []).missing([]) == []
    assert audit_requests(tomorrow, []).missing([])[0]["item_id"] == "dinner"
