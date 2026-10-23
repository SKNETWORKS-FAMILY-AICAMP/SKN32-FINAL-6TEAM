# -*- coding: utf-8 -*-
"""활동 CSV 의 **사실 칸**(연락처 · 홈페이지 · 요금 · 예약 · 연령 …)을 장소 목록(`place_catalog.raw_json`)에 맞춘다. `[2026-10-15]`

    python -m scripts.activity.load_csv_facts <csv>                  # 세어 보기만(기본)
    python -m scripts.activity.load_csv_facts <csv> --apply          # 백업하고 적는다
    python -m scripts.activity.load_csv_facts --restore <백업 폴더>   # 되돌린다

★왜: `raw_json` 에는 예전에 통째로 넣은 CSV 한 줄이 **그때 값 그대로** 남아 있다. 그 뒤 TourAPI 상세 수집 · 사람 · Claude 가
  채운 값(db_column.md)이 DB 에 없었다(2026-10-15 사용자 「2번 진행」). 요일별 영업시간은 `enrich_place_catalog_from_csv` 가
  `catalog_hours` 로 옮기고, 이 스크립트는 `raw_json` 의 **글 칸**을 맞춘다(영업시간 · 휴무 글 포함 — 대안 후보 거르기가 읽는다).
★옮기는 칸: `FACT_KEYS` + `field_sources`(칸별 출처 — 화면이 사람 값을 「ⓒ한국관광공사」로 말하지 않게 `place_info` 가 읽는다).
  CSV 에 값이 있으면 그 값, **CSV 가 빈 칸이면 `raw_json` 에서 그 키를 지운다**(옛 값이 남아 사실처럼 보이지 않게).
★안 옮기는 것: 소개글(`overview`) · 체험 안내(`experience_guide`) — 남의 글이라 저장하지 않는다(2026-09-28 결정).
  이미 들어 있는 옛 소개글은 이 스크립트가 건드리지 않는다. 식별자 · 좌표 · 분류도 건드리지 않는다.
★대상: CSV 의 관광공사 행(`tour_api`)과 브랜드 매장 행(`oliveyoung` 등) 중 **DB 목록에 이미 있는 행**만. 새 행은 넣지 않는다.
★재실행 안전 — 같은 CSV 면 두 번째는 바뀌는 것이 0 이다. `--apply` 는 백업 없이 돌지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg.types.json import Json

from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_BY_PREFIX = {"OY": "oliveyoung", "DS": "daiso", "AB": "artbox", "MS": "musinsa"}
#: CSV 와 같게 맞추는 `raw_json` 키 — db_column.md 의 사람이 채울 수 있는 칸 + 시군구
#: ★영업시간 · 휴무 **글**도 넣는다 — 요일별 칸(`catalog_hours`)과 별개로 대안 후보 거르기(`db_search/place_candidates.py` →
#:   `alternatives.open_at` · `closed_on`)가 `raw_json` 의 글을 읽는다. 처음 판은 빼서 목동아이스링크가 거기서 「모름」이었다(2026-10-15).
FACT_KEYS = ("business_hours", "closed_days", "tel", "homepage", "fee", "reservation_info", "spendtime", "capacity", "pet",
             "age_limit", "lDongSignguCd")


def _source(content_id: str) -> str | None:
    return "tour_api" if content_id.isdigit() else SOURCE_BY_PREFIX.get(content_id[:2])


def _sources(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    value = json.loads(text)                      # ★형식이 틀리면 여기서 멈춘다(조용히 넘기지 않는다)
    if not isinstance(value, dict):
        raise ValueError(f"field_sources 가 {{컬럼: 출처}} 모양이 아니다: {text[:80]}")
    return value or None


def patch_for(row: dict[str, str], raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """CSV 한 줄 → (`raw_json` 에 덮을 키, 지울 키). 이미 같으면 둘 다 비어 있다."""
    put: dict[str, Any] = {}
    drop: list[str] = []
    for key in FACT_KEYS:
        value = (row.get(key) or "").strip()
        if value:
            if raw.get(key) != value:
                put[key] = value
        elif key in raw:
            drop.append(key)
    sources = _sources(row.get("field_sources") or "")
    current = raw.get("field_sources")
    if isinstance(current, str):
        current = _sources(current)
    if sources:
        if current != sources:
            put["field_sources"] = sources
    elif "field_sources" in raw:
        drop.append("field_sources")
    return put, drop


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def plan(conn, tenant: str, rows: list[dict[str, str]]) -> tuple[list[tuple[str, str, dict, list]], Counter]:
    stats: Counter = Counter()
    by_source: dict[str, list[str]] = {}
    for row in rows:
        cid = row["contentid"].strip()
        source = _source(cid)
        if source:
            by_source.setdefault(source, []).append(cid)
    raws: dict[tuple[str, str], dict[str, Any]] = {}
    with conn.cursor() as cur:
        for source, ids in by_source.items():
            cur.execute("SELECT content_id, raw_json FROM place_catalog WHERE tenant_id=%s AND source=%s AND content_id = ANY(%s)",
                        (tenant, source, ids))
            raws.update({(source, cid): raw or {} for cid, raw in cur.fetchall()})
    changes = []
    for row in rows:
        cid = row["contentid"].strip()
        source = _source(cid)
        if not source:
            stats["skip_unknown_source"] += 1
            continue
        if (source, cid) not in raws:
            stats["skip_not_in_catalog"] += 1
            continue
        put, drop = patch_for(row, raws[(source, cid)])
        if not put and not drop:
            stats["same"] += 1
            continue
        stats["rows_changed"] += 1
        for key in put:
            stats[f"put:{key}"] += 1
        for key in drop:
            stats[f"drop:{key}"] += 1
        changes.append((source, cid, put, drop))
    return changes, stats


def _backup_dir() -> Path:
    stem = REPO_ROOT / "_backup" / f"{datetime.now():%Y-%m-%d_%H%M}_place_catalog_facts"
    path, count = stem, 1
    while path.exists():
        count += 1
        path = Path(f"{stem}_{count}")
    path.mkdir(parents=True)
    return path


def apply(conn, tenant: str, changes: list[tuple[str, str, dict, list]]) -> Path:
    backup = _backup_dir()
    with conn.transaction(), conn.cursor() as cur:
        lines = []
        for source, cid, _put, _drop in changes:
            cur.execute("SELECT raw_json FROM place_catalog WHERE tenant_id=%s AND source=%s AND content_id=%s", (tenant, source, cid))
            lines.append(json.dumps({"tenant_id": tenant, "source": source, "content_id": cid, "raw_json": cur.fetchone()[0]},
                                    ensure_ascii=False))
        (backup / "place_catalog_raw_json.jsonl").write_text("\n".join(lines), encoding="utf-8")   # ★바꾸기 전에 먼저 쓴다
        for source, cid, put, drop in changes:
            cur.execute("UPDATE place_catalog SET raw_json = (raw_json - %s::text[]) || %s::jsonb "
                        "WHERE tenant_id=%s AND source=%s AND content_id=%s", (drop, Json(put), tenant, source, cid))
    return backup


def restore(conn, folder: Path) -> int:
    done = 0
    with conn.transaction(), conn.cursor() as cur:
        for line in (folder / "place_catalog_raw_json.jsonl").read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            cur.execute("UPDATE place_catalog SET raw_json=%s WHERE tenant_id=%s AND source=%s AND content_id=%s",
                        (Json(item["raw_json"]), item["tenant_id"], item["source"], item["content_id"]))
            done += 1
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", type=Path, nargs="?")
    ap.add_argument("--tenant", default=None)
    ap.add_argument("--apply", action="store_true", help="백업하고 DB 에 적는다(없으면 세어 보기만)")
    ap.add_argument("--restore", type=Path, default=None, help="이 백업 폴더로 되돌린다")
    args = ap.parse_args(argv)
    tenant = args.tenant or get_settings().tenant_id
    with get_connection() as conn:
        if args.restore:
            print(f"되돌림 {restore(conn, args.restore)}행")
            return 0
        if not args.csv:
            ap.error("csv 경로가 필요하다")
        changes, stats = plan(conn, tenant, read_csv(args.csv))
        print(dict(sorted(stats.items())))
        if not args.apply:
            print("--apply 가 없어 DB 에 쓰지 않았다")
            return 0
        print(f"적음 {len(changes)}행 · 백업 {apply(conn, tenant, changes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
