from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.operations_diagnostics import Event, Spool, record
from app.application.operations_policy import SourcePolicy
from app.application import admin_service


def event(**changes):
    return Event(tenant_id="test_operations", kind="processing_error", code="LOOKUP_FAILED",
                 deployment="test-build", policy_version="test-policy", **changes)


@contextmanager
def unavailable():
    raise OSError("sensitive provider exception must not be logged")
    yield


def test_db_failure_survives_new_spool_instance_and_hides_exception(tmp_path, caplog):
    pending = tmp_path / "pending.sqlite3"
    value = event()
    assert record(value, connection_factory=unavailable, spool=Spool(pending))["status"] == "spooled"
    assert Spool(pending).snapshot()["pending"] == 1
    assert "sensitive provider exception" not in caplog.text
    assert record(value, connection_factory=unavailable, spool=Spool(pending))["status"] == "spooled"
    assert Spool(pending).snapshot()["pending"] == 1


def test_full_spool_keeps_existing_event_and_records_loss(tmp_path):
    spool = Spool(tmp_path / "pending.sqlite3", max_events=1)
    first, second = event(), event()
    assert spool.enqueue(first) == "spooled"
    assert spool.enqueue(second) == "collection_degraded"
    assert spool.snapshot()["pending"] == 1 and spool.snapshot()["lost"] == 1
    assert spool.enqueue(first) == "spooled"
    assert spool.snapshot()["lost"] == 1


def test_byte_limit_and_disk_failure_are_visible(tmp_path, monkeypatch):
    spool = Spool(tmp_path / "pending.sqlite3", max_bytes=1)
    assert record(event(), connection_factory=unavailable, spool=spool)["status"] == "collection_degraded"
    assert spool.snapshot()["lost"] == 1
    monkeypatch.setattr(spool, "enqueue", lambda _: (_ for _ in ()).throw(OSError("disk failed")))
    assert record(event(), connection_factory=unavailable, spool=spool)["status"] == "collection_degraded"


def test_replay_failure_keeps_same_event_for_later(tmp_path):
    spool = Spool(tmp_path / "pending.sqlite3")
    spool.enqueue(event())
    result = spool.replay(unavailable)
    assert result["processed"] == 0 and result["failed"] == 1 and result["pending"] == 1


def test_expired_events_are_not_resurrected(tmp_path):
    spool = Spool(tmp_path / "pending.sqlite3")
    value = event(occurred_at=datetime.now(UTC)-timedelta(days=90))
    assert record(value, connection_factory=unavailable, spool=spool)["status"] == "expired"
    spool.enqueue(value)
    assert spool.replay(unavailable)["expired"] == 1
    assert spool.snapshot()["pending"] == 0


@pytest.mark.parametrize("changes", [{"body": "customer input"}, {"conditions": ["token=secret"]},
    {"deployment": "https://private.invalid"}, {"policy_version": "person@example.invalid"},
    {"occurred_at": datetime.now()}, {"code": "raw text"}])
def test_diagnostics_reject_unnecessary_original_fields(changes):
    base = event().model_dump()
    with pytest.raises(ValidationError):
        Event(**{**base, **changes})


def test_same_fault_groups_across_customers_but_not_deployments():
    a = event(customer_id=uuid4(), conditions=["SOURCE_OFFLINE", "DAYTIME"])
    b = event(customer_id=uuid4(), conditions=["DAYTIME", "SOURCE_OFFLINE", "DAYTIME"])
    assert a.fingerprint() == b.fingerprint()
    assert a.fingerprint() != a.model_copy(update={"deployment": "next"}).fingerprint()


@pytest.mark.parametrize("changes", [{"daily_paid_cap": 101}, {"daily_paid_cap": 1, "trip_paid_cap": 2},
    {"check_interval_seconds": 1}, {"check_interval_seconds": 86401}])
def test_policy_bounds_cannot_be_expanded(changes):
    with pytest.raises(ValueError):
        SourcePolicy(**changes).validate_bounds()


def _inquiry_conn(monkeypatch, stored):
    from unittest.mock import MagicMock
    saved = {}
    monkeypatch.setattr(admin_service, "record", lambda conn, tenant, kind, identity, lock=False: dict(stored) if stored else {})
    monkeypatch.setattr(admin_service, "put", lambda conn, tenant, kind, identity, value, **kw: saved.update(value=value, **kw))
    return MagicMock(), saved


def test_operator_reply_is_stored_on_the_inquiry(monkeypatch):
    stored = {"userId": "u1", "title": "t", "body": "b", "status": "기록 완료", "assignee": "", "replies": [], "history": []}
    conn, saved = _inquiry_conn(monkeypatch, stored)
    admin_service.mutate(conn, "test_operations", "qa", {"type": "reply", "inquiryId": "i1", "body": "확인했습니다."})
    value = saved["value"]
    assert value["status"] == "답변 완료" and value["assignee"] == "qa"
    assert value["replies"][0]["body"] == "확인했습니다." and value["replies"][0]["operator"] == "qa"
    assert saved["action"] == "reply" and value["history"]


def test_operator_can_change_inquiry_status_and_assignee(monkeypatch):
    stored = {"userId": "u1", "title": "t", "body": "b", "status": "접수", "assignee": "", "replies": [], "history": []}
    conn, saved = _inquiry_conn(monkeypatch, stored)
    admin_service.mutate(conn, "test_operations", "qa", {"type": "inquiry-status", "inquiryId": "i1", "status": "처리 중", "assignee": "qa", "reason": "확인 시작"})
    assert saved["value"]["status"] == "처리 중" and saved["value"]["assignee"] == "qa"
    assert "확인 시작" in saved["value"]["history"][0]["text"]


@pytest.mark.parametrize("kind", ["reply", "inquiry-status"])
def test_unknown_inquiry_is_not_created_by_reply(monkeypatch, kind):
    conn, saved = _inquiry_conn(monkeypatch, None)
    command = {"type": kind, "inquiryId": "missing", "body": "x", "status": "접수", "assignee": "", "reason": "x"}
    with pytest.raises(admin_service.AdminServiceError) as raised:
        admin_service.mutate(conn, "test_operations", "qa", command)
    assert raised.value.status_code == 404
    assert not saved


def test_customer_sees_operator_reply_without_operator_identity():
    from app.domains.travel_ops.modules.web_account.admin_customer_api import _public
    answered = _public({"id": "i1", "title": "t", "body": "b", "language": "ko", "receivedAt": "x", "replies": [{"body": "안내", "operator": "qa", "at": "y"}]})
    assert answered["status"] == "답변 완료" and answered["replies"] == [{"body": "안내", "operator": "guguroute 운영팀", "at": "y"}]
    assert _public({"id": "i1", "title": "t", "body": "b", "language": "ko", "receivedAt": "x", "replies": []})["status"] == "기록 완료"


def test_periodic_replay_recovers_same_event_after_commit_before_queue_ack(tmp_path, monkeypatch):
    """DB 커밋 뒤 대기 행 삭제가 실패해도 다음 회차에서 발생 UUID를 보존한다."""
    from app.application import operations_diagnostics as diagnostics
    from scripts import replay_operations_diagnostics as worker

    value = event()
    spool = Spool(tmp_path / "pending.sqlite3")
    spool.enqueue(value)
    committed = set()
    seen = []

    class Connection:
        def transaction(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def persist(conn, current):
        seen.append(current.event_id)
        added = current.event_id not in committed
        committed.add(current.event_id)
        return added

    monkeypatch.setattr(diagnostics, "persist", persist)
    real_connect = spool.connect
    calls = 0

    @contextmanager
    def acknowledgement_failed():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("private disk failure")
        with real_connect() as conn:
            yield conn

    monkeypatch.setattr(spool, "connect", acknowledgement_failed)
    first = worker.run_once(connection_factory=Connection, spool=spool)
    assert first["failed"] == 1 and first["pending"] == 1
    second = worker.run_once(connection_factory=Connection, spool=Spool(spool.path))
    assert second["processed"] == 1 and second["pending"] == 0
    assert seen == [value.event_id, value.event_id] and committed == {value.event_id}


def test_replay_and_prune_failures_have_separate_safe_status(tmp_path, monkeypatch):
    from scripts import replay_operations_diagnostics as worker

    spool = Spool(tmp_path / "pending.sqlite3")
    spool.enqueue(event())
    result = worker.run_once(connection_factory=unavailable, spool=spool, prune_expired=True)
    assert result["failed"] == 1 and result["prune_failed"] == 1 and result["pending"] == 1
    monkeypatch.setattr(worker, "run_once", lambda **kw: result)
    monkeypatch.setattr("sys.argv", ["replay_operations_diagnostics", "--prune"])
    assert worker.main() == 1


def test_spool_disk_failure_does_not_expose_exception_in_cli(monkeypatch, capsys):
    from scripts import replay_operations_diagnostics as worker

    class BrokenSpool:
        def replay(self, *args, **kwargs):
            raise OSError("sensitive-disk-path")

    monkeypatch.setattr(worker, "Spool", BrokenSpool)
    monkeypatch.setattr("sys.argv", ["replay_operations_diagnostics"])
    assert worker.main() == 1
    output = capsys.readouterr()
    assert "DIAGNOSTIC_REPLAY_FAILED" in output.out
    assert "sensitive-disk-path" not in output.out + output.err


@pytest.mark.parametrize("limit", [0, -1, 1001, True, "100"])
def test_replay_rejects_invalid_limits_before_opening_spool(limit):
    from scripts import replay_operations_diagnostics as worker

    class NeverOpen:
        def replay(self, *args, **kwargs):
            pytest.fail("invalid limit opened spool")

    with pytest.raises(ValueError, match="limit_out_of_range"):
        worker.run_once(spool=NeverOpen(), limit=limit)


def test_replay_uses_configured_batch_limit_and_reports_lost_records(monkeypatch, capsys):
    from scripts import replay_operations_diagnostics as worker

    seen = []

    class SpoolDouble:
        def replay(self, factory, *, limit):
            seen.append(limit)
            return {"failed": 0, "lost": 1, "pending": 0}

    monkeypatch.setattr(worker, "configuration", lambda: {"diagnostics": {"replay_limit": 7}})
    monkeypatch.setattr(worker, "Spool", SpoolDouble)
    monkeypatch.setattr("sys.argv", ["replay_operations_diagnostics"])
    assert worker.main() == 1
    assert seen == [7]


@pytest.mark.parametrize("code", ["classification_failed", "source_failed", "error", "retry",
                                "team_timeout", "team_exception", "state_conflict"])
def test_execution_callback_spools_owned_identifiers_without_original_text(tmp_path, code, caplog):
    import json
    from app.application.operations_diagnostics import execution_recorder

    spool = Spool(tmp_path / "pending.sqlite3")
    collect = execution_recorder(connection_factory=unavailable, policy_version="execution-v1", spool=spool)
    customer, trip, case = uuid4(), uuid4(), uuid4()
    result = collect({"tenant_id": "test_operations", "code": code, "customer_id": str(customer),
                      "trip_id": str(trip), "case_id": str(case),
                      "error_code": "sensitive original error", "body": "private customer message"})
    assert result["status"] == "spooled"
    with spool.connect() as conn:
        saved = json.loads(conn.execute("SELECT payload FROM pending").fetchone()[0])
    assert saved["customer_id"] == str(customer) and saved["trip_id"] == str(trip)
    assert saved["case_id"] == str(case) and saved["conditions"] == []
    assert saved["event_id"] == result["event_id"]
    assert "private customer message" not in str(saved) + caplog.text
    assert "sensitive original error" not in str(saved) + caplog.text


def test_execution_callback_records_only_known_reason_and_does_not_count_recovery(tmp_path):
    from app.application.operations_diagnostics import execution_recorder

    spool = Spool(tmp_path / "pending.sqlite3")
    collect = execution_recorder(connection_factory=unavailable, policy_version="execution-v1", spool=spool)
    assert collect({"tenant_id": "test_operations", "code": "retry_recovered"}) == {"status": "ignored"}
    assert spool.snapshot()["pending"] == 0
    assert collect({"tenant_id": "test_operations", "code": "source_failed", "customer_id": "not-a-uuid"}) == {"status": "rejected"}
    assert spool.snapshot()["pending"] == 0
    result = collect({"tenant_id": "test_operations", "code": "retry", "error_code": "dependency_deferred"})
    assert result["status"] == "spooled"
    with spool.connect() as conn:
        value = Event.model_validate_json(conn.execute("SELECT payload FROM pending").fetchone()[0])
    assert value.conditions == ["DEPENDENCY_DEFERRED"]


def test_execution_callback_collection_degraded_is_visible(tmp_path, caplog):
    from app.application.operations_diagnostics import execution_recorder

    collect = execution_recorder(connection_factory=unavailable, policy_version="execution-v1",
                                 spool=Spool(tmp_path / "pending.sqlite3", max_events=0))
    assert collect({"tenant_id": "test_operations", "code": "error"})["status"] == "collection_degraded"
    assert "status=collection_degraded" in caplog.text
