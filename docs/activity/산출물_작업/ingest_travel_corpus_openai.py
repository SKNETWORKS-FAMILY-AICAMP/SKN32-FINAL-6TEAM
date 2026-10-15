"""작업용 적재 — knowledge.ingest 의 청킹 규칙(load_corpus/_metadata)을 그대로 쓰고, 임베딩만 OpenAI(1536칸)로."""
import sys
from pathlib import Path
from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.types.json import Json
from app.core.settings import get_settings, get_guardrails
from app.infrastructure.db.session import get_connection
from knowledge.ingest import load_corpus, _metadata

manifest = Path(sys.argv[1]) / "manifest.json"
docs = load_corpus(manifest)
total = sum(len(d.sections) for d in docs)
print(f"문서 {len(docs)} · 청크 {total}")
settings = get_settings()
dim = get_guardrails().get("rag.embedding_dim")
pending, ids = [], {}
with get_connection() as conn:
    register_vector(conn)
    with conn.cursor() as cur:
        for d in docs:
            f = d.frontmatter
            cur.execute("""SELECT document_id FROM knowledge_documents WHERE tenant_id=%s AND source_uri=%s AND title=%s
                           AND scope=%s AND version=%s AND pii_class=%s ORDER BY created_at LIMIT 1""",
                        (d.manifest["tenant_id"], f["source_uri"], f["title"], f["scope"], str(f["version"]), f["pii_class"]))
            row = cur.fetchone()
            if row is None:
                cur.execute("""INSERT INTO knowledge_documents (tenant_id,title,source_uri,scope,version,pii_class)
                               VALUES (%s,%s,%s,%s,%s,%s) RETURNING document_id""",
                            (d.manifest["tenant_id"], f["title"], f["source_uri"], f["scope"], str(f["version"]), f["pii_class"]))
                row = cur.fetchone()
            ids[d.manifest["document_id"]] = row[0]
            for s in d.sections:
                cur.execute("SELECT 1 FROM knowledge_chunks WHERE document_id=%s AND chunk_no=%s", (row[0], s.number))
                if cur.fetchone() is None:
                    pending.append((row[0], s.number, s.content, _metadata(d, s)))
    print(f"임베딩할 청크 {len(pending)}개 · 모델 {settings.embedding_model} · 배치 64")
    if "--dry" in sys.argv or not pending:
        conn.rollback(); print("(쓰지 않음)" if "--dry" in sys.argv else "(이미 다 적재됨)"); raise SystemExit
    client = OpenAI(api_key=settings.openai_api_key)
    vecs, calls, tokens = [], 0, 0
    for off in range(0, len(pending), 64):
        batch = pending[off:off + 64]
        r = client.embeddings.create(model=settings.embedding_model, input=[b[2] for b in batch])
        calls += 1; tokens += r.usage.total_tokens
        vecs.extend(i.embedding for i in sorted(r.data, key=lambda x: x.index))
    assert all(len(v) == dim for v in vecs), "차원 불일치"
    with conn.cursor() as cur:
        for b, v in zip(pending, vecs):
            cur.execute("""INSERT INTO knowledge_chunks (document_id,chunk_no,content,metadata_json,embedding)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT (document_id,chunk_no) DO NOTHING""",
                        (b[0], b[1], b[2], Json(b[3]), v))
    conn.commit()
    print(f"완료: API 호출 {calls}회 · 입력 토큰 {tokens:,}")
