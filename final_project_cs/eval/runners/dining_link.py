# -*- coding: utf-8 -*-
"""원장 ↔ 장소 연결 평가 — 정답셋(`eval/datasets/dining_link_v1.jsonl`)으로 두 연결 길을 잰다. `[2026-10-14]`

    python -m eval.runners.dining_link [--holdout] [--dsn ...] [--out REPORT.json] [--with-sql MIGRATION.sql]

★재는 길
    db       등록 뒤 — `dining.link_core_place`(224): 관광공사 번호 → 없으면 80m · 이름(유사도 0.75)으로 후보가 하나일 때
    review   등록 전 확인 화면 — `ledger._catalog_uid`: 원장 가게 번호 → 관광공사 번호 → 이름 찾기(`find_place_by_name`)
★판정(사례 · 길마다 하나)
    correct_link     맞는 가게와 이었다
    correct_abstain  잇지 않아야 하는 사례에서 잇지 않았다
    wrong_link       ★다른 가게와 이었다 — 다른 가게의 영업시간으로 판정하게 된다. **가장 나쁘다. 목표 0**
    missed           이어야 하는데 잇지 않았다(판정이 「모름」으로 남는다)
    stale            정답 가게가 원장에서 사라졌다(원장을 다시 세웠다) — 점수에서 뺀다
★DB 길은 사례마다 장소 한 행을 넣고 연결 함수를 부른 뒤 **되돌린다**(ROLLBACK). 원장 · 코어 표에 남는 것이 없다.
★`--with-sql` — 아직 원장 DB 에 안 올린 마이그레이션(함수 교체)을 **이 실행의 트랜잭션 안에서만** 올리고 끝에 되돌린다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from app.domains.travel_ops.instances.dining.ledger import _catalog_uid

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "eval" / "datasets" / "dining_link_v1.jsonl"
HOLDOUT = ROOT / "eval" / "datasets" / "dining_link_holdout_v1.jsonl"
TENANT = "eval_link"
LABELS = ("correct_link", "correct_abstain", "wrong_link", "missed", "stale")


def label(expected: str | None, got: str | None) -> str:
    if expected is None:
        return "correct_abstain" if got is None else "wrong_link"
    if got is None:
        return "missed"
    return "correct_link" if got == expected else "wrong_link"


def via_db(conn, place: dict) -> str | None:
    with conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute("INSERT INTO places (tenant_id, name, kind, latitude, longitude, source_name, source_content_id, "
                    "trip_scope) VALUES (%s, %s, %s, %s, %s, %s, %s, gen_random_uuid()) RETURNING place_id",
                    (TENANT, place["name"], place["kind"], place["latitude"], place["longitude"],
                     place.get("source_name"), place.get("source_content_id")))
        core_id = cur.fetchone()[0]
        cur.execute("SELECT dining.link_core_place(%s, %s)", (TENANT, core_id))
        uid = cur.fetchone()[0]
    return str(uid) if uid else None


def via_review(conn, place: dict) -> str | None:
    with conn.transaction(force_rollback=True):
        return _catalog_uid(conn, place.get("source_content_id"), dict(place))


def names(conn, uids: set[str]) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT place_uid::text, name_ko FROM dining.dn_place WHERE place_uid::text = ANY(%s)", (list(uids),))
        return dict(cur.fetchall())


def run(dsn: str, path: Path, *, with_sql: str | None = None) -> dict:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    with psycopg.connect(dsn) as conn:
        if with_sql:
            conn.execute(with_sql)            # 바깥 트랜잭션 — 끝에 되돌린다
        alive = names(conn, {c["expect"]["place_uid"] for c in cases if c["expect"]["place_uid"]})
        for case in cases:
            expected = case["expect"]["place_uid"]
            row = {"id": case["id"], "group": case["group"], "place": case["place"]["name"], "expect": case["expect"]["name"]}
            for way, fn in (("db", via_db), ("review", via_review)):
                if expected and expected not in alive:
                    row[way] = {"label": "stale", "got": None}
                    continue
                try:
                    got = fn(conn, case["place"])
                except Exception as exc:   # noqa: BLE001 — 사례 하나가 죽어도 나머지를 잰다. 죽은 것은 error 로 센다
                    row[way] = {"label": "error", "got": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
                    continue
                row[way] = {"label": label(expected, got), "got": got}
            rows.append(row)
        got_names = names(conn, {r[w]["got"] for r in rows for w in ("db", "review") if r[w].get("got")})
        conn.rollback()                       # ★with 블록은 끝에 커밋한다 — 올린 함수 · 아무것도 남기지 않는다
    for r in rows:
        for way in ("db", "review"):
            if r[way].get("got"):
                r[way]["got_name"] = got_names.get(r[way]["got"])
    return {"dataset": path.name, "n": len(rows), "rows": rows,
            "summary": {way: summarize(rows, way) for way in ("db", "review")}}


def summarize(rows: list[dict], way: str) -> dict:
    total = Counter(r[way]["label"] for r in rows)
    by_group: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_group[r["group"]][r[way]["label"]] += 1
    scored = sum(v for k, v in total.items() if k not in ("stale",))
    correct = total["correct_link"] + total["correct_abstain"]
    should_link = sum(1 for r in rows if r["expect"] and r[way]["label"] != "stale")
    linked = sum(1 for r in rows if r[way].get("got"))
    return {"labels": dict(total), "accuracy": f"{correct}/{scored}",
            "wrong_link": total["wrong_link"], "error": total["error"],
            # 이은 것 중 맞는 비율 · 이어야 할 것 중 이은 비율
            "precision": f"{total['correct_link']}/{linked}", "recall": f"{total['correct_link']}/{should_link}",
            "by_group": {g: dict(c) for g, c in by_group.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://postgres:postgres@127.0.0.1:5433/dining_rebuild")
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--with-sql", help="이 실행 안에서만 올렸다가 되돌릴 SQL 파일")
    a = ap.parse_args()
    sql = Path(a.with_sql).read_text(encoding="utf-8") if a.with_sql else None
    report = run(a.dsn, HOLDOUT if a.holdout else DEV, with_sql=sql)
    report["env"] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "db": a.dsn.rsplit("/", 1)[-1],
                     "with_sql": Path(a.with_sql).name if a.with_sql else None}
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    return 1 if any(s["error"] for s in report["summary"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
