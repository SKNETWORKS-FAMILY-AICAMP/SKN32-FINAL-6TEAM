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


def test_the_travel_corpus_vectors_are_all_or_nothing_per_provider_and_that_is_visible():
    """★여행 코퍼스의 벡터 칸은 제공자마다 **전부 채워졌거나 전부 비었다** — 일부만 찬 칸으로 검색하면 근거가 몰래 줄어든다.

    ★`[2026-09-22]` 여행 130청크는 처음에 **1024칸만** 채웠다(OpenAI 크레딧이 없어 로컬 임베딩으로만 적재).
    ★`[2026-10-14]` 전에는 「1536칸 = 0」을 그대로 단언했지만, 10-07 넘김 장치 계약(`wiki/external/llm-failover.md`)은 오히려
      유료 대체로 검색하려면 1536칸을 **채우라**고 정했다(`scripts/embed_chunks_openai.py`). 로컬 DB 는 채워져 있고 x600 서버는 비어 있다 —
      둘 다 정상 상태이고, 일부만 찬 상태만 막는다. 비어 있으면 그 제공자로 검색할 때 **예외**(조용히 0건이 아님),
      차 있으면 그 칸으로 검색한다(유료 호출 없이 질문 벡터를 대신 넣어 본다).
    """
    from app.core import settings as settings_module
    from app.infrastructure.rag import retriever

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*), count(kc.embedding), count(kc.embedding_1024)
               FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
               WHERE kd.scope = ANY(%s)""", (TRAVEL_SCOPES,))
        total, openai_dim, local_dim = cur.fetchone()
    assert total == 130 and local_dim == 130 and openai_dim in (0, total), (total, openai_dim, local_dim)

    original = settings_module.get_settings()
    patched = original.model_copy(update={"embedding_provider": "openai"})
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(retriever, "get_settings", lambda: patched)
        retriever._embed_query.cache_clear()
        if openai_dim == 0:
            with pytest.raises(RuntimeError, match="embedding_1024|벡터 칸"):
                retriever.search_policy("demo", "비가 와서 못 간다", TRAVEL_SCOPES)
        else:
            monkeypatch.setattr(retriever, "_embed_query", lambda query: [0.01] * 1536)
            assert retriever.search_policy("demo", "비가 와서 못 간다", TRAVEL_SCOPES, top_k=3)
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
