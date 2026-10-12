"""최근 사실 안내 뒤 숫자 답변이 옛 업무를 재개하지 않는지 확인한다."""
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.contracts import StateConflict
from app.domains.travel_ops.components.conversation import case_dispatch, chat_log


class Conn:
    def __init__(self, rows):
        self.rows = rows
        self.commits = 0

    def cursor(self):
        return nullcontext(self)

    def execute(self, query, args):
        self.args = args

    def fetchall(self):
        return self.rows

    def commit(self):
        self.commits += 1


def prepare(monkeypatch, *, latest="different", explicit=False, token=False,
            replayed=False, extra=False, message="1번", schema=None):
    trip_id, customer_id, waiting, other = uuid4(), uuid4(), uuid4(), uuid4()
    rows = [(waiting, replayed)] + ([(other, False)] if extra else [])
    conn = Conn(rows)
    state = {"trip_message": {"trip_id": str(trip_id)}, "required_input_schema": schema or {
        "required": ["message"], "choices": [{"message": "식당 변경", "label": "식당 변경"}]}}
    cases = {key: {"customer_id": customer_id, "state_json": state} for key, _ in rows}
    monkeypatch.setattr(case_dispatch.repository, "get_case", lambda _, **kwargs: cases[kwargs["case_id"]])
    seen, reads = [], []

    def recent(_, **kwargs):
        reads.append(kwargs)
        if latest == "none":
            return []
        return [{"role": "assistant", "case_id": str(waiting) if latest == "same" else
                 None if latest == "unknown" else str(uuid4())}, {"role": "customer"}]

    monkeypatch.setattr(chat_log, "recent", recent)
    def resume(**kwargs):
        seen.append(kwargs)
        return {"synthetic": True}
    controller = SimpleNamespace(resume=resume, resume_customer_input=resume)
    monkeypatch.setattr(case_dispatch, "response", lambda **kwargs: kwargs)
    call = lambda: case_dispatch.resume_pending(conn, controller=controller, tenant="travel-recency-test",
        trip={"trip_id": trip_id, "customer_id": customer_id}, request_id="reply-one", message=message,
        actor_id="test", case_id=waiting if explicit else None, token="synthetic-token" if token else None,
        expected_version=None)
    return call, seen, reads, conn, waiting, trip_id


@pytest.mark.parametrize("message", ["1", "1번", "1번이요", "1번째!", " 1번요. "])
def test_number_after_a_new_fact_does_not_resume_the_old_question(monkeypatch, message):
    call, seen, reads, conn, _, trip_id = prepare(monkeypatch, message=message)
    assert call() is None
    assert not seen and conn.commits == 0
    assert reads == [{"tenant_id": "travel-recency-test", "trip_id": trip_id}]


@pytest.mark.parametrize("latest", ["same", "none", "unknown"])
def test_same_question_and_legacy_history_keep_resume(monkeypatch, latest):
    call, seen, _, conn, waiting, _ = prepare(monkeypatch, latest=latest)
    assert call()["case_id"] == waiting
    assert len(seen) == 1 and conn.commits == 1


@pytest.mark.parametrize("kind", ["explicit", "token", "replayed"])
def test_explicit_or_replayed_reply_keeps_its_case_after_new_fact(monkeypatch, kind):
    call, seen, reads, _, waiting, _ = prepare(monkeypatch, **{kind: True})
    assert call()["case_id"] == waiting
    assert seen[0]["case_id"] == waiting and reads == []


@pytest.mark.parametrize("message,schema", [
    ("식당 변경", None), ("30분이요", {"required": ["minutes"]}),
])
def test_named_choice_and_typed_duration_keep_existing_matcher(monkeypatch, message, schema):
    call, seen, reads, _, waiting, _ = prepare(monkeypatch, message=message, schema=schema)
    assert call()["case_id"] == waiting
    assert len(seen) == 1 and reads == []


def test_ambiguous_legacy_number_still_requires_a_case(monkeypatch):
    call, seen, _, _, _, _ = prepare(monkeypatch, latest="none", extra=True)
    with pytest.raises(StateConflict, match="업무를 지정"):
        call()
    assert seen == []
