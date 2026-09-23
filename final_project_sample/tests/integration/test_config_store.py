"""중앙 설정 저장소 — `program/plan/A-COP_Composer_중앙설정저장소_결정.md`.

★실제 PostgreSQL 로 검사한다. 조건부 쓰기(CAS)는 DB 가 하는 일이라 가짜
  커넥션으로 검사하면 "우리 코드가 우리 가짜와 맞다" 만 증명된다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from acop_basement.core.config_store import (
    ConfigStoreError,
    FileConfigStore,
    PostgresConfigStore,
    RevisionMismatch,
)
from acop_basement.infrastructure.db.session import get_connection

DECLARATION = {
    "modules": {"vector_rag": {"enabled": True}},
    "ports": {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"},
    "teams": [{"team_id": "t1", "active": False, "implementation_ref": "app.x:T"}],
}


@pytest.fixture()
def store():
    deployment_id = "test-" + uuid4().hex
    created = PostgresConfigStore(get_connection, deployment_id)
    created.create(DECLARATION, revision="rev-1")
    try:
        yield created
    finally:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM project_configs WHERE deployment_id = %s",
                            (deployment_id,))


# ── 읽기 ─────────────────────────────────────────────────────────────
def test_read_returns_the_stored_declaration(store):
    assert store.read() == DECLARATION


def test_unregistered_deployment_fails_loudly_instead_of_returning_empty():
    """★등록 안 된 대상이 기본값으로 도는 것이 가장 위험하다."""
    unknown = PostgresConfigStore(get_connection, "test-missing-" + uuid4().hex)
    with pytest.raises(ConfigStoreError, match="선언이 없다"):
        unknown.read()


def test_deployment_id_is_required():
    with pytest.raises(ConfigStoreError, match="deployment_id"):
        PostgresConfigStore(get_connection, "")


# ── 조건부 쓰기 ──────────────────────────────────────────────────────
def test_write_replaces_the_declaration_when_the_revision_matches(store):
    changed = {**DECLARATION, "teams": [{"team_id": "t2", "active": True,
                                         "implementation_ref": "app.y:U"}]}
    store.write(changed, base_revision="rev-1", new_revision="rev-2")
    assert store.read() == changed


def test_stale_base_revision_is_rejected_and_nothing_changes(store):
    """★"마지막에 쓴 사람이 이긴다" 를 막는다."""
    changed = {**DECLARATION, "modules": {"vector_rag": {"enabled": False}}}
    with pytest.raises(RevisionMismatch) as caught:
        store.write(changed, base_revision="stale", new_revision="rev-9")

    assert caught.value.current_revision == "rev-1"
    assert store.read() == DECLARATION, "거부됐는데 내용이 바뀌면 안 된다"


def test_two_writers_with_the_same_base_revision_only_one_wins(store):
    """★프로세스 로컬 락으로는 못 막는 경우 — 조건을 DB 가 판정한다."""
    first = {**DECLARATION, "teams": [{"team_id": "a", "active": True,
                                       "implementation_ref": "app.a:A"}]}
    second = {**DECLARATION, "teams": [{"team_id": "b", "active": True,
                                        "implementation_ref": "app.b:B"}]}

    store.write(first, base_revision="rev-1", new_revision="rev-2")
    with pytest.raises(RevisionMismatch):
        store.write(second, base_revision="rev-1", new_revision="rev-3")

    assert store.read() == first


def test_create_refuses_to_overwrite_an_existing_deployment(store):
    with pytest.raises(ConfigStoreError, match="이미 등록된"):
        store.create(DECLARATION, revision="rev-x")


# ── 파일 저장소 (기존 동작 보존) ──────────────────────────────────────
def test_file_store_round_trips(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("modules: {}\n", encoding="utf-8")
    file_store = FileConfigStore(path)

    file_store.write(DECLARATION, base_revision="rev-1", new_revision="rev-2")

    assert file_store.read() == DECLARATION


def test_file_store_reports_a_missing_file_instead_of_returning_empty(tmp_path):
    with pytest.raises(ConfigStoreError, match="읽지 못했다"):
        FileConfigStore(tmp_path / "nope.yaml").read()


def test_file_store_leaves_no_temporary_file_behind(tmp_path):
    """임시 파일은 안 남는다. ★`.bak` 은 임시 파일이 아니라 계약이다
    (`docs/handoff/13` — 직전 상태 복구용)."""
    path = tmp_path / "project.yaml"
    path.write_text("modules: {}\n", encoding="utf-8")
    FileConfigStore(path).write(DECLARATION, base_revision="a", new_revision="b")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["project.yaml", "project.yaml.bak"]
    assert not list(tmp_path.glob(".project.*")), "staged 임시 파일이 남았다"


def test_file_store_keeps_the_previous_content_in_the_backup(tmp_path):
    path = tmp_path / "project.yaml"
    path.write_text("modules: {}\n", encoding="utf-8")
    FileConfigStore(path).write(DECLARATION, base_revision="a", new_revision="b")

    assert path.with_suffix(".yaml.bak").read_text(encoding="utf-8") == "modules: {}\n"
