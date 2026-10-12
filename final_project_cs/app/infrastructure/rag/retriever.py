"""pgvector policy retriever."""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from pgvector.psycopg import register_vector

from app.core.context import PolicyChunk
from app.core.settings import get_guardrails, get_settings
from app.infrastructure.db.session import get_connection


#: 제공자별 (벡터 칸, 차원). ★`[2026-09-22]` 두 임베딩이 **공존한다** — 1536 칸을 지우지 않았다.
#:  어느 쪽으로 검색할지는 설정(`ACOP_EMBEDDING_PROVIDER`)이 정하고, **고른 쪽 칸이 비어 있으면
#:  검색은 예외를 낸다.** 다른 칸으로 몰래 넘어가지 않는다(RULE.md §3.2 「신호 없는 축소 금지」).
PROVIDERS = {"openai": ("embedding", 1536), "ollama": ("embedding_1024", 1024)}


def _provider() -> tuple[str, str, int]:
    name = (get_settings().embedding_provider or "openai").strip().lower()
    if name not in PROVIDERS:
        raise RuntimeError(f"ACOP_EMBEDDING_PROVIDER 는 {sorted(PROVIDERS)} 중 하나여야 한다: {name!r}")
    column, dim = PROVIDERS[name]
    return name, column, dim


@lru_cache(maxsize=64)
def _embed_query(query: str) -> list[float]:
    settings = get_settings()
    name, _, dim = _provider()
    if name == "ollama":
        vector = _embed_with_ollama(query, settings)
    else:
        if not settings.openai_api_key.strip():
            raise RuntimeError("ACOP_OPENAI_API_KEY is required for retrieval; no embedding fallback is available")
        vector = OpenAI(api_key=settings.openai_api_key).embeddings.create(
            model=settings.embedding_model, input=query
        ).data[0].embedding
    if len(vector) != dim:
        raise ValueError(f"query embedding dimension mismatch: expected {dim}, got {len(vector)}")
    # Keep the embedding as a list so pgvector's psycopg adapter serializes it
    # as a vector literal ([...]), rather than a PostgreSQL tuple literal (...).
    return list(vector)


def _embed_with_ollama(query: str, settings) -> list[float]:
    """로컬 임베딩(Ollama `/api/embed`). ★본문이 오류여도 200 으로 오는 공급자가 있어 본문을 본다."""
    import json
    import urllib.request

    if not settings.ollama_base_url:
        raise RuntimeError("ACOP_EMBEDDING_PROVIDER=ollama 인데 ACOP_OLLAMA_BASE_URL 이 비어 있다")
    timeout = settings.ollama_timeout_seconds
    if getattr(settings, "llm_failover_enabled", False):       # ★`[2026-10-07]` 넘김 장치가 켜져 있으면 오래 기다리지 않는다(고객 응답 15초 안에 API 까지)
        timeout = min(timeout, float(settings.llm_failover_primary_timeout_seconds))
    request = urllib.request.Request(
        settings.ollama_base_url.rstrip("/") + "/api/embed",
        data=json.dumps({"model": settings.ollama_embedding_model, "input": query}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    if payload.get("error"):
        raise RuntimeError(f"로컬 임베딩 실패: {payload['error']}")
    vectors = payload.get("embeddings") or ([payload["embedding"]] if payload.get("embedding") else [])
    if not vectors:
        raise RuntimeError("로컬 임베딩이 빈 응답을 줬다")
    return list(vectors[0])


def _query_vector(cur, tenant_id: str, allowed_scopes: list[str], name: str, column: str, query: str) -> tuple[str, list[float]]:
    """질문의 벡터와 **그 벡터로 검색할 칸**. 평소에는 고른 제공자 그대로다.

    ★`[2026-10-07 사용자 지시]` 모델 서버 넘김 장치(`llm_failover.py`)가 켜져 있고 제공자가 ollama 일 때, Ollama 임베딩이 안 되면(연결 · 시간 초과 · 서킷 열림)
      **서버용 OpenAI 키로 질문을 임베딩하고 1536 칸으로 검색한다.** 그 칸이 비어 있으면 **넘기지 않고 예외를 올린다** — 칸이 다른 벡터로 몰래 검색하면
      근거 0건이 「규정이 없다」로 읽힌다(RULE.md §3.2). 칸 채우기: `python -m scripts.embed_chunks_openai`."""
    settings = get_settings()
    from app.infrastructure import llm_failover as failover

    if name != "ollama" or not failover.embedding_failover_enabled(settings):
        return column, _embed_query(query)
    breaker = failover.breaker_for(f"ollama-embed@{(settings.ollama_base_url or '').rstrip('/')}",
                                   threshold=int(settings.llm_failover_failures), open_seconds=float(settings.llm_failover_open_seconds))
    reason = "circuit_open"
    if breaker.allow():
        try:
            vector = _embed_query(query)
        except Exception as exc:                                    # noqa: BLE001 — 어떤 실패든 다음 경로로(이유만 남긴다)
            breaker.failure()
            reason = type(exc).__name__
        else:
            breaker.success()
            return column, vector
    cur.execute("SELECT 1 FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id) "
                "WHERE kd.tenant_id=%s AND kd.scope = ANY(%s) AND kc.embedding IS NOT NULL LIMIT 1", (tenant_id, allowed_scopes))
    if cur.fetchone() is None:
        raise RuntimeError(f"Ollama 임베딩이 안 된다({reason}) — OpenAI 로 넘기려 했으나 scope {sorted(allowed_scopes)} 의 1536 칸(embedding)이 비어 있다. "
                           "python -m scripts.embed_chunks_openai 로 먼저 채워야 한다")
    vector = failover.embed_with_api(settings, query)
    failover.record_fallback("embed", reason)
    if len(vector) != PROVIDERS["openai"][1]:
        raise ValueError(f"fallback query embedding dimension mismatch: expected {PROVIDERS['openai'][1]}, got {len(vector)}")
    return PROVIDERS["openai"][0], list(vector)


def search_policy(
    tenant_id: str, query: str, allowed_scopes: list[str], top_k: int | None = None
) -> list[PolicyChunk]:
    limit = get_guardrails().get("rag.top_k") if top_k is None else top_k
    with get_connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            # Avoid an external embedding call when the tenant/scope predicate
            # is empty; this also makes tenant isolation deterministic.
            cur.execute(
                "SELECT 1 FROM knowledge_documents WHERE tenant_id=%s AND scope = ANY(%s) LIMIT 1",
                (tenant_id, allowed_scopes),
            )
            if cur.fetchone() is None:
                return []

            name, column, _dim = _provider()
            # ★`[2026-09-22]` 문서는 있는데 **고른 제공자의 벡터 칸이 통째로 비어 있으면** 예외다.
            #   아래 검색은 `{column} IS NOT NULL` 로 거르므로 그냥 두면 0건이 돌아가고, 부르는 쪽은
            #   그걸 「규정이 없다」로 읽는다 — 신호 없는 축소이고 이 저장소가 금지하는 폴백이다
            #   (RULE.md §3.2). 실제로 여행 코퍼스는 1024칸만 채워져 있어서(OpenAI 크레딧 없음)
            #   제공자를 openai 로 되돌리면 여행 Team 이 전부 조용히 근거 0건이 된다.
            cur.execute(
                f"""SELECT 1 FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                    WHERE kd.tenant_id=%s AND kd.scope = ANY(%s) AND kc.{column} IS NOT NULL LIMIT 1""",
                (tenant_id, allowed_scopes),
            )
            if cur.fetchone() is None:
                raise RuntimeError(
                    f"scope {sorted(allowed_scopes)} 에 문서는 있는데 {name} 제공자의 벡터 칸"
                    f"({column})이 비어 있다 — 그 코퍼스를 이 제공자로 적재해야 한다"
                    " (scripts/ingest_corpus_local.py · scripts/embed_chunks_local.py)")

            column, query_embedding = _query_vector(cur, tenant_id, allowed_scopes, name, column, query)
            cur.execute(
                # ★%s::vector 캐스트가 필요하다. register_vector() 는 numpy 배열용
                # 어댑터라 plain list 를 넘기면 double precision[] 로 렌더링되고
                # `operator does not exist: vector <=> double precision[]` 로 죽는다.
                # (2026-08-12: tuple -> `(...)` 로 죽고, list -> 배열로 죽었다.
                #  wiki/records/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md)
                f"""SELECT chunk_id, content, metadata_json,
                          1 - ({column} <=> %s::vector) AS score
                   FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                   WHERE kd.tenant_id = %s AND kd.scope = ANY(%s) AND {column} IS NOT NULL
                   ORDER BY {column} <=> %s::vector LIMIT %s""",
                (query_embedding, tenant_id, allowed_scopes, query_embedding, limit),
            )
            rows = cur.fetchall()
    return [
        PolicyChunk(
            document_id=row[2]["document_id"],
            chunk_no=int(row[2]["chunk_no"]),
            content=row[1],
            score=float(row[3]),
            scope=row[2]["scope"],
        )
        for row in rows
]
