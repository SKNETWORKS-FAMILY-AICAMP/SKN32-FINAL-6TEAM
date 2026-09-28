from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.rag.retriever import search_policy


#: ★`[2026-09-22]` 이 파일은 **쇼핑몰 코퍼스**를 본다. 같은 tenant 에 여행 코퍼스가 함께
#:  들어오면서(12문서·130청크) tenant 만으로 세던 수가 틀렸다 — 그래서 scope 로 좁힌다.
#:  여행 쪽은 `test_travel_corpus_retrieval.py` 가 따로 본다. 25·306 이라는 수는
#:  2026-08-17 에 이 코퍼스가 받은 판정이므로 **그대로 둔다.**
COMMERCE_SCOPES = ["order", "shipping", "return", "exchange", "refund", "support", "incident"]


def _commerce_counts(cur) -> tuple[int, int]:
    cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s AND scope = ANY(%s)",
                ("demo", COMMERCE_SCOPES))
    documents = cur.fetchone()[0]
    cur.execute(
        """SELECT count(*) FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
           WHERE kd.tenant_id=%s AND kd.scope = ANY(%s)""", ("demo", COMMERCE_SCOPES))
    return documents, cur.fetchone()[0]


@pytest.fixture(scope="module", autouse=True)
def populated_demo():
    with get_connection() as conn, conn.cursor() as cur:
        documents, chunks = _commerce_counts(cur)
    assert (documents, chunks) == (25, 306), (
        "demo corpus must be loaded before integration tests: "
        f"expected documents=25 chunks=306, got documents={documents} chunks={chunks}"
    )


def test_corpus_counts_and_embedding_dimension():
    with get_connection() as conn, conn.cursor() as cur:
        assert _commerce_counts(cur) == (25, 306)
        cur.execute(
            """SELECT min(vector_dims(kc.embedding)), max(vector_dims(kc.embedding))
               FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
               WHERE kd.scope = ANY(%s) AND kc.embedding IS NOT NULL""", (COMMERCE_SCOPES,))
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


def test_both_embedding_columns_are_filled_for_the_commerce_corpus():
    """★쇼핑몰 코퍼스는 두 벡터가 **공존**한다(1536 칸을 지우지 않았다).

    ★`[2026-09-22]` 전에는 `knowledge_chunks` **전체**를 셌다. 여행 코퍼스가 들어오면서
      그 수가 틀렸다 — 여행 130청크는 **1024칸만** 채워져 있다(OpenAI 크레딧이 없어
      로컬 임베딩으로만 적재했다). 그 사실은 숨기지 않고 아래에서 그대로 확인한다.
    """
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*), count(kc.embedding), count(kc.embedding_1024)
               FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
               WHERE kd.scope = ANY(%s)""", (COMMERCE_SCOPES,))
        total, openai_dim, local_dim = cur.fetchone()
    assert total == openai_dim == local_dim, (total, openai_dim, local_dim)


def test_the_travel_corpus_is_local_only_and_that_is_visible():
    """★여행 코퍼스에는 1536 벡터가 **없다.** 제공자를 openai 로 되돌리면 검색이 **예외**로 죽는다 —
    조용히 0건이 되지 않는다(`retriever.search_policy`)."""
    import pytest as _pytest

    from app.core import settings as settings_module
    from app.infrastructure.db.session import get_connection
    from app.infrastructure.rag import retriever

    travel_scopes = ["travel_activity", "travel_weather", "travel_dining",
                     "travel_mobility", "travel_cancellation", "travel_access"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*), count(kc.embedding), count(kc.embedding_1024)
               FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
               WHERE kd.scope = ANY(%s)""", (travel_scopes,))
        total, openai_dim, local_dim = cur.fetchone()
    assert (total, openai_dim, local_dim) == (130, 0, 130), (total, openai_dim, local_dim)

    original = settings_module.get_settings()
    patched = original.model_copy(update={"embedding_provider": "openai"})
    with _pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(retriever, "get_settings", lambda: patched)
        retriever._embed_query.cache_clear()
        with _pytest.raises(RuntimeError, match="embedding_1024|벡터 칸"):
            retriever.search_policy("demo", "비가 와서 못 간다", travel_scopes)
    retriever._embed_query.cache_clear()
