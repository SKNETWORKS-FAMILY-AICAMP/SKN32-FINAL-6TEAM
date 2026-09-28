-- 로컬 임베딩(bge-m3, 1024차원) 칸. ★`[2026-09-22]`
-- ★기존 1536 칸을 지우거나 바꾸지 않는다 — 두 임베딩을 **공존**시킨다(CLAUDE.md §1).
--   OpenAI 크레딧이 없을 때 로컬 모델로 검색하려면 이 칸을 채운다(`scripts/embed_chunks_local.py`).
-- ★재실행해도 안전하다.
ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_1024 vector(1024);

-- 부분 인덱스 — 채워진 행만 든다(아직 안 채운 코퍼스가 있어도 인덱스가 비대해지지 않는다).
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_1024_idx
    ON knowledge_chunks USING hnsw (embedding_1024 vector_cosine_ops)
    WHERE embedding_1024 IS NOT NULL;
