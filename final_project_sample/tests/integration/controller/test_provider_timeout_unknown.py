"""provider timeout 이 `unknown` 으로 남고 자동 재실행되지 않는지 증명한다.

CLAUDE.md §0.2:
    provider timeout 을 **성공으로 추정하지 않는다.**
    `unknown` 으로 남기고 자동 재실행하지 않는다.

★DoD-11 은 이 항목을 "코드 경로는 있으나 실제로 timeout 을 주입해 확인하지 않았다"
  로 미검증 처리했다. `git grep` 으로 status='unknown' 을 찾은 것은 증거가 아니다 —
  이 프로젝트에서 "코드가 있다" 와 "그 경로가 밟힌다" 의 차이로 6번 당했다
  (분류기 미연결 · RAG 검색 전건 실패 · Team LLM 미호출 등).

★여기서 재는 것은 **outbox(Message Broker) 발행 경로**다.
  action_requests 실행 경로는 이 시스템에 존재하지 않는다 —
  Team 은 제안까지만 하고 실제 provider 호출은 미구현이다.
  그 사실은 docs/evidence/DoD-11_action_idempotency_승인.md 에 적어 두었다.
"""
from __future__ import annotations

import asyncio

import pytest

from acop_basement.infrastructure.db.session import get_connection
from acop_basement.infrastructure.messaging.outbox import OutboxBrokerAdapter
from acop_basement.infrastructure.messaging.worker import OutboxWorker

from .test_controller_integration import db, seed_case  # noqa: F401


def _publish(tenant: str, case_id, key: str) -> None:
    adapter = OutboxBrokerAdapter(lambda: get_connection())
    asyncio.run(adapter.publish("test.timeout", {"tenant_id": tenant, "case_id": str(case_id)}, key))


def _status(conn, tenant: str, key: str) -> tuple[str, int, str | None]:
    with conn.cursor() as cur:
        cur.execute("SELECT status, attempts, last_error FROM outbox WHERE tenant_id=%s AND dedupe_key=%s", (tenant, key))
        return cur.fetchone()


def test_provider_timeout_stays_unknown_and_is_not_retried(db):  # noqa: F811
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "timeout-" + tenant
    _publish(tenant, case_id, key)

    calls: list[dict] = []

    def timing_out(message):
        calls.append(message)
        raise TimeoutError("provider did not answer in time")

    worker = OutboxWorker(get_connection, timing_out, tenant_id=tenant)
    assert worker.process_once() is True
    assert len(calls) == 1

    status, attempts, last_error = _status(conn, tenant, key)
    # ★성공으로 추정하지 않는다
    assert status != "delivered"
    # ★실패로 단정하지도 않는다 — 돈이 이미 나갔을 수 있다
    assert status not in ("dead_letter", "pending")
    assert status == "unknown"
    assert attempts == 1
    assert "did not answer" in last_error

    # ★자동 재실행되지 않는다: 다시 돌려도 publisher 를 부르지 않는다
    assert worker.process_once() is False
    assert len(calls) == 1
    assert _status(conn, tenant, key)[0:2] == ("unknown", 1)


def test_crashed_worker_leaves_processing_row_reclaimed_to_unknown(db):  # noqa: F811
    """★버그사냥 2026-08-17 — 워커가 'processing' 으로 claim 을 커밋한 뒤,
    `publisher()` 를 부르기 전이나 부르는 도중에 죽으면 그 행은 영영 'processing'
    에 멈췄다. 재시작한 워커는 `status='pending'` 만 보므로 다시 집지 않는다.

    provider timeout 과 똑같은 근거로 처리한다: **배달됐는지 모른다** →
    자동 재실행하지 않고 `unknown` 으로 남겨 사람이 `/ops/outbox` 에서 결론짓는다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "crashed-" + tenant
    _publish(tenant, case_id, key)

    # ★죽은 워커를 흉내낸다 — claim 은 커밋됐는데 publisher() 는 끝내 못 불렀다.
    #   locked_at 을 임계값보다 훨씬 과거로 심어 "오래 전에 멈췄다" 를 만든다.
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE outbox SET status='processing', locked_at=now() - interval '1 hour' "
            "WHERE tenant_id=%s AND dedupe_key=%s", (tenant, key))
    conn.commit()

    calls: list[dict] = []
    worker = OutboxWorker(get_connection, calls.append, tenant_id=tenant)
    # 회수된 행은 'pending' 이 아니라 'unknown' 이 되므로, 이번 호출이 새로
    # 집을 'pending' 행은 없다 — publisher 는 불리지 않는다.
    assert worker.process_once() is False
    assert calls == []

    status, attempts, last_error = _status(conn, tenant, key)
    assert status == "unknown"
    assert "crashed" in last_error

    # ★여기서도 자동 재실행되지 않는다.
    assert worker.process_once() is False
    assert calls == []


def test_fresh_processing_row_is_not_reclaimed(db):  # noqa: F811
    """★임계값(300s) 안의 'processing' 은 정상 처리 중일 수 있다 — 건드리면 안 된다."""
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "fresh-" + tenant
    _publish(tenant, case_id, key)

    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE outbox SET status='processing', locked_at=now() - interval '5 seconds' "
            "WHERE tenant_id=%s AND dedupe_key=%s", (tenant, key))
    conn.commit()

    worker = OutboxWorker(get_connection, lambda message: None, tenant_id=tenant)
    worker.process_once()

    status, _, _ = _status(conn, tenant, key)
    assert status == "processing", "임계값 안의 processing 행을 건드리면 안 된다"


def test_ordinary_failure_is_distinguished_from_unknown(db):  # noqa: F811
    """timeout 이 아닌 실패는 재시도 대상이다. 둘을 같게 처리하면 안 된다."""
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "boom-" + tenant
    _publish(tenant, case_id, key)

    def boom(message):
        raise ValueError("bad payload")

    worker = OutboxWorker(get_connection, boom, tenant_id=tenant)
    assert worker.process_once() is True
    status, attempts, _ = _status(conn, tenant, key)
    # ★거절당한 것은 안 나갔다는 뜻이므로 재시도해도 된다
    assert status == "pending"
    assert attempts == 1


def test_unknown_row_is_never_reclaimed_even_by_a_healthy_worker(db):  # noqa: F811
    """★unknown 을 남긴 뒤 정상 worker 를 붙여도 그 행은 배달되지 않는다.

    사람이 provider 를 조회해 결론을 내기 전에는 재실행하지 않는다는 뜻이다.
    """
    conn, tenant = db
    case_id, _ = seed_case(conn, tenant)
    key = "stuck-" + tenant
    _publish(tenant, case_id, key)

    def times_out(_message):
        raise TimeoutError("t")

    OutboxWorker(get_connection, times_out, tenant_id=tenant).process_once()
    assert _status(conn, tenant, key)[0] == "unknown"

    delivered: list[dict] = []
    healthy = OutboxWorker(get_connection, delivered.append, tenant_id=tenant)
    assert healthy.process_once() is False
    assert delivered == []
    assert _status(conn, tenant, key)[0] == "unknown"


def test_action_status_enum_can_hold_unknown(db):  # noqa: F811
    """action_requests 쪽 `unknown` 은 DB enum 에만 있고 쓰는 코드가 없다.

    ★이 테스트는 "구현됐다" 를 주장하지 않는다. enum 이 값을 받아준다는 것만 확인하고,
      실제 provider 호출 경로가 없다는 사실을 고정해 둔다.
    """
    conn, tenant = db
    with conn.cursor() as cur:
        cur.execute("SELECT unnest(enum_range(NULL::action_status))::text")
        values = {row[0] for row in cur.fetchall()}
    assert "unknown" in values
    assert {"succeeded", "failed", "executing"} <= values
