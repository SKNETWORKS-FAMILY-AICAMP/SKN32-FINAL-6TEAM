# -*- coding: utf-8 -*-
"""관광공사 목록 장소의 임베딩 — 한 번 만들어 저장하고, 취향의 가까움과 분류 추정에 쓴다. `[2026-10-07 사용자 결정 — uiux 전달]` 마이그레이션 058

사용자 결정: 「대안 고르기는 규칙(분류 나무 · 영업시간 · 거리 · 여유) + 임베딩(비슷한 경험 · 분류 빈 장소 채우기 — **한 번 채워 저장**)」.

★임베딩 글 = 장소 이름 + 관광공사 종류 이름(`catalog_text`). 주소 · 소개글 · 사진은 안 쓴다(창작물을 모델에 먹이지 않는다).
★요청 자리에서 장소를 임베딩하지 않는다 — 목록 장소는 `fill_catalog` 가 미리 만들어 `place_embeddings` 에 둔다(스크립트 `scripts/embed_place_catalog.py`, 기본은 건수만 세는 dry-run).
  후보를 고를 때는 **저장된 벡터만** 읽는다. 저장분이 없으면 이 기능은 조용히 쉬지 않고 **못 썼다고 알린다**(`taste.ranked_by` = `count` — 규칙 순서).
★분류 추정(`estimate_class`): 이름이 같은 목록 항목이 없을 때 **가장 닮은 목록 장소들의 분류 투표**로 중분류를 짐작한다. 짐작한 값은 늘 **`estimated`** 등급으로 적고
  (`name_match` 가 더 믿을 수 있다), 이유 문장에 「관광공사 분류」라고 쓰지 않는다. 투표가 갈리거나 닮은 정도가 낮으면 모른다고 둔다(지어내지 않는다).
★임베더는 주입한다(`Embedder` — 글 목록 → 벡터 목록). 실제 모델은 Ollama `/api/embed`(bge-m3, 1024차원) — 설정 `ollama_base_url` · `ollama_embedding_model`.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Callable, Sequence

from app.core.settings import get_settings

DIM = 1024
Embedder = Callable[[Sequence[str]], list[list[float]]]
#: 분류를 짐작할 때 — 가장 닮은 몇 곳이 투표하고, 얼마나 닮아야 하고, 표가 얼마나 몰려야 하는가. 출처: **우리가 고른 값**(실측으로 조정한다)
KNN_K = 7
MIN_SIMILARITY = 0.55
MIN_SHARE = 0.6


def model_name() -> str:
    return str(get_settings().ollama_embedding_model)


def ollama_embedder(settings: Any | None = None) -> Embedder:
    """Ollama `/api/embed` 로 글 목록을 한 번에 임베딩한다. 못 부르면 예외(조용히 빈 벡터를 주지 않는다)."""
    import urllib.request

    settings = settings or get_settings()
    if not settings.ollama_base_url:
        raise RuntimeError("ACOP_OLLAMA_BASE_URL 이 비어 있다")

    def embed(texts: Sequence[str]) -> list[list[float]]:
        request = urllib.request.Request(settings.ollama_base_url.rstrip("/") + "/api/embed",
                                         data=json.dumps({"model": settings.ollama_embedding_model, "input": list(texts)}).encode(),
                                         headers={"content-type": "application/json"})
        with urllib.request.urlopen(request, timeout=float(settings.ollama_timeout_seconds)) as response:
            payload = json.loads(response.read())
        if payload.get("error"):
            raise RuntimeError(f"임베딩 실패: {payload['error']}")
        vectors = payload.get("embeddings") or []
        if len(vectors) != len(texts) or any(len(v) != DIM for v in vectors):
            raise RuntimeError(f"임베딩 응답 모양이 다르다(글 {len(texts)} · 벡터 {len(vectors)})")
        return [list(map(float, v)) for v in vectors]

    return embed


def catalog_text(title: str, type_label: str | None) -> str:
    return f"{title.strip()} ({type_label})" if type_label else title.strip()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _lit(vector: Sequence[float]) -> str:
    """벡터를 SQL 글 리터럴 `[a,b,…]` 로 — `%s::vector` 로 받는다. ★`register_vector` 는 numpy 용이라 일반 목록을 넘기면 배열로 나가 `vector <=> double precision[]` 로 죽는다
    (`rag/retriever.py` 의 2026-08-12 기록). 글 리터럴이면 어댑터에 기대지 않는다."""
    return "[" + ",".join(f"{float(x):.7g}" for x in vector) + "]"


def _parse(text: str) -> list[float]:
    return [float(x) for x in text.strip("[]").split(",")] if text else []


# ── 채우기 ──────────────────────────────────────────────────────
def missing(conn, tenants: list[str], *, limit: int | None = None) -> list[tuple[str, str, str, str | None]]:
    """아직 임베딩이 없는(또는 이름이 바뀌어 낡은) 목록 장소 — `(tenant_id, content_id, title, 종류 이름)`. 쇼핑 · 음식 가지(SH · FD)는 대상이 아니다(취향 · 분류 추정에 안 쓴다 — 4,440곳 약국 · 편의점을 만들지 않는다)."""
    from .terms import category_label

    out: list[tuple[str, str, str, str | None]] = []
    with conn.cursor() as cur:
        cur.execute("SELECT c.tenant_id, c.content_id, c.title, c.content_type_id, e.text_sha FROM place_catalog c "
                    "LEFT JOIN place_embeddings e ON e.tenant_id=c.tenant_id AND e.content_id=c.content_id AND e.model=%s "
                    "WHERE c.tenant_id = ANY(%s) AND c.source='tour_api' AND c.title IS NOT NULL "
                    "AND COALESCE(c.raw_json->>'lclsSystm1','') NOT IN ('SH','FD') ORDER BY c.tenant_id, c.content_id",
                    (model_name(), tenants))
        for tenant_id, content_id, title, content_type, sha in cur.fetchall():
            text = catalog_text(title, category_label(content_type))
            if sha != _sha(text):
                out.append((tenant_id, str(content_id), title, category_label(content_type)))
            if limit is not None and len(out) >= limit:
                break
    return out


def fill_catalog(conn, tenants: list[str], embed: Embedder, *, limit: int | None = None, batch: int = 32, dry_run: bool = True) -> dict[str, int]:
    """없는 임베딩을 만든다. `dry_run`(기본)이면 **세기만** 한다. 센 값: `missing`(만들 것) · `written`(만든 것)."""
    todo = missing(conn, tenants, limit=limit)
    if dry_run or not todo:
        return {"missing": len(todo), "written": 0}
    written = 0
    for start in range(0, len(todo), batch):
        chunk = todo[start:start + batch]
        texts = [catalog_text(title, label) for _t, _c, title, label in chunk]
        vectors = embed(texts)
        with conn.transaction(), conn.cursor() as cur:
            for (tenant_id, content_id, _title, _label), text, vector in zip(chunk, texts, vectors):
                cur.execute("INSERT INTO place_embeddings (tenant_id, content_id, model, text_sha, embedding) VALUES (%s,%s,%s,%s,%s::vector) "
                            "ON CONFLICT (tenant_id, content_id, model) DO UPDATE SET text_sha=EXCLUDED.text_sha, embedding=EXCLUDED.embedding, created_at=now()",
                            (tenant_id, content_id, model_name(), _sha(text), _lit(vector)))
                written += 1
    return {"missing": len(todo), "written": written}


# ── 읽기 ────────────────────────────────────────────────────────
def vectors_of(conn, tenants: list[str], content_ids: Sequence[str]) -> dict[str, list[float]]:
    """저장된 벡터 — `{content_id: 벡터}`. 없는 것은 빠진다."""
    if not content_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute("SELECT content_id, embedding::text FROM place_embeddings WHERE tenant_id = ANY(%s) AND model=%s AND content_id = ANY(%s)",
                    (tenants, model_name(), list(content_ids)))
        return {str(content_id): _parse(vector) for content_id, vector in cur.fetchall()}


def centroid(vectors: Sequence[Sequence[float]]) -> list[float] | None:
    if not vectors:
        return None
    mean = [sum(column) / len(vectors) for column in zip(*vectors)]
    norm = math.sqrt(sum(x * x for x in mean))
    return [x / norm for x in mean] if norm else None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


# ── 분류 추정 ───────────────────────────────────────────────────
def estimate_class(conn, tenants: list[str], vector: Sequence[float]) -> dict[str, Any] | None:
    """이 벡터와 가장 닮은 목록 장소 `KNN_K` 곳의 **중분류 투표** — `{"lcls2", "lcls1", "share", "similarity", "voters"}` 또는 None(모른다).

    닮은 정도 평균이 `MIN_SIMILARITY` 미만이거나 1위 표가 `MIN_SHARE` 미만이면 모른다. 쇼핑 · 음식 · 숙박 가지는 투표하지 않는다(임베딩을 안 만들었다)."""
    literal = _lit(vector)
    with conn.cursor() as cur:
        cur.execute("SELECT c.raw_json->>'lclsSystm1', c.raw_json->>'lclsSystm2', 1 - (e.embedding <=> %s::vector) AS sim "
                    "FROM place_embeddings e JOIN place_catalog c ON c.tenant_id=e.tenant_id AND c.content_id=e.content_id "
                    "WHERE e.tenant_id = ANY(%s) AND e.model=%s AND c.raw_json->>'lclsSystm2' IS NOT NULL "
                    "ORDER BY e.embedding <=> %s::vector LIMIT %s", (literal, tenants, model_name(), literal, KNN_K))
        rows = cur.fetchall()
    if not rows:
        return None
    votes: Counter[tuple[str, str]] = Counter()
    sims: dict[tuple[str, str], list[float]] = {}
    for l1, l2, sim in rows:
        votes[(l1, l2)] += 1
        sims.setdefault((l1, l2), []).append(float(sim))
    (l1, l2), count = votes.most_common(1)[0]
    share = count / len(rows)
    similarity = sum(sims[(l1, l2)]) / len(sims[(l1, l2)])
    if share < MIN_SHARE or similarity < MIN_SIMILARITY:
        return None
    return {"lcls1": l1, "lcls2": l2, "share": round(share, 2), "similarity": round(similarity, 2), "voters": len(rows)}


__all__ = ["DIM", "Embedder", "catalog_text", "centroid", "cosine", "estimate_class", "fill_catalog", "missing", "model_name", "ollama_embedder", "vectors_of"]
