# -*- coding: utf-8 -*-
"""취향 추천 — 후보의 **셋째 단**(`basis: "taste"`). `[2026-10-07 사용자 결정 — uiux 전달]`

사용자: 「3단 취향 추천까지 진행 — 대안 고르기는 규칙(분류 나무 · 영업시간 · 거리 · 여유) + 임베딩, 이유 문장만 모델이 확인된 값으로 쓴다」.

★무엇을 「취향」으로 보나: 사용자가 **이 여행에 담은 다른 활동**의 분류다. 일정에 공원 · 둘레길이 많으면 그 갈래가 취향이고, 한옥마을 · 궁궐이 많으면 그쪽이다.
  짐작이 아니라 **센 값**이다 — 이유 문장에는 일정에 실제로 있는 장소 이름과 개수만 쓴다(「일정에 담은 「북촌한옥마을」 · 「창덕궁」과 같은 분류의 곳이에요」).
★쇼핑(SH) · 음식(FD) · 숙박(AC) 가지는 취향 계산에서 뺀다(끼니 · 잠자리는 취향이 아니라 일과이고, 쇼핑은 후보에서 뺀다는 사용자 지시가 있다).
★셋째 단은 **앞 두 단(같은 종류 → 비슷한 경험)이 모자랄 때만** 채운다 — 그래서 취향이 같은 종류를 밀어내지 않는다.
★임베딩(`place_embeddings` 가 채워져 있을 때만): 취향 후보를 **일정에 담은 장소들의 평균 벡터와 가까운 순**으로 다시 줄 세운다. 임베딩이 없으면 규칙 순서(센 분류 → 가까운 순) 그대로다 —
  조용히 다른 방식으로 바꾸지 않고 후보의 `taste.ranked_by` 에 어느 쪽으로 줄 세웠는지 적는다(`count` · `embedding`).
"""
from __future__ import annotations

from collections import Counter
from typing import Any

#: 취향 계산 · 취향 후보에서 뺀 대분류 — 쇼핑 · 음식 · 숙박
NOT_TASTE_LCLS1 = frozenset({"SH", "FD", "AC"})
TOP_CLASSES = 3


def profile(conn, tenants: list[str], items: list[dict[str, Any]], skip_item_id: str | None) -> dict[str, Any]:
    """이 여행의 다른 활동이 가진 분류를 센다 — `{classes: [{lcls2, count, titles:[…]}], items_seen}`. 분류를 모르는 활동은 센 대상에서 빠진다(`items_seen` 은 분류를 안 활동 수).

    장소의 관광공사 번호(`content_id`)로 목록 항목을 찾고, 없으면 **이름이 같은 목록 항목**에서 찾는다(이름이 여러 중분류에 걸치면 모른다 — 지어내지 않는다)."""
    mine = [i for i in items if i.get("kind") == "activity" and i.get("place") and i.get("id") != skip_item_id]
    if not mine:
        return {"classes": [], "items_seen": 0}
    ids = sorted({str(i["place"]["content_id"]) for i in mine if i["place"].get("content_id")})
    names = sorted({(i["place"].get("name") or "").strip() for i in mine if (i["place"].get("name") or "").strip()})
    by_id: dict[str, tuple[str, str]] = {}
    by_name: dict[str, set[tuple[str, str]]] = {}
    name_ids: dict[str, set[str]] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT content_id, title, raw_json->>'lclsSystm1', raw_json->>'lclsSystm2' FROM place_catalog "
                    "WHERE tenant_id = ANY(%s) AND source='tour_api' AND (content_id = ANY(%s) OR title = ANY(%s))", (tenants, ids, names))
        for content_id, title, l1, l2 in cur.fetchall():
            if l1 and l2:
                by_id[str(content_id)] = (l1, l2)
                by_name.setdefault(title, set()).add((l1, l2))
                name_ids.setdefault(title, set()).add(str(content_id))
    counts: Counter[str] = Counter()
    titles: dict[str, list[str]] = {}
    liked_ids: list[str] = []                                           # 취향으로 센 장소의 목록 번호 — 임베딩 평균을 낸다
    seen = 0
    for item in mine:
        place = item["place"]
        found = by_id.get(str(place.get("content_id"))) if place.get("content_id") else None
        liked = str(place["content_id"]) if found is not None else None
        if found is None:
            options = by_name.get((place.get("name") or "").strip(), set())
            found = next(iter(options)) if len(options) == 1 else None
            ids_by_name = name_ids.get((place.get("name") or "").strip(), set())
            liked = next(iter(ids_by_name)) if found is not None and len(ids_by_name) == 1 else None
        if found is None:
            continue
        seen += 1
        l1, l2 = found
        if l1 in NOT_TASTE_LCLS1:
            continue
        counts[l2] += 1
        if liked:
            liked_ids.append(liked)
        titles.setdefault(l2, [])
        name = (place.get("name") or "").strip()
        if name and name not in titles[l2]:
            titles[l2].append(name)
    order = {l2: n for n, l2 in enumerate(counts)}                      # 같은 개수면 일정에 먼저 나온 갈래가 앞
    ranked = sorted(counts, key=lambda l2: (-counts[l2], order[l2]))[:TOP_CLASSES]
    return {"classes": [{"lcls2": l2, "count": counts[l2], "titles": titles[l2][:2]} for l2 in ranked], "items_seen": seen, "liked_ids": liked_ids}


def places(conn, tenant_id: str, ref: tuple[float, float], taste: dict[str, Any], now, *, exclude_lcls2: set[str] | None = None,
           limit: int = 12, radius_m: float = 3000) -> list[dict[str, Any]]:
    """취향 갈래에 드는 가까운 곳 — 후보마다 `basis: "taste"` · 근거(`taste` = {with: 일정의 장소 이름, count, ranked_by}). `exclude_lcls2` 는 앞 단이 이미 훑은 중분류.

    ★순서: 임베딩이 있으면 일정 장소들의 평균 벡터와 가까운 순, 없으면 센 갈래 먼저 → 가까운 순(`catalog_pool.nearby_in_classes` 가 가까운 순으로 준다)."""
    from app.domains.travel_ops.components.places import catalog_pool
    from app.domains.travel_ops.components.intake import candidates as base

    wanted = [c for c in taste["classes"] if c["lcls2"] not in (exclude_lcls2 or set())]
    if not wanted:
        return []
    by_class = {c["lcls2"]: c for c in wanted}
    cands = catalog_pool.nearby_in_classes(conn, tenant_id, latitude=ref[0], longitude=ref[1], radius_m=radius_m,
                                           lcls2=list(by_class), exclude_names=set(), limit=limit)
    catalog_pool.reuse_hours(conn, tenant_id, cands, now)
    out = []
    for place, cand in zip(base._tour_places(cands), cands):
        l2 = (cand.attributes.get("lcls") or [None, None, None])[1]
        evidence = by_class.get(l2) or wanted[0]
        out.append({**place, "basis": "taste", "taste": {"with": evidence["titles"], "count": evidence["count"], "ranked_by": "count", "lcls2": l2}})
    rank = {c["lcls2"]: n for n, c in enumerate(wanted)}
    out.sort(key=lambda p: rank.get(p["taste"]["lcls2"], 99))          # 센 갈래 먼저 — 같은 갈래 안은 가까운 순(들어온 순서) 그대로
    return _rerank_by_embedding(conn, tenant_id, out, taste.get("liked_ids") or [])


def _rerank_by_embedding(conn, tenant_id: str, out: list[dict[str, Any]], liked_ids: list[str]) -> list[dict[str, Any]]:
    """저장된 임베딩이 **후보 전부와 일정의 장소(하나 이상)** 에 있으면 일정 장소들의 평균 벡터와 가까운 순으로 다시 줄 세운다(`ranked_by: "embedding"` + `score`).
    하나라도 모자라면 규칙 순서 그대로 두고 `ranked_by: "count"` 로 적는다 — 섞어 쓰지 않는다. 임베딩 표가 없는 DB 면 규칙 순서(`count`)."""
    from . import embeddings
    from app.domains.travel_ops.components.places.catalog_pool import _catalog_tenants

    if not out or not liked_ids:
        return out
    tenants = _catalog_tenants(tenant_id)
    try:
        with conn.transaction():
            liked = embeddings.vectors_of(conn, tenants, liked_ids)
            cand_ids = [p.get("content_id") for p in out if p.get("content_id")]
            vectors = embeddings.vectors_of(conn, tenants, cand_ids)
    except Exception as exc:                                  # noqa: BLE001 — 임베딩 표 · 확장이 없는 DB(시험 · 다른 조립)면 규칙 순서
        if type(exc).__name__ not in ("UndefinedTable", "UndefinedObject", "UndefinedFunction", "FeatureNotSupported"):
            raise
        return out
    mean = embeddings.centroid(list(liked.values()))
    if mean is None or len(vectors) < len(out) or any(not p.get("content_id") for p in out):
        return out
    scored = [(embeddings.cosine(mean, vectors[p["content_id"]]), p) for p in out]
    scored.sort(key=lambda sp: -sp[0])
    return [{**p, "taste": {**p["taste"], "ranked_by": "embedding", "score": round(score, 2)}} for score, p in scored]


def reason_head(taste: dict[str, Any]) -> str:
    """이유 문장의 머리 — 일정에 있는 장소 이름과 개수만 쓴다(짐작한 분위기 · 느낌을 쓰지 않는다)."""
    titles = [f"「{t}」" for t in taste.get("with") or []]
    count = int(taste.get("count") or 0)
    if titles and count > len(titles):
        return f"일정에 담은 {' · '.join(titles)} 등 {count}곳과 같은 분류의 곳이에요"
    if titles:
        return f"일정에 담은 {' · '.join(titles)}과 같은 분류의 곳이에요"
    return "일정에 담은 곳들과 같은 분류의 곳이에요"


__all__ = ["NOT_TASTE_LCLS1", "TOP_CLASSES", "places", "profile", "reason_head"]
