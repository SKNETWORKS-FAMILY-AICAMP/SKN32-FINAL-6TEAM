"""필수 검사 완료 집계와 현재 접수의 누락 안내 회귀 시험."""
from copy import deepcopy

import pytest

from app.domains.travel_ops.components.intake import dining_review
from app.domains.travel_ops.instances.dining.agent import judge_day
from tests.unit.travel.test_dining_agent import PLAN, TOOL_TURN, Script, _final, _tools
from tests.unit.travel.test_dining_customer_requests import (
    condition, request, run_with_requests, save_result,
)
from tests.unit.travel.test_dining_judge_merge import _result, _review, _run
from tests.unit.travel.test_intake_dining_completion import storage as storage


def test_failed_evidence_does_not_complete_required_open_check():
    check = {"check": "open_at", "verdict": "ok", "evidence": [
        {"call_id": "c2", "path": "verdict", "value": "ok"}]}
    result = judge_day(PLAN, tools=_tools(), chat=Script(TOOL_TURN, _final([check])))
    assert result.items[0]["checks"][0]["failure"]
    assert any(g["check"] == "open_at" for g in result.missing)


def test_honest_unknown_is_an_answer_rather_than_a_missing_check():
    check = {"check": "open_at", "verdict": "unknown", "evidence": []}
    result = judge_day(PLAN, tools=_tools(), chat=Script(TOOL_TURN, _final([check])))
    assert "failure" not in result.items[0]["checks"][0]
    assert not any(g["check"] == "open_at" for g in result.missing)


def _notices(payload):
    return [r for it in payload["items"] for r in it.get("rows", []) if r["row"] == "dining_check"]


def test_missing_attribute_is_visible_without_erasing_proven_bad(monkeypatch):
    result, _ = run_with_requests([request()])
    _, _, saved = save_result(monkeypatch, result)
    notice = _notices(saved[0])[0]
    assert notice["result"] == "unknown" and "할랄" in notice["text"]
    assert notice["missing_checks"][0]["request_id"] == "r1"
    assert next(r for r in saved[0]["items"][0]["rows"] if r["row"] == "hours")["result"] == "bad"
    assert dining_review.registration_issue(saved[0])["code"] == "intake_dining_conditions_unmet"


def test_two_missing_attributes_are_shown_separately_on_the_right_meal(monkeypatch):
    notes = "저녁은 할랄과 채식 모두 필수예요."
    result, _ = run_with_requests([request(quote=notes), request("r2", "vegetarian", quote=notes)], notes=notes)
    _, _, saved = save_result(monkeypatch, result, notes=notes)
    notice = _notices(saved[0])[0]
    assert {g["attribute"] for g in notice["missing_checks"]} == {"halal", "vegetarian"}
    assert "할랄" in notice["text"] and "채식" in notice["text"]


def test_no_notice_when_customer_condition_was_verified(monkeypatch):
    result, _ = run_with_requests([request()], [condition()])
    _, _, saved = save_result(monkeypatch, result)
    assert _notices(saved[0]) == []


def test_missing_check_notice_keeps_existing_ok_and_does_not_block_registration(monkeypatch):
    result = _result([])
    result.missing = [{"item_id": "0-1", "check": "open_at", "failure": "missing_check"}]
    stored = _review(hours="ok")
    _, _, saved = _run(monkeypatch, result, stored)
    notice = _notices(saved[0])[0]
    assert "영업" in notice["text"]
    assert next(r for r in saved[0]["items"][1]["rows"] if r["row"] == "hours")["result"] == "ok"
    assert saved[0]["ready"] is True and dining_review.registration_issue(saved[0]) is None


def test_missing_notice_is_not_written_into_another_meal(monkeypatch):
    result = _result([])
    result.missing = [{"item_id": "other", "check": "open_at", "failure": "missing_check"}]
    _, _, saved = _run(monkeypatch, result, _review(hours="ok"))
    assert not saved or not _notices(saved[0])


@pytest.mark.parametrize("failure", [None, "empty_result"])
def test_empty_answer_still_shows_reported_missing_checks(monkeypatch, failure):
    result = _result([], failure=failure)
    result.missing = [{"item_id": "0-1", "check": "found", "failure": "missing_check"}]
    _, _, saved = _run(monkeypatch, result, deepcopy(_review()))
    assert _notices(saved[0])[0]["missing_checks"][0]["check"] == "found"


def _lifecycle_run(storage, monkeypatch, result, *, notes=""):
    from datetime import datetime, timezone
    from app.domains.travel_ops.instances.dining import judge

    conn, saved = storage
    payload = dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=True,
                                    now=datetime.now(timezone.utc), notes=notes)
    monkeypatch.setattr(judge, "judge_day", lambda *a, **kw: result)
    judge.run(lambda: conn, tenant_id="tenant", intake_id="intake", revision=2, review=payload,
              notes=notes, chat=None, model="fake", tools_factory=lambda c: None)
    return saved["payload"]


def test_lifecycle_checks_customer_coverage_even_if_result_omits_gaps(storage, monkeypatch):
    result = _result([
        {"check": "found", "verdict": "unknown", "evidence": []},
        {"check": "open_at", "verdict": "unknown", "evidence": []},
    ])
    result.requests = [request(targets=["0-1"])]
    payload = _lifecycle_run(storage, monkeypatch, result, notes="저녁은 할랄이 필수예요.")
    assert payload["dining_judge"]["status"] == "failed"
    assert _notices(payload)[0]["missing_checks"][0]["attribute"] == "halal"
    assert dining_review.registration_issue(payload) is None


def test_failed_empty_result_cannot_hide_missing_checks_by_omitting_gaps(storage, monkeypatch):
    payload = _lifecycle_run(storage, monkeypatch, _result([], failure="empty_result"))
    assert {g["check"] for g in _notices(payload)[0]["missing_checks"]} == {"found", "open_at"}
    assert dining_review.registration_issue(payload) is None
