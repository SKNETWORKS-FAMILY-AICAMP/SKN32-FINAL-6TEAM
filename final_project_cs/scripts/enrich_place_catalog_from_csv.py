# -*- coding: utf-8 -*-
"""활동 팀 CSV → 우리 장소 목록(`place_catalog`)·영업시간 표(`catalog_hours`) **보강**. `[2026-10-01]`

    python -m scripts.enrich_place_catalog_from_csv <csv>                 # 세어 보기만(기본)
    python -m scripts.enrich_place_catalog_from_csv <csv> --apply         # 백업하고 적는다
    python -m scripts.enrich_place_catalog_from_csv --restore <백업 폴더>   # 되돌린다

★무엇을 옮기나(조직 develop 의 `activity_total_data.csv` 를 우리 장소 목록과 관광공사 id 로 맞춘다):
  1. **브랜드**(올리브영·다이소 …) — `place_catalog.raw_json.brand` 에 **덧붙인다**(기존 키는 그대로).
     브랜드 매장 행(id 접두 OY·DS·AB·MS)은 우리 목록의 같은 매장(이름·위치 150m 안이 같을 때만)에 붙인다.
  2. **영업시간·휴무** 글 → 요일별 칸(`activity/hours_text.read_week`, 모델 호출 없음) → `catalog_hours`.
     ★이미 요일별 칸이 있는 행(새벽 작업이 읽은 것)은 **건드리지 않는다.** 칸을 못 만든 글은 넣지 않는다(새벽 작업이 읽는다).
★안 옮기는 것: 소개글(`overview`) — 관광공사 소개글은 저장하지 않기로 했다(2026-09-28 결정). 요금(`fee`) · 새 매장 행도 이번엔 안 넣는다.
★팀 적재 스크립트(`load_place_catalog_csv`)를 그대로 쓰지 않은 까닭: CSV 한 행 전체(소개글 포함)를 `raw_json` 에 넣고 같은 출처면
  기존 `raw_json` 을 통째로 바꾼다.
★재실행 안전 — 같은 CSV 를 다시 돌려도 같은 값이다. `--apply` 는 백업 없이 돌지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg.types.json import Json

from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.activity.hours_text import read_week

REPO_ROOT = Path(__file__).resolve().parents[1]
BRAND_ID_PREFIXES = ("OY", "DS", "AB", "MS")
MATCH_M = 150          # 브랜드 매장 행을 우리 목록의 같은 매장으로 보는 거리 — ★우리가 고른 값


def _norm(title: str) -> str:
    return re.sub(r"[\s()·\-]|점$", "", title or "")


def _meters(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    return math.hypot((a_lat - b_lat) * 111_000, (a_lon - b_lon) * 88_000)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_plan(rows: list[dict[str, str]], catalog: list[tuple[str, str, float | None, float | None]]) -> dict[str, Any]:
    """CSV 와 목록(content_id, title, lat, lon)을 맞춰 무엇을 적을지 정한다. DB 를 부르지 않는다."""
    in_catalog = {cid: (title, lat, lon) for cid, title, lat, lon in catalog}
    by_norm: dict[str, list[str]] = {}
    for cid, title, _lat, _lon in catalog:
        by_norm.setdefault(_norm(title), []).append(cid)
    stats: Counter = Counter()
    plan: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = (row.get("contentid") or "").strip()
        if cid.isdigit():
            if cid not in in_catalog:
                stats["csv_only_tourapi"] += 1
                continue
            entry = plan.setdefault(cid, {})
            if (row.get("brand") or "").strip():
                entry["brand"] = row["brand"].strip()
            if (row.get("business_hours") or "").strip() or (row.get("closed_days") or "").strip():
                entry["text"] = (row.get("business_hours") or "").strip(), (row.get("closed_days") or "").strip()
            continue
        if not cid[:2] in BRAND_ID_PREFIXES:
            stats["skipped_other_id"] += 1
            continue
        # 브랜드 매장 행 — 같은 이름·150m 안의 우리 행 하나에만 붙인다
        try:
            lat, lon = float(row["mapy"]), float(row["mapx"])
        except (KeyError, ValueError):
            stats["brand_no_coordinate"] += 1
            continue
        twins = [c for c in by_norm.get(_norm(row.get("title") or ""), [])
                 if in_catalog[c][1] is not None and in_catalog[c][2] is not None
                 and _meters(lat, lon, float(in_catalog[c][1]), float(in_catalog[c][2])) <= MATCH_M]
        if len(twins) != 1:
            stats["brand_unmatched" if not twins else "brand_ambiguous"] += 1
            continue
        stats["brand_matched"] += 1
        entry = plan.setdefault(twins[0], {})
        if (row.get("brand") or "").strip():
            entry.setdefault("brand", row["brand"].strip())
        if (row.get("business_hours") or "").strip() or (row.get("closed_days") or "").strip():
            entry.setdefault("text", ((row.get("business_hours") or "").strip(), (row.get("closed_days") or "").strip()))
    return {"plan": plan, "stats": stats}


def _backup_dir(tag: str) -> Path:
    stem = REPO_ROOT / "_backup" / f"{datetime.now():%Y-%m-%d_%H%M}_{tag}"
    path, count = stem, 1
    while path.exists():                      # ★같은 분에 또 돌려도 앞 백업을 덮지 않는다
        count += 1
        path = Path(f"{stem}_{count}")
    path.mkdir(parents=True)
    return path


def apply(tenant: str, plan: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ids = list(plan)
    out: dict[str, Any] = Counter()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT content_id, raw_json, source_modified_at FROM place_catalog "
                    "WHERE tenant_id=%s AND source='tour_api' AND content_id = ANY(%s)", (tenant, ids))
        catalog = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        cur.execute("SELECT content_id, hours_week, hours_read, hours_origin, phone, source_modified_at, read_at, "
                    "content_type_id FROM catalog_hours WHERE tenant_id=%s AND source='tour_api' AND content_id = ANY(%s)",
                    (tenant, ids))
        hours_rows = {r[0]: r for r in cur.fetchall()}
        # ★백업 먼저 — 바꾸기 전 값을 파일로
        backup = _backup_dir("place_catalog_enrich")
        (backup / "place_catalog_raw_json.jsonl").write_text(
            "\n".join(json.dumps({"content_id": cid, "raw_json": raw}, ensure_ascii=False) for cid, (raw, _m) in catalog.items()),
            encoding="utf-8")
        (backup / "catalog_hours_before.jsonl").write_text(
            "\n".join(json.dumps({"content_id": r[0], "hours_week": r[1], "hours_read": r[2], "hours_origin": r[3],
                                  "phone": r[4], "source_modified_at": r[5], "read_at": r[6].isoformat(),
                                  "content_type_id": r[7]}, ensure_ascii=False) for r in hours_rows.values()),
            encoding="utf-8")
        inserted: list[str] = []
        now = datetime.now().astimezone()
        for cid, entry in plan.items():
            if cid not in catalog:
                continue
            raw, modified = catalog[cid]
            if entry.get("brand") and not (raw or {}).get("brand"):
                cur.execute("UPDATE place_catalog SET raw_json = raw_json || jsonb_build_object('brand', %s::text) "
                            "WHERE tenant_id=%s AND source='tour_api' AND content_id=%s", (entry["brand"], tenant, cid))
                out["brand_written"] += 1
            if "text" in entry:
                existing = hours_rows.get(cid)
                if existing is not None and existing[1]:
                    out["hours_kept_existing"] += 1
                    continue
                usetime, restdate = entry["text"]
                read = read_week(usetime, restdate)
                if read is None:
                    out["hours_unreadable"] += 1
                    continue
                record = {**read.as_record(source="activity_csv", read_at=now.isoformat()), "method": "csv_rule",
                          "note": "조직 develop 활동 CSV 의 관광공사 원문 — 규칙으로 읽음(모델 호출 없음)"}
                cur.execute(
                    "INSERT INTO catalog_hours (tenant_id, source, content_id, content_type_id, hours_week, hours_read, "
                    "hours_origin, source_modified_at, read_at) "
                    "SELECT %s,'tour_api',pc.content_id,pc.content_type_id,%s,%s,%s,pc.source_modified_at,%s "
                    "FROM place_catalog pc WHERE pc.tenant_id=%s AND pc.source='tour_api' AND pc.content_id=%s "
                    "ON CONFLICT (tenant_id, source, content_id) DO UPDATE SET hours_week=EXCLUDED.hours_week, "
                    "hours_read=EXCLUDED.hours_read, hours_origin=EXCLUDED.hours_origin, "
                    "source_modified_at=EXCLUDED.source_modified_at, read_at=EXCLUDED.read_at",
                    (tenant, Json(read.week), Json(record), Json({"usetime": usetime, "restdate": restdate}), now,
                     tenant, cid))
                if existing is None:
                    inserted.append(cid)
                out["hours_written"] += 1
        (backup / "catalog_hours_inserted.json").write_text(json.dumps(inserted), encoding="utf-8")
    out["backup"] = str(backup)
    return dict(out)


def restore(folder: Path, tenant: str) -> dict[str, int]:
    done: Counter = Counter()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for line in (folder / "place_catalog_raw_json.jsonl").read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            cur.execute("UPDATE place_catalog SET raw_json=%s WHERE tenant_id=%s AND source='tour_api' AND content_id=%s",
                        (Json(item["raw_json"]), tenant, item["content_id"]))
            done["raw_json_restored"] += 1
        inserted = json.loads((folder / "catalog_hours_inserted.json").read_text(encoding="utf-8"))
        if inserted:
            cur.execute("DELETE FROM catalog_hours WHERE tenant_id=%s AND source='tour_api' AND content_id = ANY(%s)",
                        (tenant, inserted))
            done["hours_deleted"] = len(inserted)
        before = (folder / "catalog_hours_before.jsonl").read_text(encoding="utf-8").splitlines()
        for line in filter(None, before):
            item = json.loads(line)
            cur.execute(
                "UPDATE catalog_hours SET hours_week=%s, hours_read=%s, hours_origin=%s, phone=%s, source_modified_at=%s, "
                "read_at=%s WHERE tenant_id=%s AND source='tour_api' AND content_id=%s",
                (Json(item["hours_week"]) if item["hours_week"] is not None else None, Json(item["hours_read"]),
                 Json(item["hours_origin"]) if item["hours_origin"] is not None else None, item["phone"],
                 item["source_modified_at"], item["read_at"], tenant, item["content_id"]))
            done["hours_restored"] += 1
    return dict(done)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", type=Path, nargs="?")
    ap.add_argument("--tenant", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", type=Path)
    args = ap.parse_args(argv)
    tenant = args.tenant or get_settings().tenant_id
    if args.restore:
        print(restore(args.restore, tenant))
        return 0
    if args.csv is None:
        ap.error("CSV 경로가 필요하다")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT content_id, title, latitude, longitude FROM place_catalog "
                    "WHERE tenant_id=%s AND source='tour_api'", (tenant,))
        catalog = [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]
    built = build_plan(read_csv(args.csv), catalog)
    plan, stats = built["plan"], built["stats"]
    week_ok = sum(1 for e in plan.values() if "text" in e and read_week(*e["text"]) is not None)
    print(f"목록 {len(catalog)}행 · 붙일 행 {len(plan)} (브랜드 {sum(1 for e in plan.values() if e.get('brand'))}, "
          f"영업시간 글 {sum(1 for e in plan.values() if 'text' in e)} → 요일별 칸으로 읽힘 {week_ok})")
    print(f"브랜드 매장 행 맞춤: 같은 매장 {stats['brand_matched']} · 못 찾음 {stats['brand_unmatched']} · 여럿 {stats['brand_ambiguous']}"
          f" · 우리 목록에 없는 관광공사 행 {stats['csv_only_tourapi']}")
    if not args.apply:
        print("--apply 가 없어 DB 에 쓰지 않았다")
        return 0
    print(apply(tenant, plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
