-- 정책 청크의 1536 칸(OpenAI)을 NULL 허용으로 바꾼다. ★`[2026-09-22]`
--
-- ★왜. 020 이 1024 칸(bge-m3)을 더해 두 임베딩을 공존시켰지만 `embedding` 은 여전히
--   NOT NULL 이었다. 그래서 **로컬 임베딩만으로 적재하는 코퍼스는 아예 INSERT 가 안 된다** —
--   OpenAI 크레딧이 없는 지금 여행 코퍼스를 넣을 길이 없었다.
-- ★대안으로 0 벡터를 채우는 방법이 있지만 쓰지 않는다. 0 벡터는 「값이 없다」가 아니라
--   「원점과 같다」라서 코사인 검색에 실제로 끼어든다 — 없는 것을 있는 것으로 적는 꼴이다.
--   NULL 은 검색 쿼리(`WHERE {column} IS NOT NULL`)가 이미 걸러 준다.
-- ★기존 306행은 건드리지 않는다. 제약만 푸는 것이라 값은 그대로 남는다.
-- ★재실행해도 안전하다(이미 NULL 허용이면 DROP NOT NULL 은 아무 일도 하지 않는다).
ALTER TABLE knowledge_chunks ALTER COLUMN embedding DROP NOT NULL;

-- 1536 칸의 hnsw 인덱스도 채워진 행만 들게 한다 — 020 이 1024 칸에 건 것과 같은 모양.
-- ★인덱스를 지웠다 다시 만드는 것이라 **검색이 잠깐 느려질 수 있다.** 306행 규모에서는
--   체감되지 않지만, 코퍼스가 커진 뒤에 이 파일을 다시 돌리면 그 점을 알고 돌린다.
DROP INDEX IF EXISTS knowledge_chunks_embedding_idx;
CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
