"""활동 장소 별칭 시드 CSV 를 `activity.ac_place_alias` 에 적재한다. `[2026-10-19]`

입력: `instances/activity/data_processing/place_aliases.csv` (열: content_id · canonical_title · alias · source). 다른 파일은 `--csv` 로.
검증: 정식 제목(`canonical_title`)이 원장 `activity.ac_place.name_ko` 와 다르거나 원장에 없는 행은 **넣지 않고** 알려 준다 —
      별칭이 엉뚱한 장소를 가리키지 않게. 한 별칭이 둘 이상의 장소를 가리키면 그것도 알려 준다(앱은 모호한 별칭을 쓰지 않는다).
적재: (정규화한 별칭, content_id) 기준으로 덮어쓴다(같은 CSV 를 다시 돌려도 같은 결과). CSV 에서 빠진 `curated` 행은 지우지 않고 수만 알려 준다 —
      지우려면 `--prune`(`customer` 행은 건드리지 않는다). 마이그레이션 306 이 먼저 돌아 있어야 한다.
접속: `ACTIVITY_DSN` 이 있으면 그것, 없으면 앱과 같은 코어 설정(`ACOP_DATABASE_URL`).
★운영 DB 에 넣는 것은 원장 `load_places.py` 와 같이 **수동 적재**다 — 배포가 자동으로 하지 않는다.

사용법
    python scripts/activity/load_place_aliases.py --dry-run     몇 행이 들어가는지 · 문제 행만 본다
    python scripts/activity/load_place_aliases.py
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))                       # final_project_cs
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def dsn() -> str:
    given = os.environ.get("ACTIVITY_DSN")
    if given:
        return given
    from app.infrastructure.db.session import database_dsn   # 코어 설정을 못 읽으면 여기서 멈춘다(추측으로 채우지 않는다)

    return database_dsn()


def check(seed: list[dict[str, str]], titles: dict[str, str]) -> tuple[list[dict[str, str]], list[str]]:
    """시드 행을 `(넣을 행, 문제 목록)` 으로. 문제: 원장에 없음 · 정식 제목 불일치 · 빈 별칭 · 별칭이 모호함. 계산만 한다."""
    from app.domains.travel_ops.instances.activity.place_aliases import key_of

    ok: list[dict[str, str]] = []
    problems: list[str] = []
    for row in seed:
        cid, canonical, alias = (row.get("content_id") or "").strip(), (row.get("canonical_title") or "").strip(), row.get("alias") or ""
        if not key_of(alias):
            problems.append(f"빈 별칭: {row}")
        elif cid not in titles:
            problems.append(f"원장에 없는 contentid {cid} ({canonical}) — 별칭 「{alias}」")
        elif titles[cid] != canonical:
            problems.append(f"정식 제목 불일치 {cid}: 파일 「{canonical}」 ≠ 원장 「{titles[cid]}」")
        else:
            ok.append(row)
    owners: dict[str, set[str]] = {}
    for row in ok:
        owners.setdefault(key_of(row["alias"]), set()).add(row["content_id"])
    problems += [f"모호한 별칭 「{k}」 → {sorted(v)} (앱은 쓰지 않는다)" for k, v in owners.items() if len(v) > 1]
    return ok, problems


def load(conn, rows: list[dict[str, str]], *, prune: bool) -> dict[str, int]:
    """한 트랜잭션에서 덮어쓰기 → (선택) 파일에서 빠진 `curated` 행 지우기. 반환 `{"loaded", "stale", "pruned", "total"}`."""
    from app.domains.travel_ops.instances.activity.place_aliases import key_of

    data = [{"alias_norm": key_of(r["alias"]), "content_id": r["content_id"], "alias": r["alias"].strip(),
             "source": (r.get("source") or "curated").strip() or "curated"} for r in rows]
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT to_regclass('activity.ac_place_alias')")
        if cur.fetchone()[0] is None:
            raise SystemExit("activity.ac_place_alias 가 없다 — 마이그레이션 306 을 먼저 돌린다(python -m app.infrastructure.db.migrate)")
        cur.executemany(
            "INSERT INTO activity.ac_place_alias (alias_norm, content_id, alias, source) "
            "VALUES (%(alias_norm)s, %(content_id)s, %(alias)s, %(source)s) "
            "ON CONFLICT (alias_norm, content_id) DO UPDATE SET alias = EXCLUDED.alias, source = EXCLUDED.source", data)
        keep = {(r["alias_norm"], r["content_id"]) for r in data}
        cur.execute("SELECT alias_norm, content_id FROM activity.ac_place_alias WHERE source = 'curated'")
        stale = [pair for pair in cur.fetchall() if tuple(pair) not in keep]
        pruned = 0
        if prune:
            for alias_norm, content_id in stale:
                cur.execute("DELETE FROM activity.ac_place_alias WHERE alias_norm = %s AND content_id = %s AND source = 'curated'",
                            (alias_norm, content_id))
                pruned += cur.rowcount
        cur.execute("SELECT count(*) FROM activity.ac_place_alias")
        total = cur.fetchone()[0]
    return {"loaded": len(data), "stale": len(stale), "pruned": pruned, "total": total}


def main() -> int:
    from app.domains.travel_ops.instances.activity import place_aliases

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", default=str(place_aliases.SEED_CSV))
    parser.add_argument("--dry-run", action="store_true", help="검증만 하고 쓰지 않는다")
    parser.add_argument("--prune", action="store_true", help="파일에서 빠진 curated 행을 지운다")
    args = parser.parse_args()

    from pathlib import Path

    import psycopg

    seed = place_aliases.read_seed(Path(args.csv))
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT content_id, name_ko FROM activity.ac_place")
            titles = dict(cur.fetchall())
        ok, problems = check(seed, titles)
        print(f"시드 {len(seed)}행 → 넣을 행 {len(ok)}, 문제 {len(problems)}")
        for line in problems:
            print("  ! " + line)
        if args.dry_run:
            return 1 if problems else 0
        result = load(conn, ok, prune=args.prune)
    print(f"적재 {result['loaded']}행 · 파일에 없는 curated {result['stale']}행 · 지움 {result['pruned']}행 · 표 전체 {result['total']}행")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
