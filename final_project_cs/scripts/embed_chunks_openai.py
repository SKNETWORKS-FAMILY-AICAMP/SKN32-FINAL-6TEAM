# -*- coding: utf-8 -*-
"""정책 청크의 **1536차원 칸(`embedding`)을 서버용 OpenAI 키로 채운다.** `[2026-10-07 사용자 지시]`

    python -m scripts.embed_chunks_openai            # 아직 안 채운 것만
    python -m scripts.embed_chunks_openai --all      # 전부 다시
    python -m scripts.embed_chunks_openai --dry-run  # 몇 개를 채울지만 센다(API 를 부르지 않는다)

★왜 있나. 평소 규정 검색은 Ollama 임베딩(bge-m3, 1024칸)으로 한다. Ollama 가 죽으면 **서버용 OpenAI 키로 질문을 임베딩해 1536 칸으로 검색**하게
  했는데(`rag/retriever.py` · `llm_failover.py`), 여행 규정 코퍼스는 1024 칸만 채워져 있어 그 칸이 **비어 있으면 넘기지 않고 예외**를 낸다.
  이 스크립트가 같은 청크 본문 그대로 1536 칸을 채운다. 1024 칸은 건드리지 않는다(두 벡터가 공존한다).
★서버용 키(`ACOP_OPENAI_API_KEY_SERVER`)로만 부른다 — 개인 키로 대신하지 않는다. 키 값은 어디에도 찍지 않는다.
★비용: 청크 한 개 약 300~600 토큰(`text-embedding-3-small`) — 130개면 몇십 원 안팎이다. 호출 수는 마지막에 적는다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.redaction import masked  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402

DIM = 1536
BATCH = 32


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="이미 채운 것도 다시 만든다")
    parser.add_argument("--dry-run", action="store_true", help="대상 수만 세고 API 를 부르지 않는다")
    args = parser.parse_args()

    settings = get_settings()
    where = "" if args.all else " WHERE embedding IS NULL"
    from pgvector.psycopg import register_vector

    with get_connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(f"SELECT chunk_id, content FROM knowledge_chunks{where} ORDER BY chunk_id")
            rows = cur.fetchall()
        print(f"대상 청크 {len(rows)}개 · 모델 {settings.embedding_model}")
        if args.dry_run or not rows:
            return 0
        key = (settings.openai_api_key_server or "").strip()
        if not key:
            print("★ACOP_OPENAI_API_KEY_SERVER 가 비어 있다 — 서버용 키가 없다", file=sys.stderr)
            return 1
        from openai import OpenAI

        client = OpenAI(api_key=key, timeout=30.0, max_retries=1)
        done = failed = calls = 0
        for start in range(0, len(rows), BATCH):
            batch = rows[start:start + BATCH]
            try:
                calls += 1
                data = client.embeddings.create(model=settings.embedding_model, input=[masked(text) for _, text in batch]).data
                vectors = [item.embedding for item in sorted(data, key=lambda item: item.index)]
                if len(vectors) != len(batch) or any(len(v) != DIM for v in vectors):
                    raise RuntimeError(f"차원 또는 개수가 다르다: {DIM} 차원 {len(batch)}개를 기대했는데 {[len(v) for v in vectors][:3]}")
            except Exception as exc:                                  # noqa: BLE001 — ★조용히 넘기지 않는다: 세어서 마지막에 알린다(키 값은 찍지 않는다)
                failed += len(batch)
                print(f"  실패 {start}~{start + len(batch)}: {type(exc).__name__}", file=sys.stderr)
                continue
            with conn.transaction(), conn.cursor() as cur:
                for (chunk_id, _), vector in zip(batch, vectors):
                    cur.execute("UPDATE knowledge_chunks SET embedding=%s WHERE chunk_id=%s", (vector, chunk_id))
            done += len(batch)
            print(f"  {done}/{len(rows)}")
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), count(embedding), count(embedding_1024) FROM knowledge_chunks")
            total, openai_dim, local_dim = cur.fetchone()
    print(f"채움 {done}/{len(rows)} · 실패 {failed} · API 호출 {calls}번 · 지금 상태: 청크 {total} · 1536칸 {openai_dim} · 1024칸 {local_dim}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
