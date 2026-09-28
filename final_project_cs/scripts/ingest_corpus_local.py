# -*- coding: utf-8 -*-
"""정책 코퍼스를 **로컬 임베딩**(Ollama `bge-m3`, 1024차원)으로 적재한다.

    python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json --dry-run
    python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json

★**왜 따로 있나.** `knowledge/ingest.py` 는 OpenAI 임베딩(1536칸) 전용이고 키가 없으면
  첫 줄에서 죽는다. 그 파일은 **쇼핑몰 306청크가 어떻게 들어갔는지의 기록**이라 고치지
  않고 그대로 둔다. 이쪽은 같은 문서를 **1024칸**으로 넣는 길이다.

★**청크를 여기서 쪼개지 않는다.** 문서를 절로 나누는 코드는 `knowledge/ingest.py` 의
  `load_corpus()`/`_parse_document()` 하나뿐이고 이 스크립트는 그것을 **그대로 부른다.**
  쪼개는 코드가 둘이 되면 같은 문서가 스크립트마다 다른 청크로 들어간다.

── 청크 경계 규칙 (다음 사람이 같은 청크를 다시 만들 수 있게) ──────────────────
  1. 문서는 `---` frontmatter + 본문이다. frontmatter 는 청크가 아니다.
  2. **`## ` 로 시작하는 줄 하나가 청크 하나**다. 경계는 다음 `## ` 직전까지.
     첫 `## ` 앞의 머리말(문서가 무엇을 다루는지 적은 문단)은 **청크가 아니다.**
  3. 제목 줄은 본문에서 빼고 `metadata_json.section_title` 로 싣는다.
  4. 본문은 앞뒤 공백만 떼고 **그대로** 넣는다 — 문장 재배열·요약·길이 맞춤을 하지 않는다.
  5. `chunk_no` 는 문서 안에서 1부터 센 절 번호다. `(document_id, chunk_no)` 가 UNIQUE 다.
  6. 절 수는 manifest 의 `section_count` 와 **같아야 한다.** 다르면 적재 전에 죽는다.
  7. 길이·중복 기준은 `python -m scripts.check_corpus` 가 본다. 적재 전에 그것이 먼저 통과해야 한다.

★**재실행해도 안전하다.** 같은 (문서, 절 번호)가 이미 있으면 건너뛴다. 본문이 바뀐
  문서를 다시 넣으려면 `--replace` 로 그 문서의 청크를 지우고 다시 만든다.

★**조용한 폴백이 없다.** 임베딩 서버가 없거나 차원이 다르면 예외로 죽는다. 실패한
  청크 수를 세어 마지막에 알리고, 하나라도 실패하면 종료코드가 1 이다.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from psycopg.types.json import Json  # noqa: E402

from app.core.settings import get_settings  # noqa: E402
from app.infrastructure.db.session import get_connection  # noqa: E402
from knowledge.ingest import _metadata, load_corpus  # noqa: E402

#: 로컬 임베딩 차원. `app/infrastructure/rag/retriever.py` 의 `PROVIDERS["ollama"]` 와 같아야 한다.
DIM = 1024
COLUMN = "embedding_1024"


def embed(text: str, *, base_url: str, model: str, timeout: float) -> list[float]:
    """Ollama `/api/embed`. ★본문이 오류여도 200 으로 오는 공급자가 있어 **본문을 본다**."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/embed",
        data=json.dumps({"model": model, "input": text}).encode(),
        headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    if payload.get("error"):
        raise RuntimeError(f"임베딩 실패: {payload['error']}")
    vectors = payload.get("embeddings") or ([payload["embedding"]] if payload.get("embedding") else [])
    if not vectors:
        raise RuntimeError("임베딩이 빈 응답을 줬다")
    if len(vectors[0]) != DIM:
        raise RuntimeError(f"차원이 다르다: {DIM} 을 기대했는데 {len(vectors[0])}")
    return list(vectors[0])


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True,
                        help="적재할 코퍼스의 manifest.json (예: knowledge/travel/manifest.json)")
    parser.add_argument("--dry-run", action="store_true", help="DB 를 건드리지 않고 문서·청크 수만 센다")
    parser.add_argument("--replace", action="store_true",
                        help="이 코퍼스의 기존 청크를 지우고 다시 만든다(본문을 고쳤을 때)")
    args = parser.parse_args()

    manifest_path = (REPO_ROOT / args.manifest) if not Path(args.manifest).is_absolute() else Path(args.manifest)
    documents = load_corpus(manifest_path)
    chunks = sum(len(d.sections) for d in documents)
    print(f"코퍼스 {manifest_path.relative_to(REPO_ROOT)} — 문서 {len(documents)} · 절 {chunks}")
    if args.dry_run:
        return 0

    settings = get_settings()
    if not settings.ollama_base_url:
        print("★ACOP_OLLAMA_BASE_URL 이 비어 있다 — 로컬 임베딩 서버 주소가 없다", file=sys.stderr)
        return 1
    model = settings.ollama_embedding_model
    print(f"임베딩 모델 {model} · {DIM}차원 · 칸 {COLUMN}")

    from pgvector.psycopg import register_vector

    done = skipped = failed = 0
    with get_connection() as conn:
        register_vector(conn)
        for doc in documents:
            f = doc.frontmatter
            tenant_id = doc.manifest["tenant_id"]
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT document_id FROM knowledge_documents
                       WHERE tenant_id=%s AND source_uri=%s AND title=%s AND scope=%s
                         AND version=%s AND pii_class=%s
                       ORDER BY created_at LIMIT 1""",
                    (tenant_id, f["source_uri"], f["title"], f["scope"], f["version"], f["pii_class"]))
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """INSERT INTO knowledge_documents
                           (tenant_id,title,source_uri,scope,version,pii_class)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING document_id""",
                        (tenant_id, f["title"], f["source_uri"], f["scope"], f["version"], f["pii_class"]))
                    row = cur.fetchone()
                document_uuid = row[0]
                if args.replace:
                    cur.execute("DELETE FROM knowledge_chunks WHERE document_id=%s", (document_uuid,))
            conn.commit()

            for section in doc.sections:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM knowledge_chunks WHERE document_id=%s AND chunk_no=%s",
                                (document_uuid, section.number))
                    if cur.fetchone() is not None:
                        skipped += 1
                        continue
                try:
                    vector = embed(section.content, base_url=settings.ollama_base_url, model=model,
                                   timeout=settings.ollama_timeout_seconds)
                except (RuntimeError, urllib.error.URLError, TimeoutError, OSError) as exc:
                    # ★조용히 넘기지 않는다 — 실패를 세어 마지막에 알린다(CLAUDE.md §3).
                    failed += 1
                    print(f"  실패 {f['document_id']}#c{section.number}: "
                          f"{type(exc).__name__}: {exc}"[:180], file=sys.stderr)
                    continue
                with conn.transaction(), conn.cursor() as cur:
                    cur.execute(
                        f"""INSERT INTO knowledge_chunks
                            (document_id,chunk_no,content,metadata_json,{COLUMN})
                            VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT (document_id,chunk_no) DO NOTHING""",
                        (document_uuid, section.number, section.content,
                         Json(_metadata(doc, section)), vector))
                done += 1
            print(f"  {f['document_id']} ({f['scope']}) — 넣음 {done} · 건너뜀 {skipped} · 실패 {failed}")

        scopes = sorted({d.frontmatter["scope"] for d in documents})
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT count(DISTINCT kd.document_id), count(*), count(kc.{COLUMN})
                    FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
                    WHERE kd.tenant_id=%s AND kd.scope = ANY(%s)""",
                (documents[0].manifest["tenant_id"], scopes))
            doc_count, chunk_count, filled = cur.fetchone()
    print(f"지금 이 코퍼스 상태: 문서 {doc_count} · 청크 {chunk_count} · {COLUMN} 채워짐 {filled}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
