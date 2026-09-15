"""pgvector policy retriever."""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from pgvector.psycopg import register_vector

from acop_basement.core.context import PolicyChunk
from acop_basement.core.settings import get_guardrails, get_settings
from acop_basement.infrastructure.db.session import get_connection


@lru_cache(maxsize=64)
def _embed_query(query: str) -> list[float]:
    settings = get_settings()
    if not settings.openai_api_key.strip():
        raise RuntimeError("ACOP_OPENAI_API_KEY is required for retrieval; no embedding fallback is available")
    vector = OpenAI(api_key=settings.openai_api_key).embeddings.create(
        model=settings.embedding_model, input=query
    ).data[0].embedding
    expected = get_guardrails().get("rag.embedding_dim")
    if len(vector) != expected:
        raise ValueError(f"query embedding dimension mismatch: expected {expected}, got {len(vector)}")
    # Keep the embedding as a list so pgvector's psycopg adapter serializes it
    # as a vector literal ([...]), rather than a PostgreSQL tuple literal (...).
    return list(vector)


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

            query_embedding = _embed_query(query)
            cur.execute(
                # ★%s::vector 캐스트가 필요하다. register_vector() 는 numpy 배열용
                # 어댑터라 plain list 를 넘기면 double precision[] 로 렌더링되고
                # `operator does not exist: vector <=> double precision[]` 로 죽는다.
                # (2026-08-12: tuple -> `(...)` 로 죽고, list -> 배열로 죽었다.
                #  docs/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md)
                """SELECT chunk_id, content, metadata_json,
                          1 - (embedding <=> %s::vector) AS score
                   FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                   WHERE kd.tenant_id = %s AND kd.scope = ANY(%s)
                   ORDER BY embedding <=> %s::vector LIMIT %s""",
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
