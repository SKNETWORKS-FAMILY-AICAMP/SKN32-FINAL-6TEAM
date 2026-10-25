"""접수 등록의 현재 판 잠금·필수 식사 확인. 사용자 요청으로 작성만 하고 실행하지 않았다."""
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.components.intake import registration, review, dining_review


def wire(monkeypatch, *, state=("review", 2), issue=None):
    calls = []
    payload = {"revision": 2, "dining_judge": {"status": "completed", "revision": 2}}
    monkeypatch.setattr(review, "intake_state", lambda *args: calls.append("lock") or state)
    monkeypatch.setattr(review, "load", lambda *args: calls.append("load") or payload)
    monkeypatch.setattr(dining_review, "refresh", lambda *args: calls.append("refresh") or payload)
    monkeypatch.setattr(dining_review, "registration_issue", lambda value: issue)
    return calls, payload


def test_the_current_intake_is_locked_before_loading_its_review(monkeypatch):
    calls, payload = wire(monkeypatch)
    assert registration.require_review(SimpleNamespace(), "t", "i", 2) is payload
    assert calls == ["lock", "load", "refresh"]


@pytest.mark.parametrize("code,status", [("intake_dining_check_pending", 409),
                                          ("intake_dining_conditions_unmet", 422)])
def test_the_same_required_judgment_gates_registration(monkeypatch, code, status):
    wire(monkeypatch, issue={"status": status, "code": code, "message": "확인이 필요해요", "detail": {"items": ["0-1"]}})
    with pytest.raises(registration.RegistrationRefused) as caught:
        registration.require_review(SimpleNamespace(), "t", "i", 2)
    assert caught.value.status == status and caught.value.code == code
    assert caught.value.detail == {"items": ["0-1"]}


def test_a_different_revision_is_refused_before_reading_the_review(monkeypatch):
    calls, _ = wire(monkeypatch, state=("review", 3))
    with pytest.raises(registration.RegistrationRefused, match="그 사이") as caught:
        registration.require_review(SimpleNamespace(), "t", "i", 2)
    assert caught.value.code == "stale_revision" and calls == ["lock"]


def test_confirmed_retry_keeps_idempotency_even_if_old_check_would_block(monkeypatch):
    calls, payload = wire(monkeypatch, state=("confirmed", 2),
                          issue={"status": 422, "code": "intake_dining_conditions_unmet"})
    assert registration.require_review(SimpleNamespace(), "t", "i", 2) is payload
    assert calls == ["lock", "load"]


def test_a_failed_check_without_verified_bad_keeps_registration_available(monkeypatch):
    policy = dining_review.registration_issue
    calls, payload = wire(monkeypatch)
    payload["dining_judge"]["status"] = "failed"
    monkeypatch.setattr(dining_review, "registration_issue", policy)
    assert registration.require_review(SimpleNamespace(), "t", "i", 2) is payload
    assert calls == ["lock", "load", "refresh"]


def test_missing_intake_is_not_an_empty_success(monkeypatch):
    calls, _ = wire(monkeypatch, state=None)
    with pytest.raises(registration.RegistrationRefused) as caught:
        registration.require_review(SimpleNamespace(), "t", "i", 2)
    assert caught.value.status == 404 and calls == ["lock"]


@pytest.mark.parametrize("saved,expected", [(("saved-trip",), "saved-trip"), (None, None)])
def test_registration_reuses_a_trip_created_by_another_confirm_path(saved, expected):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            assert params == ("t", "i")

        def fetchone(self):
            return saved

    assert registration.confirmed_trip_id(SimpleNamespace(cursor=Cursor), "t", "i") == expected


@pytest.mark.parametrize("blocked", [True, False])
def test_reopen_commit_holds_the_gate_until_the_same_connection_marks_confirmed(monkeypatch, blocked):
    from contextlib import contextmanager
    from uuid import UUID
    from app.domains.travel_ops.components.intake import reopen_commit, pipeline
    calls = []
    class Conn:
        active = False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        @contextmanager
        def transaction(self):
            self.active = True
            try: yield
            finally: self.active = False
    conn = Conn()
    def gate(current, *args):
        assert current is conn and conn.active
        calls.append("gate")
        if blocked: raise registration.RegistrationRefused(409, "intake_dining_check_pending", "확인 중")
    def write(**kw):
        with kw["connect"]() as current:
            assert current is conn and conn.active
        calls.append("write")
        return 3, True, None
    def mark(current, **kw):
        assert current is conn and conn.active
        calls.append("confirmed")
    monkeypatch.setattr(registration, "require_review", gate)
    monkeypatch.setattr(reopen_commit, "_commit_locked", write)
    monkeypatch.setattr(pipeline, "mark_confirmed", mark)
    args = dict(store=None, connect=lambda: conn, tenant="t", intake_id=UUID(int=1), revision=2,
                reopened={"trip_id": str(UUID(int=2))}, status="review", built=None, now=None)
    if blocked:
        with pytest.raises(reopen_commit.CommitRefused) as caught: reopen_commit.commit(**args)
        assert caught.value.code == "intake_dining_check_pending" and calls == ["gate"]
    else:
        assert reopen_commit.commit(**args) == (3, True, None)
        assert calls == ["gate", "write", "confirmed"]
    assert not conn.active


def test_chat_edit_finishes_the_dining_check_outside_connections_before_commit(monkeypatch):
    from contextlib import contextmanager
    from uuid import UUID
    from app.domains.travel_ops.components.conversation import chat_edit
    from app.domains.travel_ops.components.intake import pipeline, reopen, reopen_commit
    active = []
    state = {"pending": True}
    @contextmanager
    def connect():
        active.append(True)
        try: yield object()
        finally: active.pop()
    monkeypatch.setattr(chat_edit, "_revision", lambda *a: 1)
    monkeypatch.setattr(reopen, "open_for_trip", lambda *a, **kw: (UUID(int=1), False))
    monkeypatch.setattr(reopen, "origins", lambda *a: {})
    monkeypatch.setattr(reopen, "session", lambda *a, **kw: {})
    monkeypatch.setattr(reopen, "cancel", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "_claims", lambda *a: [])
    monkeypatch.setattr(pipeline, "_sources", lambda *a: [{"source_id": "source"}])
    monkeypatch.setattr(pipeline, "view", lambda *a, **kw: None)
    monkeypatch.setattr(pipeline, "draft", lambda *a, **kw: ("review", None, SimpleNamespace()))
    monkeypatch.setattr(pipeline, "mark_confirmed", lambda *a, **kw: None)
    def rejudge(*a, **kw):
        assert not active
        state["pending"] = False
    monkeypatch.setattr(pipeline, "rejudge", rejudge)
    def commit(**kw):
        assert not state["pending"], "채팅 수정도 식당 확인을 마친 뒤 확정해야 한다"
        return 2, True, None
    monkeypatch.setattr(reopen_commit, "commit", commit)
    store = SimpleNamespace(latest=lambda *a: ({"version": 1}, []))
    result = chat_edit._run_locked(store=store, connect=connect, tenant="t", customer_id=UUID(int=2),
                                  trip_id=UUID(int=3), base_version=1, ops=[], lookups=lambda: (None, None, None),
                                  now=None, cause_extra=None)
    assert result["changed"] and not state["pending"]
