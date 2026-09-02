"""멈춘 분류를 되잡는 절차를 DB 없이 검증한다."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application import classification, classification_sweeper
from app.application.classification_sweeper import sweep_stuck_classifying
from app.core.contracts import StateConflict
from app.domain.events import EventType


class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.conn.sql = sql
        self.conn.params = params
        tenant_id, stuck_after_seconds, limit = params
        cutoff = self.conn.now - timedelta(seconds=stuck_after_seconds)
        candidates = [
            row for row in self.conn.cases
            if row["tenant_id"] == tenant_id
            and row["status"] == "classifying"
            and row["updated_at"] < cutoff
        ]
        candidates.sort(key=lambda row: row["updated_at"])
        self.rows = [
            (row["case_id"], row["subject"], row["version"])
            for row in candidates[:limit]
        ]

    def fetchall(self):
        return list(self.rows)


class FakeConn:
    def __init__(self, cases):
        self.cases = cases
        self.now = datetime(2026, 9, 3, tzinfo=UTC)
        self.transactions = 0
        self.sql = ""
        self.params = ()

    def cursor(self):
        return FakeCursor(self)

    def transaction(self):
        conn = self

        class _Ctx:
            def __enter__(self):
                conn.transactions += 1
                return conn

            def __exit__(self, *exc):
                return False

        return _Ctx()


def _case(*, age_seconds, version=1, status="classifying", tenant_id="demo"):
    return {
        "case_id": uuid4(),
        "tenant_id": tenant_id,
        "subject": f"문의-{age_seconds}",
        "version": version,
        "status": status,
        "updated_at": datetime(2026, 9, 3, tzinfo=UTC) - timedelta(seconds=age_seconds),
    }


def _classifier(text):
    return {"intent": "general", "issue_code": "general", "sentiment": "neutral"}


def test_only_old_classifying_cases_are_selected(monkeypatch):
    old = _case(age_seconds=301)
    recent = _case(age_seconds=299)
    other_status = _case(age_seconds=500, status="routing")
    other_tenant = _case(age_seconds=500, tenant_id="other")
    conn = FakeConn([recent, other_status, old, other_tenant])
    transitioned = []
    monkeypatch.setattr(classification, "transition_case",
                        lambda conn, **kwargs: transitioned.append(kwargs))

    result = sweep_stuck_classifying(
        conn, tenant_id="demo", classifier=_classifier, actor_id="sweeper",
        stuck_after_seconds=300, limit=10,
    )

    assert result == {"scanned": 1, "classified": 1, "failed": 0, "conflicted": 0,
                      "errored": 0}
    assert [call["case_id"] for call in transitioned] == [old["case_id"]]
    assert "updated_at < now() - make_interval(secs => %s)" in conn.sql


def test_limit_and_oldest_first_are_honored(monkeypatch):
    cases = [_case(age_seconds=400), _case(age_seconds=600), _case(age_seconds=500)]
    conn = FakeConn(cases)
    transitioned = []
    monkeypatch.setattr(classification, "transition_case",
                        lambda conn, **kwargs: transitioned.append(kwargs))

    result = sweep_stuck_classifying(
        conn, tenant_id="demo", classifier=_classifier, actor_id="sweeper",
        stuck_after_seconds=300, limit=2,
    )

    assert result["scanned"] == 2
    assert [call["case_id"] for call in transitioned] == [cases[1]["case_id"], cases[2]["case_id"]]
    assert "ORDER BY updated_at ASC" in conn.sql
    assert conn.params[-1] == 2


def test_a_recording_error_does_not_stop_following_cases(monkeypatch):
    """★기록 자체가 실패한 건은 `errored` 다.

    `failed`(=CLASSIFICATION_FAILED 를 적는 데 성공)와 다르다 —
    이쪽은 아무것도 못 적어서 Case 가 여전히 `classifying` 에 남는다.
    """
    cases = [_case(age_seconds=600), _case(age_seconds=500), _case(age_seconds=400)]
    conn = FakeConn(cases)
    attempted = []

    def transition(conn, **kwargs):
        attempted.append(kwargs["case_id"])
        if kwargs["case_id"] == cases[1]["case_id"]:
            raise RuntimeError("기록 실패")

    monkeypatch.setattr(classification, "transition_case", transition)

    result = sweep_stuck_classifying(
        conn, tenant_id="demo", classifier=_classifier, actor_id="sweeper",
        stuck_after_seconds=300, limit=10,
    )

    assert attempted == [case["case_id"] for case in cases]
    assert result == {"scanned": 3, "classified": 2, "failed": 0, "conflicted": 0,
                      "errored": 1}


def test_transition_conflict_is_counted_and_not_raised(monkeypatch):
    cases = [_case(age_seconds=500), _case(age_seconds=400)]
    conn = FakeConn(cases)

    def transition(conn, **kwargs):
        if kwargs["case_id"] == cases[0]["case_id"]:
            raise StateConflict("다른 실행이 먼저 전이함")

    monkeypatch.setattr(classification, "transition_case", transition)

    result = sweep_stuck_classifying(
        conn, tenant_id="demo", classifier=_classifier, actor_id="sweeper",
        stuck_after_seconds=300, limit=10,
    )

    assert result == {"scanned": 2, "classified": 1, "failed": 0, "conflicted": 1,
                      "errored": 0}


def test_actual_row_version_is_passed_as_expected_version(monkeypatch):
    case = _case(age_seconds=500, version=7)
    conn = FakeConn([case])
    transitioned = []
    monkeypatch.setattr(classification, "transition_case",
                        lambda conn, **kwargs: transitioned.append(kwargs))

    result = sweep_stuck_classifying(
        conn, tenant_id="demo", classifier=_classifier, actor_id="sweeper",
        stuck_after_seconds=300, limit=10,
    )

    assert result["classified"] == 1
    assert transitioned[0]["expected_version"] == case["version"]


def test_a_classifier_failure_is_recorded_and_counted_apart_from_errors(monkeypatch):
    """★두 실패를 구분한다 (2026-09-03 검수에서 나눴다).

        failed   분류는 안 됐지만 CLASSIFICATION_FAILED 를 **적는 데 성공**했다.
                 Case 는 escalated 로 나아가고 다음 회차에 다시 안 걸린다.
        errored  아무것도 못 적었다. Case 는 `classifying` 에 그대로 남아
                 **다음 회차에 또 걸린다.**

    합쳐 세면 "실패했지만 처리는 됐다" 와 "아무 일도 못 했다" 를 구분할 수 없다.
    운영자가 할 일이 다르다.
    """
    conn = FakeConn([_case(age_seconds=600)])
    recorded = []
    monkeypatch.setattr(classification, "transition_case",
                        lambda conn, **kwargs: recorded.append(kwargs))

    def broken_classifier(_text):
        raise TimeoutError("provider timeout")

    result = sweep_stuck_classifying(
        conn, tenant_id="demo", classifier=broken_classifier, actor_id="sweeper",
        stuck_after_seconds=300, limit=10,
    )

    # 분류는 실패했지만 기록은 됐다 → failed
    assert result == {"scanned": 1, "classified": 0, "failed": 1, "conflicted": 0,
                      "errored": 0}
    assert recorded[0]["event_type"] is EventType.CLASSIFICATION_FAILED
