"""활동 장소 CSV 를 `activity.ac_place` 에 적재한다. `[2026-10-12]`

입력: `instances/activity/data_processing/activity_total_data.csv` (6,338행). 다른 파일은 `--csv` 로.
적재: content_id 기준으로 덮어쓴다(같은 CSV 를 다시 돌려도 같은 결과). CSV 에서 빠진 행은 지우지 않고 수만 알려 준다 —
      지우려면 `--prune`. 마이그레이션 300 이 먼저 돌아 있어야 한다.
접속: `ACTIVITY_DSN` 이 있으면 그것, 없으면 앱과 같은 코어 설정(`ACOP_DATABASE_URL`).

사용법
    python scripts/activity/load_places.py --dry-run     몇 행이 들어가는지만 본다
    python scripts/activity/load_places.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
CSV_PATH = os.path.join(ROOT, "app", "domains", "travel_ops", "instances", "activity",
                        "data_processing", "activity_total_data.csv")
#: CSV 칸 → 표 칸. CSV 에 없는 칸(상세 수집 6칸이 아직 없을 때)은 NULL 로 들어간다.
COLUMNS = (
    ("contentid", "content_id"), ("contenttypeid", "content_type_id"), ("title", "name_ko"),
    ("addr1", "addr1"), ("addr2", "addr2"), ("sigungucode", "sigungu_code"),
    ("lclsSystm1", "lcls1"), ("lclsSystm2", "lcls2"), ("lclsSystm3", "lcls3"), ("brand", "brand"),
    ("business_hours", "usetime_text"), ("closed_days", "restdate_text"),
    ("overview", "overview"), ("fee", "fee_text"),
    ("info_center", "info_center"), ("reservation", "reservation_text"), ("capacity", "capacity_text"),
    ("spend_time", "spend_time"), ("age_limit", "age_limit"), ("experience_guide", "experience_guide"),
)
TARGETS = [t for _, t in COLUMNS] + ["name_key", "lat", "lng"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _coord(row: dict[str, str]) -> tuple[float | None, float | None]:
    """(위도, 경도). 한쪽이라도 못 읽거나 0 이면 둘 다 비운다(표의 짝 제약)."""
    try:
        lat, lng = float(row.get("mapy") or ""), float(row.get("mapx") or "")
    except ValueError:
        return None, None
    if not lat or not lng:
        return None, None
    return lat, lng


def rows(path: str) -> list[dict[str, object]]:
    """CSV 한 행 → 표 한 행. content_id 나 이름이 비면 건너뛰고, content_id 가 겹치면 먼저 온 것만."""
    from app.domains.travel_ops.instances.activity.csv_places import _normalize

    out: list[dict[str, object]] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for raw in csv.DictReader(fh):
            row = {target: _text(raw.get(source)) for source, target in COLUMNS}
            if not row["content_id"] or not row["name_ko"] or row["content_id"] in seen:
                continue
            seen.add(row["content_id"])
            row["name_key"] = _normalize(row["name_ko"])
            row["lat"], row["lng"] = _coord(raw)
            out.append(row)
    return out


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dsn() -> str:
    given = os.environ.get("ACTIVITY_DSN")
    if given:
        return given
    from app.infrastructure.db.session import database_dsn   # 코어 설정을 못 읽으면 여기서 멈춘다(추측으로 채우지 않는다)

    return database_dsn()


def load(conn, data: list[dict[str, object]], *, source_file: str, file_sha256: str, prune: bool) -> dict[str, int]:
    """한 트랜잭션에서 적재 기록 → 덮어쓰기 → (선택) 빠진 행 지우기. 반환 `{"loaded", "stale", "pruned", "total"}`."""
    placeholders = ", ".join(f"%({c})s" for c in TARGETS)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in TARGETS if c != "content_id")
    # ★원문이 바뀐 행만 미리 편 요일표를 비운다 — 다음 `read_hours.py` 가 다시 편다. 안 바뀐 행은 모델로 읽은 값을 지키지 않으면
    #   같은 CSV 를 다시 적재할 때마다 모델 호출을 다시 해야 한다.
    changed = ("activity.ac_place.usetime_text IS DISTINCT FROM EXCLUDED.usetime_text "
               "OR activity.ac_place.restdate_text IS DISTINCT FROM EXCLUDED.restdate_text")
    updates += (f", hours_week = CASE WHEN {changed} THEN NULL ELSE activity.ac_place.hours_week END"
                f", hours_read = CASE WHEN {changed} THEN NULL ELSE activity.ac_place.hours_read END")
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT to_regclass('activity.ac_place')")
        if cur.fetchone()[0] is None:
            raise SystemExit("activity.ac_place 가 없다 — 마이그레이션 300 을 먼저 돌린다(python -m app.infrastructure.db.migrate)")
        cur.execute("INSERT INTO activity.ac_load_meta (source_file, file_sha256, row_count) VALUES (%s, %s, %s) "
                    "RETURNING load_id", (source_file, file_sha256, len(data)))
        load_id = cur.fetchone()[0]
        cur.executemany(
            f"INSERT INTO activity.ac_place ({', '.join(TARGETS)}, load_id) VALUES ({placeholders}, %(load_id)s) "
            f"ON CONFLICT (content_id) DO UPDATE SET {updates}, load_id = EXCLUDED.load_id, updated_at = now()",
            [{**r, "load_id": load_id} for r in data])
        cur.execute("SELECT count(*) FROM activity.ac_place WHERE load_id <> %s", (load_id,))
        stale = cur.fetchone()[0]
        pruned = 0
        if prune and stale:
            cur.execute("DELETE FROM activity.ac_place WHERE load_id <> %s", (load_id,))
            pruned = cur.rowcount
        cur.execute("SELECT count(*) FROM activity.ac_place")
        total = cur.fetchone()[0]
    return {"loaded": len(data), "stale": stale, "pruned": pruned, "total": total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--csv", default=CSV_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prune", action="store_true", help="이번 CSV 에 없는 행을 지운다")
    args = parser.parse_args()
    data = rows(args.csv)
    with_coord = sum(1 for r in data if r["lat"] is not None)
    print(f"장소 {len(data):,}곳 (좌표 있음 {with_coord:,}, 운영시간 원문 있음 "
          f"{sum(1 for r in data if r['usetime_text']):,}, 휴무 원문 있음 {sum(1 for r in data if r['restdate_text']):,})")
    if args.dry_run:
        return
    import psycopg

    with psycopg.connect(dsn()) as conn:
        result = load(conn, data, source_file=os.path.relpath(args.csv, ROOT), file_sha256=sha256(args.csv),
                      prune=args.prune)
    print(f"적재 {result['loaded']:,}곳 · 표 전체 {result['total']:,}곳"
          + (f" · CSV 에 없는 행 {result['stale']:,}곳" + (f"(지움 {result['pruned']:,})" if args.prune else " (--prune 으로 지운다)")
             if result["stale"] else ""))


if __name__ == "__main__":
    main()
