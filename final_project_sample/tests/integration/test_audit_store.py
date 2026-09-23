"""중앙 감사 저장소 — 실제 PostgreSQL 과 기존 JSONL 동작을 함께 검사한다.

★DB 조회는 항상 deployment_id 로 격리되어야 한다. idempotency key 는 조회
  근거일 뿐 고유 제약이 아니므로 같은 키의 이벤트도 모두 보존한다.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from acop_basement.core.audit_store import FileAuditStore, PostgresAuditStore
from acop_basement.infrastructure.db.session import get_connection


def _event(*, key: str | None = None, revision: str = "rev-2") -> dict:
    event = {
        "event": "composer.change",
        "actor": "final_project_ui",
        "subject": "module:vector_rag",
        "timestamp": "2026-08-29T00:00:00Z",
        "previous_revision": "rev-1",
        "revision": revision,
        "changed_fields": ["modules.vector_rag.enabled"],
        "reason": "integration test",
        "correlation_id": "test-correlation",
        "operation": "disable",
        "resource_type": "module",
        "instance_id": "vector_rag",
        "idempotency_key": key,
        "result": {"config_revision": revision},
    }
    return event


@pytest.fixture()
def stores():
    first_id = "test-audit-" + uuid4().hex
    second_id = "test-audit-" + uuid4().hex
    created = (
        PostgresAuditStore(get_connection, first_id),
        PostgresAuditStore(get_connection, second_id),
    )
    try:
        yield created
    finally:
        # 테스트 격리용 정리다. 제품 저장소에는 삭제 통로가 없다.
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM composer_audit_events WHERE deployment_id IN (%s, %s)",
                    (first_id, second_id))


def test_append_can_be_read_with_recent(stores):
    first, _ = stores
    event = _event()

    first.append(event)

    assert first.recent() == [event]


def test_deployments_cannot_see_each_others_events(stores):
    first, second = stores
    first_event = _event(revision="first")
    second_event = _event(revision="second")

    first.append(first_event)
    second.append(second_event)

    assert first.recent() == [first_event]
    assert second.recent() == [second_event]


def test_find_by_idempotency_key_returns_event_or_none(stores):
    first, _ = stores
    event = _event(key="idem-found")
    first.append(event)

    assert first.find_by_idempotency_key("idem-found") == event
    assert first.find_by_idempotency_key("idem-missing") is None


def test_duplicate_idempotency_keys_are_both_appended(stores):
    first, _ = stores
    first.append(_event(key="idem-duplicate", revision="first"))
    first.append(_event(key="idem-duplicate", revision="second"))

    assert [event["revision"] for event in first.recent()] == ["second", "first"]


def test_file_store_preserves_the_existing_jsonl_format(tmp_path):
    path = tmp_path / "composer_events.jsonl"
    store = FileAuditStore(path)
    event = _event(key="file-key")

    store.append(event)

    expected = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    assert path.read_text(encoding="utf-8") == expected
    assert store.recent() == [event]
    assert store.find_by_idempotency_key("file-key") == event


def test_corrupt_file_line_does_not_block_lookups(tmp_path):
    path = tmp_path / "composer_events.jsonl"
    first = _event(key="before-corruption", revision="first")
    second = _event(key="after-corruption", revision="second")
    path.write_text(
        json.dumps(first, ensure_ascii=False) + "\n{not-json\n" +
        json.dumps(second, ensure_ascii=False) + "\n",
        encoding="utf-8")
    store = FileAuditStore(path)

    assert store.recent() == [second, first]
    assert store.find_by_idempotency_key("after-corruption") == second
