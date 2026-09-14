from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.rag.retriever import search_policy


@pytest.fixture(scope="module", autouse=True)
def populated_demo():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s", ("demo",))
        documents = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id) WHERE kd.tenant_id=%s", ("demo",))
        chunks = cur.fetchone()[0]
    assert (documents, chunks) == (25, 306), (
        "demo corpus must be loaded before integration tests: "
        f"expected documents=25 chunks=306, got documents={documents} chunks={chunks}"
    )


def test_corpus_counts_and_embedding_dimension():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s", ("demo",))
        assert cur.fetchone()[0] == 25
        cur.execute("SELECT count(*) FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id) WHERE kd.tenant_id=%s", ("demo",))
        assert cur.fetchone()[0] == 306
        cur.execute("SELECT min(vector_dims(embedding)), max(vector_dims(embedding)) FROM knowledge_chunks")
        assert cur.fetchone() == (1536, 1536)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("배송완료로 떴는데 못 받았어요", "doc_01"),
        ("주문은 3개인데 반품을 5개 신청했어요", "doc_14"),
    ],
)
def test_search_relevance(query: str, expected: str):
    results = search_policy("demo", query, ["shipping", "return", "exchange"])
    assert len(results) <= 8
    assert expected in {chunk.document_id for chunk in results}


def test_tenant_isolation_and_scope_filter():
    assert search_policy("tenant-that-does-not-exist", "환불", ["refund"]) == []
    results = search_policy("demo", "환불 지연 문의", ["refund"])
    assert all(chunk.scope == "refund" for chunk in results)
    assert all(chunk.document_id not in {"doc_01", "doc_14"} for chunk in results)
