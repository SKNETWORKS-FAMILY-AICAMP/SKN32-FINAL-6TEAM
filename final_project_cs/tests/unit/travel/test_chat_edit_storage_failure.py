"""채팅 고치기 저장 중 저장소 쓰기 실패 — 일반 500 이 아니라 명시적 실패 답(수용 F03, 2026-10-26 묶음 L).

★DB 없이 `chat_edit._run_locked` 의 경계와 `TripDesk.edit` 의 답 모양만 본다. 실제 롤백 · Case 기록 · 대화 기록 · HTTP 200 은
  `tests/e2e/test_chat_edit_web.py::test_a_storage_failure_while_saving_is_an_explicit_failure_not_a_500` 이 본다.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest

from app.domains.travel_ops.components.conversation import chat_edit
from app.domains.travel_ops.components.conversation.trip_desk import TripDesk
from app.domains.travel_ops.components.intake import pipeline, reopen, reopen_commit

NOW = datetime(2031, 3, 10, 1, tzinfo=timezone.utc)
PRIVATE = "CONTROLLED_PRIVATE_SQL_DETAIL params=(010-1234-5678)"


def _item():
    return SimpleNamespace(item_id=uuid4(), replaces_item_id=None, kind="activity", title="인사동", locked=False,
                           detail={}, seq=1, starts_at=NOW + timedelta(days=1), ends_at=NOW + timedelta(days=1, hours=1),
                           booking_id=None, place=None)


@contextmanager
def _connect():
    yield None


class _ReadbackConn:
    """저장 실패 뒤 다시 읽기용 새 연결 — 실행한 SQL 을 적고, `trips.latest_version` 으로 `version` 을 돌려준다(None 이면 끊김)."""

    def __init__(self, version, sqls):
        self.version, self.sqls = version, sqls

    @contextmanager
    def transaction(self):
        yield

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        if self.version is None:
            raise psycopg.OperationalError("connection lost " + PRIVATE)

    def fetchone(self):
        return (self.version,)


def _world(monkeypatch, *, commit_error=None, confirm_error=None, readback_version=1, sqls=None):
    item, intake_id, steps = _item(), uuid4(), []
    sqls = [] if sqls is None else sqls
    store = SimpleNamespace(latest=lambda conn, trip_id: ({"version": 1}, [item]))
    connections = {"n": 0}

    @contextmanager
    def connect():
        # 저장(commit) 단계 뒤에 여는 연결은 다시 읽기 연결이다
        connections["n"] += 1
        yield _ReadbackConn(readback_version, sqls) if "commit" in steps else None
    monkeypatch.setattr(reopen, "open_for_trip", lambda conn, **kw: (intake_id, False))
    monkeypatch.setattr(chat_edit, "_revision", lambda conn, tenant, intake: 1)
    monkeypatch.setattr(pipeline, "_claims", lambda conn, tenant, intake, revision: [])
    monkeypatch.setattr(pipeline, "_sources", lambda conn, tenant, intake: [{"source_id": "s1"}])
    monkeypatch.setattr(reopen, "origins", lambda claims: {("s1", 0): item.item_id})
    monkeypatch.setattr(reopen, "_policy_locked", lambda i: False)
    monkeypatch.setattr(pipeline, "edit", lambda conn, **kw: 2)
    monkeypatch.setattr(pipeline, "view", lambda conn, **kw: None)
    monkeypatch.setattr(pipeline, "draft", lambda conn, **kw: ("review", None, SimpleNamespace(problems=[])))
    monkeypatch.setattr(reopen, "session", lambda conn, **kw: {"trip_id": "t", "version": 1, "frozen_item_ids": []})
    monkeypatch.setattr(pipeline, "rejudge", lambda *a, **k: None)

    def commit(**kw):
        steps.append("commit")
        if commit_error is not None:
            raise commit_error
        return 2, True, SimpleNamespace()

    def mark_confirmed(conn, **kw):
        steps.append("confirm")
        if confirm_error is not None:
            raise confirm_error

    monkeypatch.setattr(reopen_commit, "commit", commit)
    monkeypatch.setattr(pipeline, "mark_confirmed", mark_confirmed)
    monkeypatch.setattr(reopen, "cancel", lambda conn, **kw: steps.append("cancel"))
    run = lambda: chat_edit._run_locked(store=store, connect=connect, tenant="unit", customer_id=uuid4(),  # noqa: E731
                                        trip_id=uuid4(), base_version=1, ops=[chat_edit.EditOp("remove", item_id=item.item_id)],
                                        lookups=lambda: (None, None, None), now=NOW, cause_extra=None)
    return run, steps


@pytest.mark.parametrize("error", [psycopg.OperationalError(PRIVATE), psycopg.errors.DiskFull(PRIVATE)])
def test_a_storage_failure_before_the_new_version_is_saved_is_an_explicit_unchanged_failure(monkeypatch, error):
    run, steps = _world(monkeypatch, commit_error=error)
    with pytest.raises(chat_edit.EditStorageFailed) as failed:
        run()
    assert failed.value.error == type(error).__name__
    assert "010" not in str(failed.value) and "CONTROLLED_PRIVATE" not in str(failed.value)
    assert steps == ["commit", "cancel"]          # 이 요청이 연 수정 접수도 닫는다(종전 finally 그대로)


def test_a_storage_failure_after_the_version_was_saved_is_not_relabelled_as_unchanged(monkeypatch):
    # ★commit 이 돌아온 뒤에는 새 판이 이미 저장됐다 — 「바꾸지 않았어요」라고 답하면 거짓이다. 그대로 올린다(숨기지 않는다)
    run, steps = _world(monkeypatch, confirm_error=psycopg.OperationalError(PRIVATE))
    with pytest.raises(psycopg.OperationalError):
        run()
    assert steps[:2] == ["commit", "confirm"]


@pytest.mark.parametrize("readback_version", [2, None], ids=["moved", "broken"])
def test_an_unconfirmed_rollback_is_not_answered_as_unchanged(monkeypatch, caplog, readback_version):
    # ★Codex E1: COMMIT 도중 끊기면 저장 여부를 모른다 — 새 연결로 다시 읽어 판이 그대로일 때만 「안 바꿨다」고 답한다
    run, steps = _world(monkeypatch, commit_error=psycopg.OperationalError(PRIVATE), readback_version=readback_version)
    with pytest.raises(psycopg.OperationalError):
        run()
    assert "commit" in steps
    # ★Codex q3: 다시 읽기 실패 기록에는 예외 종류만 — 메시지 · SQL 인자(고객 값)는 남기지 않는다
    assert "010-1234-5678" not in caplog.text and "CONTROLLED_PRIVATE" not in caplog.text


def test_the_readback_waits_for_an_unfinished_save_on_the_trip_row(monkeypatch):
    # ★Codex q3: 끊긴 연결의 COMMIT 이 서버에서 아직 끝나지 않았으면 그 앞을 읽을 수 있다 — 새 판 저장이 UPDATE 하는 trips 행에
    #   FOR SHARE 를 걸어(한도 있음) 앞 트랜잭션이 끝난 뒤 읽는다
    sqls = []
    run, _ = _world(monkeypatch, commit_error=psycopg.OperationalError(PRIVATE), sqls=sqls)
    with pytest.raises(chat_edit.EditStorageFailed):
        run()
    assert sqls[0] == f"SET LOCAL lock_timeout = '{chat_edit.SETTLE_LOCK_TIMEOUT}'"
    assert "FROM trips" in sqls[1] and sqls[1].rstrip().endswith("FOR SHARE")


@pytest.mark.parametrize("error", [psycopg.IntegrityError("dup"), psycopg.ProgrammingError("bad sql")])
def test_code_defects_while_saving_are_not_relabelled_as_storage_failures(monkeypatch, error):
    run, _ = _world(monkeypatch, commit_error=error)
    with pytest.raises(type(error)):
        run()


def test_the_desk_answers_a_storage_failure_as_an_escalated_unchanged_result(monkeypatch):
    item = _item()
    store = SimpleNamespace(tenant_id="unit", latest=lambda conn, trip_id: ({"version": 1, "customer_id": uuid4()}, [item]))
    desk = TripDesk(store=store, connection_factory=_connect)
    monkeypatch.setattr(desk, "_read_plan", lambda: None)
    monkeypatch.setattr(chat_edit, "ops_for", lambda *a, **k: ([chat_edit.EditOp("remove", item_id=item.item_id)], {}))

    def run(**kw):
        raise chat_edit.EditStorageFailed("OperationalError")

    monkeypatch.setattr(chat_edit, "run", run)
    outcome = desk.edit(trip_id=uuid4(), base_version=1, decision=None, now=NOW)
    assert outcome == {"status": "escalated", "reason": "save_failed", "text": chat_edit.SAVE_FAILED_TEXT}
    assert "일정은 바꾸지 않았어요" in outcome["text"] and "OperationalError" not in outcome["text"]
