from __future__ import annotations

import pytest

from app.infrastructure.db.session import get_connection

#: 여행 코퍼스 scope (`knowledge/travel/manifest.json` · `scripts/check_corpus.py` TRAVEL_SCOPE_PLAN)
TRAVEL_SCOPES = ["travel_activity", "travel_weather", "travel_dining",
                 "travel_mobility", "travel_cancellation", "travel_access"]

#: ★`[2026-10-06]` 이 파일은 **임베딩 제공자와 벡터 칸**만 본다.
#:  2026-09-22 판은 쇼핑몰 코퍼스(25문서·306청크)를 세고 쇼핑몰 질의로 검색 적합성을 봤는데,
#:  D-023(쇼핑몰 자산을 시험 재료로 쓰지 않는다) 에 따라 그 코퍼스를 지우면서 함께 걷어냈다.
#:  코퍼스 적재·scope 격리는 `test_travel_corpus_retrieval.py` 가 본다.


def test_the_provider_choice_is_explicit_and_never_falls_back(monkeypatch):
    """★고른 제공자가 이상하거나 준비가 안 됐으면 **예외**다 — 다른 칸으로 몰래 넘어가지 않는다."""
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


def test_the_travel_corpus_is_local_only_and_that_is_visible():
    """★여행 코퍼스에는 1536 벡터가 **없다.** 제공자를 openai 로 되돌리면 검색이 **예외**로 죽는다 —
    조용히 0건이 되지 않는다(`retriever.search_policy`).

    ★`[2026-09-22]` 여행 130청크는 **1024칸만** 채워져 있다(OpenAI 크레딧이 없어 로컬 임베딩으로만
      적재했다). 그 사실을 숨기지 않고 여기서 그대로 확인한다.
    """
    from app.core import settings as settings_module
    from app.infrastructure.rag import retriever

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*), count(kc.embedding), count(kc.embedding_1024)
               FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
               WHERE kd.scope = ANY(%s)""", (TRAVEL_SCOPES,))
        total, openai_dim, local_dim = cur.fetchone()
    assert (total, openai_dim, local_dim) == (130, 0, 130), (total, openai_dim, local_dim)

    original = settings_module.get_settings()
    patched = original.model_copy(update={"embedding_provider": "openai"})
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(retriever, "get_settings", lambda: patched)
        retriever._embed_query.cache_clear()
        with pytest.raises(RuntimeError, match="embedding_1024|벡터 칸"):
            retriever.search_policy("demo", "비가 와서 못 간다", TRAVEL_SCOPES)
    retriever._embed_query.cache_clear()


def test_no_other_corpus_is_loaded_in_this_tenant():
    """★★`[2026-10-06]` 적재된 scope 는 **여행 scope 뿐**이어야 한다.

    전에는 같은 tenant 에 쇼핑몰 코퍼스(25문서·306청크)가 함께 있었고, 여행 Team 의
    `knowledge_scope` 에 쇼핑몰 scope 하나(`refund`)가 섞여 들어가 활동 취소 판정이
    쇼핑몰 환불 규정을 근거로 집어 오던 적이 있다(2026-09-22 수정). 코퍼스를 하나로
    줄여 그 사고의 뿌리를 없앴고, 다시 섞이면 여기서 실패한다.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT scope FROM knowledge_documents WHERE tenant_id=%s", ("demo",))
        scopes = {row[0] for row in cur.fetchall()}
    assert scopes == set(TRAVEL_SCOPES), f"여행 밖 scope 가 적재돼 있다: {sorted(scopes - set(TRAVEL_SCOPES))}"
