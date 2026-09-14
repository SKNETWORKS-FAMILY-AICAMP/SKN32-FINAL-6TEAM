"""Load the policy corpus into PostgreSQL/pgvector."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from openai import OpenAI
from psycopg.types.json import Json
from pgvector.psycopg import register_vector

from app.core.settings import get_guardrails, get_settings
from app.infrastructure.db.session import get_connection

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "knowledge" / "manifest.json"


@dataclass(frozen=True)
class Section:
    number: int
    title: str
    content: str


@dataclass(frozen=True)
class Document:
    manifest: dict[str, Any]
    frontmatter: dict[str, Any]
    sections: list[Section]


def _parse_document(path: Path, manifest_entry: dict[str, Any]) -> Document:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError(f"frontmatter missing: {path}")
    frontmatter = yaml.safe_load(match.group(1))
    if not isinstance(frontmatter, dict):
        raise ValueError(f"invalid frontmatter: {path}")
    body = match.group(2).strip()
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", body))
    sections: list[Section] = []
    for number, heading in enumerate(matches, 1):
        start = heading.end()
        end = matches[number].start() if number < len(matches) else len(body)
        content = body[start:end].strip()
        if not content:
            raise ValueError(f"empty section {number}: {path}")
        sections.append(Section(number, heading.group(1).strip(), content))
    expected = manifest_entry.get("section_count")
    if expected != len(sections):
        raise ValueError(f"section count mismatch for {manifest_entry['document_id']}: {len(sections)} != {expected}")
    if frontmatter.get("document_id") != manifest_entry.get("document_id"):
        raise ValueError(f"document_id mismatch: {path}")
    return Document(manifest_entry, frontmatter, sections)


def load_corpus() -> list[Document]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    base = MANIFEST_PATH.parent
    tenant_id = manifest["tenant_id"]
    return [
        _parse_document(base / entry["file"], {**entry, "tenant_id": tenant_id})
        for entry in manifest["documents"]
    ]


def _metadata(doc: Document, section: Section) -> dict[str, Any]:
    return {
        "tenant_id": doc.manifest["tenant_id"],
        "scope": doc.frontmatter["scope"],
        "document_id": doc.frontmatter["document_id"],
        "version": doc.frontmatter["version"],
        "pii_class": doc.frontmatter["pii_class"],
        "effective_from": str(doc.frontmatter["effective_from"]),
        "section_title": section.title,
        "chunk_no": section.number,
    }


def dry_run() -> tuple[int, int]:
    documents = load_corpus()
    chunks = sum(len(document.sections) for document in documents)
    print(f"dry-run: documents={len(documents)} chunks={chunks}")
    return len(documents), chunks


def ingest() -> None:
    settings = get_settings()
    if not settings.openai_api_key.strip():
        raise RuntimeError("ACOP_OPENAI_API_KEY is required for ingest; no embedding fallback is available")
    guardrails = get_guardrails()
    embedding_dim = guardrails.get("rag.embedding_dim")
    documents = load_corpus()
    client = OpenAI(api_key=settings.openai_api_key)
    print(f"ingest: documents={len(documents)} chunks={sum(len(d.sections) for d in documents)}")

    with get_connection() as conn:
        register_vector(conn)
        pending: list[tuple[Any, ...]] = []
        document_ids: dict[str, Any] = {}
        with conn.cursor() as cur:
            for doc in documents:
                f = doc.frontmatter
                cur.execute(
                    """SELECT document_id FROM knowledge_documents
                       WHERE tenant_id=%s AND source_uri=%s AND title=%s AND scope=%s AND version=%s AND pii_class=%s
                       ORDER BY created_at LIMIT 1""",
                    (doc.manifest["tenant_id"], f["source_uri"], f["title"], f["scope"], f["version"], f["pii_class"]),
                )
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """INSERT INTO knowledge_documents
                           (tenant_id,title,source_uri,scope,version,pii_class)
                           VALUES (%s,%s,%s,%s,%s,%s) RETURNING document_id""",
                        (doc.manifest["tenant_id"], f["title"], f["source_uri"], f["scope"], f["version"], f["pii_class"]),
                    )
                    row = cur.fetchone()
                document_ids[doc.manifest["document_id"]] = row[0]
                for section in doc.sections:
                    metadata = _metadata(doc, section)
                    cur.execute("SELECT 1 FROM knowledge_chunks WHERE document_id=%s AND chunk_no=%s", (row[0], section.number))
                    if cur.fetchone() is None:
                        pending.append((row[0], section.number, section.content, metadata))

        print(f"embedding: pending_chunks={len(pending)} model={settings.embedding_model}")
        embeddings: list[list[float]] = []
        batch_size = 64
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            response = client.embeddings.create(model=settings.embedding_model, input=[row[2] for row in batch])
            ordered = sorted(response.data, key=lambda item: item.index)
            embeddings.extend([item.embedding for item in ordered])
            print(f"embedding: {min(offset + len(batch), len(pending))}/{len(pending)}")
        if any(len(vector) != embedding_dim for vector in embeddings):
            raise ValueError(f"embedding dimension mismatch: expected {embedding_dim}")

        with conn.cursor() as cur:
            for row, vector in zip(pending, embeddings):
                cur.execute(
                    """INSERT INTO knowledge_chunks
                       (document_id,chunk_no,content,metadata_json,embedding)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (document_id,chunk_no) DO NOTHING""",
                    (row[0], row[1], row[2], Json(row[3]), vector),
                )
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s", ("demo",))
            document_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id) WHERE kd.tenant_id=%s", ("demo",))
            chunk_count = cur.fetchone()[0]
        print(f"loaded: documents={document_count} chunks={chunk_count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
    else:
        ingest()


if __name__ == "__main__":
    main()
