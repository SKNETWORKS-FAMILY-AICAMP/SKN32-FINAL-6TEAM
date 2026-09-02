"""접수 뒤 실행이 시작조차 못 한 Case 를 되잡는 절차를 DB 없이 검증한다.

★`test_classification_sweeper.py` 와 짝이다. 경계를 나눌 때마다 같은 틈이 생기고
  같은 모양의 손이 필요하다:

      분류를 생성 트랜잭션 밖으로  →  `classifying` 잔류
      실행을 접수 응답 뒤로        →  `routing` 잔류  ← 이 파일
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.routing_sweeper import sweep_stuck_routing


class FakeCursor:
    def __init__(self, conn: "FakeConn") -> None:
        self.conn = conn
        self.rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.conn.sql = sql
        tenant_id, stuck_after_seconds, limit = params
        cutoff = self.conn.now - timedelta(seconds=stuck_after_seconds)
        candidates = [
            row for row in self.conn.cases
            if row["tenant_id"] == tenant_id
            and row["status"] == "routing"
            and row["updated_at"] < cutoff
            and not row.get("has_run")
        ]
        candidates.sort(key=lambda row: row["updated_at"])
        self.rows = [(row["case_id"],) for row in candidates[:limit]]

    def fetchall(self):
        return list(self.rows)


class FakeConn:
    def __init__(self, cases):
        self.cases = cases
        self.now = datetime(2026, 9, 3, tzinfo=UTC)
        self.sql = ""

    def cursor(self):
        return FakeCursor(self)

    def transaction(self):
        class _Ctx:
            def __enter__(self):
                return None

            def __exit__(self, *exc):
                return False

        return _Ctx()


def _case(*, age_seconds: int, status: str = "routing", has_run: bool = False):
    return {"case_id": uuid4(), "tenant_id": "demo", "status": status,
            "updated_at": datetime(2026, 9, 3, tzinfo=UTC) - timedelta(seconds=age_seconds),
            "has_run": has_run}


def _sweep(conn, run_case, **overrides):
    kwargs = {"tenant_id": "demo", "run_case": run_case, "actor_id": "sweeper",
              "stuck_after_seconds": 600, "limit": 10}
    kwargs.update(overrides)
    return sweep_stuck_routing(conn, **kwargs)


def test_only_old_routing_cases_without_a_run_are_selected():
    """★실행이 시작은 된 Case 는 건드리지 않는다 — 둘이 같이 돌면 안 된다."""
    old_stuck = _case(age_seconds=900)
    conn = FakeConn([
        old_stuck,
        _case(age_seconds=10),                      # 방금 접수됨
        _case(age_seconds=900, status="running"),   # 다른 상태
        _case(age_seconds=900, has_run=True),       # 실행은 시작됐다
    ])
    seen = []

    result = _sweep(conn, lambda **kw: seen.append(kw["case_id"]))

    assert [case_id for case_id in seen] == [old_stuck["case_id"]]
    assert result == {"scanned": 1, "started": 1, "errored": 0}


def test_limit_and_oldest_first_are_honored():
    cases = [_case(age_seconds=900), _case(age_seconds=1200), _case(age_seconds=700)]
    conn = FakeConn(cases)
    seen = []

    result = _sweep(conn, lambda **kw: seen.append(kw["case_id"]), limit=2)

    # 오래된 순: 1200 → 900
    assert seen == [cases[1]["case_id"], cases[0]["case_id"]]
    assert result["scanned"] == 2 and result["started"] == 2


def test_one_failure_does_not_stop_the_rest_and_is_counted():
    """★다시 걸었는데 또 터진 것은 사람이 봐야 한다 — started 와 합치지 않는다."""
    cases = [_case(age_seconds=900), _case(age_seconds=800), _case(age_seconds=700)]
    conn = FakeConn(cases)
    seen = []

    def run_case(**kw):
        seen.append(kw["case_id"])
        if kw["case_id"] == cases[1]["case_id"]:
            raise RuntimeError("에이전트 실패")

    result = _sweep(conn, run_case)

    assert seen == [case["case_id"] for case in cases]
    assert result == {"scanned": 3, "started": 2, "errored": 1}


def test_the_actor_is_passed_through():
    conn = FakeConn([_case(age_seconds=900)])
    seen = []

    _sweep(conn, lambda **kw: seen.append(kw), actor_id="sweeper-1")

    assert seen[0]["actor_id"] == "sweeper-1"
    assert seen[0]["tenant_id"] == "demo"


def test_nothing_stuck_is_not_an_error():
    conn = FakeConn([_case(age_seconds=10)])
    result = _sweep(conn, lambda **kw: None)

    assert result == {"scanned": 0, "started": 0, "errored": 0}
