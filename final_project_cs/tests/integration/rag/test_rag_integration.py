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


# ── 임베딩 제공자 (2026-09-22) ──────────────────────────────────
def test_the_provider_choice_is_explicit_and_never_falls_back(monkeypatch):
    """★고른 제공자가 이상하거나 준비가 안 됐으면 **예외**다 — 다른 칸으로 몰래 넘어가지 않는다."""
    import pytest

    from app.core import settings as settings_module
    from app.infrastructure.rag import retriever

    original = settings_module.get_settings()

    def use(**overrides):
        patched = original.model_copy(update=overrides)
        monkeypatch.setattr(settings_module, "get_settings", lambda: patched)
        monkeypatch.setattr(retriever, "get_settings", lambda: patched)
        retriever._embed_query.cache_clear()

    use(embedding_provider="openai")
    assert retriever._provider() == ("openai", "embedding", 1536)
    use(embedding_provider="ollama")
    assert retriever._provider() == ("ollama", "embedding_1024", 1024)

    use(embedding_provider="gemini")                      # 없는 제공자
    with pytest.raises(RuntimeError, match="ACOP_EMBEDDING_PROVIDER"):
        retriever._provider()

    use(embedding_provider="ollama", ollama_base_url="")   # 주소가 없다
    with pytest.raises(RuntimeError, match="ACOP_OLLAMA_BASE_URL"):
        retriever._embed_query("정책을 찾는다")
    retriever._embed_query.cache_clear()


def test_both_embedding_columns_are_filled_for_the_loaded_corpus():
    """★두 벡터가 **공존**한다(1536 칸을 지우지 않았다). 한쪽이 비면 그 제공자로는 검색이 안 된다."""
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*), count(embedding), count(embedding_1024) FROM knowledge_chunks")
        total, openai_dim, local_dim = cur.fetchone()
    assert total == openai_dim == local_dim, (total, openai_dim, local_dim)
