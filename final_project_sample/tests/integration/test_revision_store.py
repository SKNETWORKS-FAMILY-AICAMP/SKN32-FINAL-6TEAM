"""선언 이력 저장소 — 실제 PostgreSQL 과 파일 JSONL 을 함께 검사한다 (D-011).

★같은 revision 이 여러 줄일 수 있다(되돌리면 같은 내용이 다시 나온다). 조회는
  최신 한 줄을 골라야 하고, 모든 읽기·쓰기는 deployment_id 로 격리돼야 한다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from acop_basement.core.revision_store import (
    FileRevisionStore, PostgresRevisionStore, RevisionStoreError,
)
from acop_basement.infrastructure.db.session import get_connection


def _entry(revision: str, *, previous: str | None = None, event: str = "change",
           flag: bool = True) -> dict:
    return {"revision": revision, "previous_revision": previous,
            "declaration": {"modules": {"vector_rag": {"enabled": flag}}},
            "actor": "test", "reason": "integration", "event": event,
            "timestamp": "2026-09-06T00:00:00Z"}


@pytest.fixture()
def stores():
    ids = ("test-rev-" + uuid4().hex, "test-rev-" + uuid4().hex)
    created = tuple(PostgresRevisionStore(get_connection, d) for d in ids)
    try:
        yield created
    finally:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                for deployment_id in ids:
                    cur.execute("DELETE FROM project_config_revisions WHERE deployment_id = %s",
                                (deployment_id,))


def test_recent_is_newest_first_and_isolated_per_deployment(stores):
    first, second = stores
    first.append(_entry("r1", event="baseline"))
    first.append(_entry("r2", previous="r1", flag=False))
    second.append(_entry("x1", event="baseline"))

    assert [e["revision"] for e in first.recent()] == ["r2", "r1"]
    assert [e["revision"] for e in second.recent()] == ["x1"]
    assert first.recent(1)[0]["declaration"] == {"modules": {"vector_rag": {"enabled": False}}}
    assert first.recent(0) == []


def test_find_returns_the_latest_line_for_a_repeated_revision(stores):
    """★되돌리면 같은 revision 이 다시 쌓인다 — 최신 줄을 골라야 한다."""
    first, _ = stores
    first.append(_entry("r1", event="baseline"))
    first.append(_entry("r2", previous="r1", flag=False))
    first.append(_entry("r1", previous="r2", event="restore"))

    found = first.find("r1")
    assert found is not None
    assert found["event"] == "restore" and found["previous_revision"] == "r2"
    assert first.find("nope") is None
    assert first.find("") is None


def test_shape_is_enforced(stores):
    first, _ = stores
    with pytest.raises(RevisionStoreError, match="revision"):
        first.append({"declaration": {}})
    with pytest.raises(RevisionStoreError, match="선언"):
        first.append({"revision": "r", "declaration": "not-a-dict"})


def test_file_store_behaves_the_same(tmp_path):
    store = FileRevisionStore(tmp_path / "revisions.jsonl")
    assert store.recent() == [] and store.find("r1") is None
    store.append(_entry("r1", event="baseline"))
    store.append(_entry("r2", previous="r1", flag=False))
    store.append(_entry("r1", previous="r2", event="restore"))

    assert [e["revision"] for e in store.recent()] == ["r1", "r2", "r1"]
    assert store.find("r1")["event"] == "restore"
    # 손상된 줄은 건너뛴다
    (tmp_path / "revisions.jsonl").open("a", encoding="utf-8").write("{broken\n")
    assert len(store.recent()) == 3
