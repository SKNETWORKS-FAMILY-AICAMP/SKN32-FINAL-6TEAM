# -*- coding: utf-8 -*-
"""후보 장소 CSV → `place_catalog` 수동 적재. **재실행 안전**(upsert).

대상 CSV:
    scripts/activities_candidates_seoul_enriched.csv
    — 서울 Activity 후보 장소 805건(TourAPI areaBasedList2 + detailCommon2 보강).
      FD(음식)·AC(숙박)·EV(행사·이벤트)는 Activity 담당 범위 밖이므로 --exclude-codes로 제외한다.

사용:
    python -m scripts.load_place_catalog_csv scripts/activities_candidates_seoul_enriched.csv \
        --exclude-codes FD AC EV --dry-run   # 넣지 않고 검사만
    python -m scripts.load_place_catalog_csv scripts/activities_candidates_seoul_enriched.csv \
        --exclude-codes FD AC EV             # 적재 (765건)

★키는 `(tenant_id, source, content_id)` 다(011). 같은 CSV 를 다시 돌리면 같은 행을
  갱신할 뿐 늘지 않는다. CSV 의 `contentid` 는 TourAPI 식별자이므로 기본 `source` 는
  `tour_api` 다 — `places.source_name='tour_api'` 와 같은 축이고, 나중에
  `PlaceCatalogSync` 가 같은 행을 이어서 갱신한다(중복 행이 생기지 않는다).
  ※그때 `raw_json` 은 API 응답으로 통째로 바뀐다. CSV 에만 있는 보강 컬럼
  (overview·business_hours·closed_days·fee 등)을 잃고 싶지 않으면 `--source manual`
  로 넣는다(대신 동기화가 만든 행과 별개 행이 된다).

★좌표를 지어내지 않는다. 서울 범위 밖 좌표(공급자의 자리표시값
  117.9925662504 / 19.69442748 등)는 **NULL(모름)** 로 넣는다. 원본 값은
  `raw_json` 에 그대로 남고 `raw_json._load.coord_nulled` 로 표시한다.
  `source_modified_at` 도 CSV 에 없으므로 NULL 이다 — 우리가 받은 시각(`fetched_at`)과
  섞지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from app.infrastructure.travel.tour_api import LARGE_CLASS_NAMES

#: 서울 경계 상자(여유 포함). 밖이면 좌표를 신뢰하지 않는다.
SEOUL_LON = (126.70, 127.30)
SEOUL_LAT = (37.40, 37.75)

#: 서울 TourAPI areaCode. CSV 에는 시군구코드만 있어 카탈로그 동기화와 맞추려고 고정한다.
DEFAULT_AREA_CODE = "1"


def _number(value: str) -> float | None:
    try:
        return float(str(value or "").strip())
    except (TypeError, ValueError):
        return None


def to_row(src: dict[str, str], *, area_code: str, csv_name: str) -> dict[str, Any]:
    lon, lat = _number(src.get("mapx", "")), _number(src.get("mapy", ""))
    in_seoul = (lon is not None and lat is not None
                and SEOUL_LON[0] <= lon <= SEOUL_LON[1]
                and SEOUL_LAT[0] <= lat <= SEOUL_LAT[1])
    large = (src.get("lclsSystm1") or "").strip() or None
    raw = {k: v for k, v in src.items() if k and v not in (None, "")}
    raw["_load"] = {"origin": "csv", "file": csv_name,
                    "coord_nulled": (lon is not None or lat is not None) and not in_seoul}
    return {
        "content_id": (src.get("contentid") or "").strip(),
        "content_type_id": (src.get("contenttypeid") or "").strip() or None,
        "area_code": area_code,
        "title": (src.get("title") or "").strip(),
        "address": (src.get("addr1") or "").strip() or None,
        "latitude": lat if in_seoul else None,
        "longitude": lon if in_seoul else None,
        "large_class_code": large,
        "large_class_name": LARGE_CLASS_NAMES.get(large or ""),
        "raw": raw,
    }


def read_rows(path: Path, *, area_code: str,
              exclude_codes: set[str] | None = None) -> tuple[list[dict[str, Any]], Counter]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    stats: Counter = Counter()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for src in csv.DictReader(fh):
            row = to_row(src, area_code=area_code, csv_name=path.name)
            if not row["content_id"] or not row["title"]:
                stats["skipped_no_id_or_title"] += 1
                continue
            if exclude_codes and (row["large_class_code"] or "") in exclude_codes:
                stats["skipped_excluded_code"] += 1
                continue
            if row["content_id"] in seen:
                stats["skipped_duplicate"] += 1
                continue
            seen.add(row["content_id"])
            if row["raw"]["_load"]["coord_nulled"]:
                stats["coord_nulled"] += 1
            if row["large_class_code"] and row["large_class_name"] is None:
                stats["unknown_large_class"] += 1
            rows.append(row)
    stats["rows"] = len(rows)
    return rows, stats


UPSERT = (
    "INSERT INTO place_catalog (tenant_id, source, content_id, content_type_id, "
    "area_code, title, address, latitude, longitude, large_class_code, "
    "large_class_name, raw_json) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON CONFLICT (tenant_id, source, content_id) DO UPDATE SET "
    "content_type_id=EXCLUDED.content_type_id, area_code=EXCLUDED.area_code, "
    "title=EXCLUDED.title, address=EXCLUDED.address, latitude=EXCLUDED.latitude, "
    "longitude=EXCLUDED.longitude, large_class_code=EXCLUDED.large_class_code, "
    "large_class_name=EXCLUDED.large_class_name, raw_json=EXCLUDED.raw_json, "
    "fetched_at=now()"
)


def load(rows: list[dict[str, Any]], *, tenant_id: str, source: str) -> int:
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.columns WHERE table_name='place_catalog' "
            "AND column_name IN ('large_class_code','large_class_name')")
        if cur.fetchone()[0] != 2:
            raise SystemExit("place_catalog 에 신분류 컬럼이 없다 — 먼저 "
                             "`python -m app.infrastructure.db.migrate`(017) 를 돌린다")
        for row in rows:      # ★한 트랜잭션 — 중간에 실패하면 하나도 안 들어간다
            cur.execute(UPSERT, (
                tenant_id, source, row["content_id"], row["content_type_id"],
                row["area_code"], row["title"], row["address"], row["latitude"],
                row["longitude"], row["large_class_code"], row["large_class_name"],
                json.dumps(row["raw"], ensure_ascii=False)))
        cur.execute("SELECT count(*) FROM place_catalog WHERE tenant_id=%s AND source=%s",
                    (tenant_id, source))
        return cur.fetchone()[0]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("csv", type=Path)
    ap.add_argument("--tenant", default="demo")
    ap.add_argument("--source", default="tour_api")
    ap.add_argument("--area-code", default=DEFAULT_AREA_CODE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--exclude-codes", nargs="*", default=[],
                    metavar="CODE", help="제외할 large_class_code (예: FD AC EV)")
    args = ap.parse_args(argv)

    exclude = set(args.exclude_codes) if args.exclude_codes else None
    rows, stats = read_rows(args.csv, area_code=args.area_code, exclude_codes=exclude)
    print(f"읽음 {stats['rows']}건 · 좌표 NULL 처리 {stats['coord_nulled']} · "
          f"건너뜀(식별자/이름 없음 {stats['skipped_no_id_or_title']}, "
          f"중복 {stats['skipped_duplicate']}, 제외코드 {stats['skipped_excluded_code']}) · "
          f"모르는 대분류 {stats['unknown_large_class']}")
    if args.dry_run:
        print("--dry-run: DB 에 쓰지 않았다")
        return
    total = load(rows, tenant_id=args.tenant, source=args.source)
    print(f"적재 완료. place_catalog[{args.tenant}/{args.source}] 현재 {total}건")


if __name__ == "__main__":
    sys.exit(main())
