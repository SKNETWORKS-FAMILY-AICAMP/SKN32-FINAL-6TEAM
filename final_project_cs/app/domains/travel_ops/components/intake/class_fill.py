# -*- coding: utf-8 -*-
"""분류가 비어 있는 장소의 분류를 **한 번 채워 저장**한다. `[2026-10-07 사용자 결정 — uiux 전달]`

☆왜. 우리 장소 표(`places`)의 활동 행은 분류가 대개 비어 있다(522곳 중 194곳만 — 로컬 개발 DB 실측). 분류를 모르면 후보 고르기의 **같은 종류**(분류 나무)를 못 쓰고 쇼핑만 빼는 거친 길로 간다.
★두 길 — 믿을 수 있는 쪽이 먼저다:
  ①**이름 일치**(`name_match`): 이름이 같은 목록 항목이 있고 분류가 하나로 모이면 그 분류를 쓴다(소분류까지, 갈리면 갈린 단계 앞까지).
  ②**임베딩 투표**(`estimated`): 이름이 목록에 없으면 가장 닮은 목록 장소들의 중분류 투표(`embeddings.estimate_class`)로 **짐작**한다. 투표가 갈리거나 닮은 정도가 낮으면 모른다고 둔다.
★저장 위치: `places.attributes.inferred_class` = `{"lcls": [대, 중, 소|null], "grade": "name_match"|"estimated", "method", "share"?, "similarity"?}` — 목록의 분류(`source_content_type_id`)를 **덮지 않는다**
  (그 칸이 이미 있는 행은 대상이 아니다). 후보 고르기는 이 값을 읽되(`candidates._original_class`) **`estimated` 이면 이유 문장에 「관광공사 분류」라고 쓰지 않는다**.
★기본은 세기만 한다(`dry_run`) — 쓰기는 `--apply` 를 줄 때만(`scripts/fill_place_classes.py`).
"""
from __future__ import annotations

from typing import Any

from psycopg.types.json import Json

from . import embeddings

#: 이 단계 값이 같은 **이름 일치**가 하나로 모이는 분류만 쓴다 — 같은 이름이 쇼핑과 관광지에 걸치면(대분류가 갈리면) 모른다
def _common(rows: list[tuple[str | None, str | None, str | None]]) -> list[str | None] | None:
    base = list(rows[0])
    for row in rows[1:]:
        for n in range(3):
            if base[n] != row[n]:
                for m in range(n, 3):
                    base[m] = None
                break
    return base if base[0] else None


def _targets(conn, tenants: list[str], limit: int | None) -> list[tuple[Any, str, str]]:
    """분류를 채울 행 — 활동 · 공용(여행 전용 아님) · 목록 분류가 없고 · 아직 추정도 안 한 곳 · 이 테넌트들의 것. `(place_id, tenant_id, name)`."""
    with conn.cursor() as cur:
        cur.execute("SELECT place_id, tenant_id, name FROM places WHERE tenant_id = ANY(%s) AND kind='activity' AND trip_scope IS NULL "
                    "AND COALESCE(attributes->>'source_content_type_id','') = '' AND attributes->'inferred_class' IS NULL "
                    "AND COALESCE(name,'') <> '' ORDER BY tenant_id, place_id" + (" LIMIT %s" if limit else ""),
                    (tenants, limit) if limit else (tenants,))
        return cur.fetchall()


def fill_places(conn, tenants: list[str], embed: embeddings.Embedder | None, *, limit: int | None = None, dry_run: bool = True) -> dict[str, Any]:
    """분류를 채운다 — 센 값과 결정 표본(`decisions`: `(이름, 분류, 등급)`)을 돌려준다. `embed` 가 None 이면 이름 일치만 한다(`unmatched` 로 센다)."""
    targets = _targets(conn, tenants, limit)
    out: dict[str, Any] = {"targets": len(targets), "name_match": 0, "estimated": 0, "unknown": 0, "unmatched": 0, "written": 0, "decisions": []}
    decided: dict[Any, dict[str, Any]] = {}
    pending: list[tuple[Any, str, str]] = []
    with conn.cursor() as cur:
        for place_id, tenant_id, name in targets:
            cur.execute("SELECT raw_json->>'lclsSystm1', raw_json->>'lclsSystm2', raw_json->>'lclsSystm3' FROM place_catalog "
                        "WHERE tenant_id = ANY(%s) AND source='tour_api' AND title=%s", (tenants, name.strip()))
            rows = cur.fetchall()
            common = _common(rows) if rows else None
            if common:
                decided[place_id] = {"lcls": common, "grade": "name_match", "method": "catalog_title"}
                out["name_match"] += 1
            else:
                pending.append((place_id, tenant_id, name))
    if pending and embed is not None:
        vectors = embed([name.strip() for _p, _t, name in pending])
        for (place_id, _tenant, name), vector in zip(pending, vectors):
            guess = embeddings.estimate_class(conn, tenants, vector)
            if guess is None:
                out["unknown"] += 1
                continue
            decided[place_id] = {"lcls": [guess["lcls1"], guess["lcls2"], None], "grade": "estimated", "method": "embedding_knn",
                                 "share": guess["share"], "similarity": guess["similarity"], "model": embeddings.model_name()}
            out["estimated"] += 1
    else:
        out["unmatched"] = len(pending)
    names = {place_id: name for place_id, _t, name in targets}
    out["decisions"] = [(names[pid], d["lcls"], d["grade"]) for pid, d in list(decided.items())[:20]]
    if not dry_run:
        with conn.transaction(), conn.cursor() as cur:
            for place_id, value in decided.items():
                cur.execute("UPDATE places SET attributes = attributes || jsonb_build_object('inferred_class', %s::jsonb) WHERE place_id=%s",
                            (Json(value), place_id))
                out["written"] += 1
    return out


def stored_class(conn, place_id: Any) -> dict[str, Any] | None:
    """`places.attributes.inferred_class` — 없으면 None."""
    from uuid import UUID

    try:
        key = UUID(str(place_id))
    except (ValueError, TypeError):                          # 번호 모양이 아니면 모른다
        return None
    with conn.cursor() as cur:
        cur.execute("SELECT attributes->'inferred_class' FROM places WHERE place_id=%s", (key,))
        row = cur.fetchone()
    return row[0] if row and row[0] else None


__all__ = ["fill_places", "stored_class"]
