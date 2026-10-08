"""인허가(사업자 등록) 영업 중 식당을 `dining.dn_license_shop` 에 적재한다 — 이름 찾기 전용. `[2026-10-05 사용자 지시]`

입력: `fetch_license.py` 가 받은 `datasets/dining/raw/서울시 일반음식점 인허가 정보_<날짜>.csv` · `서울시 휴게음식점 인허가 정보_<날짜>.csv` (가장 최근 것).
거르는 것: 영업/정상만 · 주소가 「서울」 · 편의점 · 백화점(식당이 아니다). 좌표는 중부원점TM(EPSG:5174, 실측 오차 중앙값 6m)을 위경도로 바꾼다.
적재: 표를 비우고 다시 채운다(마이그레이션 225 가 먼저 돌아 있어야 한다). 재적재(`rebuild.py`) 뒤에 자동으로 부른다.

사용법
    python scripts/dining/load_license.py --dry-run     몇 곳이 들어가는지만 본다
    python scripts/dining/load_license.py
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.environ.get("DINING_RAW") or os.path.join(os.path.dirname(ROOT), "datasets", "dining", "raw")
SKIP_CATEGORIES = {"편의점", "백화점"}
FILES = (("general", "서울시 일반음식점 인허가 정보_*.csv"), ("rest", "서울시 휴게음식점 인허가 정보_*.csv"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def name_key(name: str | None) -> str:
    """이름 찾기 키 — `dining.ledger.find_place_by_name` 과 같은 규칙(소문자 · 한글 영숫자만)."""
    return re.sub(r"[^가-힣a-z0-9]", "", (name or "").lower())


def to_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat((text or "").strip()[:10])
    except ValueError:
        return None


def convert(transformer, x: str | None, y: str | None) -> tuple[float | None, float | None]:
    try:
        lon, lat = transformer.transform(float((x or "").strip()), float((y or "").strip()))
    except (TypeError, ValueError):
        return None, None
    # 서울 안(대략) 이 아니면 변환이 틀린 것이다 — 좌표를 비운다(이름 찾기에서 빠진다)
    if not (37.4 <= lat <= 37.72 and 126.7 <= lon <= 127.2):
        return None, None
    return round(lat, 7), round(lon, 7)


def rows(raw_dir: str = RAW):
    """(관리번호, 상호, 키, 도로명, 지번, 자치구, 업태, 전화, 위도, 경도, 허가일, 종류) 를 하나씩. 파일이 없으면 빈 순서."""
    import pyproj

    transformer = pyproj.Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)
    for kind, pattern in FILES:
        files = sorted(glob.glob(os.path.join(raw_dir, pattern)))
        if not files:
            continue
        with open(files[-1], encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if not row["TRDSTATENM"].strip().startswith("영업") or row["UPTAENM"].strip() in SKIP_CATEGORIES:
                    continue
                road, jibun = row["RDNWHLADDR"].strip(), row["SITEWHLADDR"].strip()
                if not (road or jibun).startswith("서울"):
                    continue
                key = name_key(row["BPLCNM"])
                if not key:
                    continue
                parts = (road or jibun).split()
                lat, lng = convert(transformer, row["X"], row["Y"])
                yield (row["MGTNO"].strip(), row["BPLCNM"].strip(), key, road or None, jibun or None,
                       parts[1] if len(parts) > 1 else None, row["UPTAENM"].strip() or None,
                       row["SITETEL"].strip() or None, lat, lng, to_date(row["APVPERMYMD"]), kind)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    data = list(rows())
    if not data:
        sys.exit("인허가 CSV 가 없다 — 먼저 scripts/dining/fetch_license.py")
    with_coord = sum(1 for r in data if r[8] is not None)
    print(f"영업 중 식당 {len(data):,}곳 (좌표 있음 {with_coord:,})")
    if args.dry_run:
        return
    sys.path.insert(0, HERE)
    import core_db
    import psycopg

    with psycopg.connect(core_db.dsn()) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('dining.dn_license_shop')")
        if cur.fetchone()[0] is None:
            sys.exit("dining.dn_license_shop 이 없다 — 마이그레이션 225 를 먼저 돌린다(python -m app.infrastructure.db.migrate)")
        cur.execute("TRUNCATE dining.dn_license_shop")
        with cur.copy("COPY dining.dn_license_shop (mgt_no, name_ko, name_key, road_address, jibun_address, area, category, "
                      "phone, lat, lng, approved_on, source_kind) FROM STDIN") as copy:
            seen: set[str] = set()
            for r in data:
                if r[0] in seen:                          # 관리번호가 겹치면 먼저 온 것만
                    continue
                seen.add(r[0])
                copy.write_row(r)
        cur.execute("ANALYZE dining.dn_license_shop")
        cur.execute("SELECT count(*) FROM dining.dn_license_shop")
        print("적재:", cur.fetchone()[0], "곳")


if __name__ == "__main__":
    main()
