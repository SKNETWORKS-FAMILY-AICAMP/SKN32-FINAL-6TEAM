# -*- coding: utf-8 -*-
"""이미 적재된 정책 청크를 **로컬 임베딩 모델**로 다시 재 담는다(1024차원 칸).

    python -m scripts.embed_chunks_local            # 아직 안 채운 것만
    python -m scripts.embed_chunks_local --all      # 전부 다시

★`[2026-09-22]` 왜 있나. 정책 검색이 OpenAI 임베딩에만 매여 있어 **크레딧이 없으면 RAG 시험 3건이
  계속 빨갛다**(2026-09-14 부터). 로컬 Ollama 의 `bge-m3` 가 같은 일을 한다 — 차원만 1024 다.

★**청크를 다시 쪼개지 않는다.** DB 에 이미 든 청크 **본문 그대로** 다시 임베딩한다. 적재 스크립트가
  작업 트리에 없어(2026-09-10 확인) 다시 쪼개면 **경계가 달라져** 306개라는 수도, 검사(`check_corpus`)
  결과도 지금 것과 달라진다. 같은 청크에 벡터만 하나 더 붙이는 것이 이 방법의 요점이다.

★**1536 칸을 건드리지 않는다.** 두 벡터가 공존하고, 어느 쪽으로 검색할지는 설정
  (`ACOP_EMBEDDING_PROVIDER`)이 정한다. 조용한 폴백이 아니다 — 고른 쪽 칸이 비어 있으면 검색이
  예외를 낸다.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import get_settings  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402

DIM = 1024


def embed(text: str, *, base_url: str, model: str, timeout: float) -> list[float]:
    """Ollama 자체 임베딩 API. ★본문이 오류여도 200 으로 오는 공급자가 있어 **본문을 본다**."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/embed",
        data=json.dumps({"model": model, "input": text}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    if payload.get("error"):
        raise RuntimeError(f"임베딩 실패: {payload['error']}")
    vectors = payload.get("embeddings") or ([payload["embedding"]] if payload.get("embedding") else [])
    if not vectors or len(vectors[0]) != DIM:
        raise RuntimeError(f"차원이 다르다: {DIM} 을 기대했는데 {len(vectors[0]) if vectors else 0}")
    return list(vectors[0])


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="이미 채운 것도 다시 만든다")
    args = parser.parse_args()

    settings = get_settings()
    base_url = settings.ollama_base_url
    if not base_url:
        print("★ACOP_OLLAMA_BASE_URL 이 비어 있다 — 로컬 임베딩 서버 주소가 없다", file=sys.stderr)
        return 1

    where = "" if args.all else " WHERE embedding_1024 IS NULL"
    from pgvector.psycopg import register_vector

    with get_connection() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(f"SELECT chunk_id, content FROM knowledge_chunks{where} ORDER BY chunk_id")
            rows = cur.fetchall()
        print(f"대상 청크 {len(rows)}개 · 모델 {settings.ollama_embedding_model}")
        done = failed = 0
        for chunk_id, content in rows:
            try:
                vector = embed(content, base_url=base_url, model=settings.ollama_embedding_model,
                               timeout=settings.ollama_timeout_seconds)
            except (RuntimeError, urllib.error.URLError, TimeoutError, OSError) as exc:
                # ★조용히 넘기지 않는다 — 실패를 세어 마지막에 알린다(CLAUDE.md §3).
                failed += 1
                print(f"  실패 {chunk_id}: {type(exc).__name__}: {exc}"[:160], file=sys.stderr)
                continue
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("UPDATE knowledge_chunks SET embedding_1024=%s WHERE chunk_id=%s",
                            (vector, chunk_id))
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(rows)}")
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), count(embedding), count(embedding_1024) FROM knowledge_chunks")
            total, openai_dim, local_dim = cur.fetchone()
    print(f"채움 {done}/{len(rows)} · 실패 {failed} · 지금 상태: 청크 {total} · 1536칸 {openai_dim} · "
          f"1024칸 {local_dim}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
