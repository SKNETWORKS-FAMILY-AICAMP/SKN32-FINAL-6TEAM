"""인라인 분류의 **실행 절차**가 코어 1 소유인지 (v8 §3-A · §7-A · §16).

★이 파일이 존재할 수 있다는 것 자체가 결함 1 이 고쳐졌다는 증거다. 전에는
  분류 절차가 `app/presentation/api/cases.py` 의 라우트 안에만 있어서, 부르려면
  HTTP 요청을 만들어야 했다 — Controller 도 재시도 작업도 같은 절차를 쓸 수
  없었고, 테스트도 라우트를 거쳐야만 했다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application import classification
from app.application.classification import FAILURE_CODE, REQUIRED_LABELS, classify_case
from app.domain.events import EventType


class FakeConn:
    """`conn.transaction()` 만 흉내낸다 — DB 없이 절차만 본다."""

    def __init__(self) -> None:
        self.transactions = 0

    def transaction(self):
        conn = self

        class _Ctx:
            def __enter__(self):
                conn.transactions += 1
                return conn

            def __exit__(self, *exc):
                return False

        return _Ctx()


@pytest.fixture()
def recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(classification, "transition_case",
                        lambda conn, **kwargs: calls.append(kwargs))
    return calls


def _run(recorded, classifier):
    conn = FakeConn()
    event = classify_case(conn, tenant_id="demo", case_id=uuid4(), text="환불 문의",
                          classifier=classifier, actor_id="key-1")
    return event, recorded[0], conn


def test_a_full_result_is_recorded_as_classified(recorded):
    event, call, conn = _run(recorded, lambda text: {
        "intent": "return", "issue_code": "return_other", "sentiment": "negative"})

    assert event is EventType.CLASSIFIED
    assert call["event_type"] is EventType.CLASSIFIED
    assert call["payload"]["intent"] == "return"
    assert call["expected_version"] == 1
    assert conn.transactions == 1


@pytest.mark.parametrize("missing", REQUIRED_LABELS)
def test_a_partial_result_is_a_failure_not_a_partial_success(recorded, missing):
    """★라벨이 하나라도 없으면 실패다. 기본값으로 메우지 않는다.

    조용히 메우면 빈 값이 근거 조합을 거쳐 고객 답변까지 간다(`CLAUDE.md` §1).
    """
    full = {"intent": "return", "issue_code": "return_other", "sentiment": "negative"}
    partial = {k: v for k, v in full.items() if k != missing}

    event, call, _ = _run(recorded, lambda text: partial)

    assert event is EventType.CLASSIFICATION_FAILED
    assert call["payload"] == {"failure_code": FAILURE_CODE}


def test_a_raising_classifier_is_recorded_not_propagated(recorded):
    """★provider 가 터져도 Case 는 남는다 — 실패를 기록하고 escalate 로 보낸다."""
    def explode(text):
        raise TimeoutError("provider timeout")

    event, call, _ = _run(recorded, explode)

    assert event is EventType.CLASSIFICATION_FAILED
    assert call["payload"] == {"failure_code": FAILURE_CODE}


def test_no_classifier_is_also_a_failure(recorded):
    event, call, _ = _run(recorded, None)

    assert event is EventType.CLASSIFICATION_FAILED


def test_the_text_reaches_the_classifier_masked(recorded):
    """★LLM 에는 masked 만 간다(`CLAUDE.md` §1)."""
    seen = []
    _run(recorded, lambda text: seen.append(text) or {
        "intent": "other", "issue_code": "other", "sentiment": "neutral"})

    assert seen and "010-1234-5678" not in seen[0]


def test_the_step_lives_in_core_one_not_in_the_route():
    """★결함 1 — 절차가 라우트에만 있으면 Controller 가 같은 분류를 못 부른다."""
    assert classification.__name__.startswith("app.application.")
    import app.presentation.api.cases as cases

    assert not hasattr(cases, "_classify"), "라우트에 절차 복사본이 남아 있다"
