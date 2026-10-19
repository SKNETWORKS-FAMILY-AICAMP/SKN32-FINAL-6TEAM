# -*- coding: utf-8 -*-
"""재생 시험용 **참고 자료**(고객 대화 아님)를 운영 DB 에서 읽기 전용으로 한 번 받고(`fetch`), 시험 DB 에 넣는다(`load`). `[2026-10-19]`

★운영 DB 읽기다 — **사용자 허락을 받은 뒤에만** 돌린다. 쓰기 없음(첫 줄 `SET default_transaction_read_only = on`, SELECT 만), 한 번만.
- 받는 표: 장소(`places` · `place_catalog` · `place_aliases` · `catalog_hours` · `place_provider_ids` · `place_embeddings` · `lg_core_place_link`) ·
  규정 문서(`knowledge_documents` · `knowledge_chunks`) · 대피소(`safety_shelters`) · 원장 스키마(`dining` · `activity` 의 표 전부 — 2026-10-19 허락 범위).
- 접속은 SSH 별칭과 DB 컨테이너 이름(인자)만 쓴다 — 주소 · 계정은 `~/.ssh/config` 에만 있다.
- 결과는 `<out>/reference.jsonl` 새 파일(이미 있으면 멈춘다) + `reference.meta.json`(시각 · 표별 줄 수).

    python -m eval.conversation_replay.fetch_reference fetch --ssh <별칭> --container <DB 컨테이너> --out <git 밖 폴더>
    python -m eval.conversation_replay.fetch_reference load --db <시험 DB 주소(replay)> --out <같은 폴더> [--tenant demo]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

KST = timezone(timedelta(hours=9))
PSQL = 'psql -At -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
TABLES = ["places", "place_catalog", "place_aliases", "catalog_hours", "place_provider_ids", "place_embeddings", "lg_core_place_link",
          "knowledge_documents", "knowledge_chunks", "safety_shelters"]
SCHEMAS = ["dining", "activity"]          # 2026-10-19 사용자 허락 범위(요식 · 활동 원장)


def _script(container: str) -> str:
    """원격에서 돌 셸 — 원장 스키마의 표 이름을 먼저 읽고, 공용 표와 함께 한 줄 JSON 으로 내보낸다(읽기 전용 거래)."""
    names = "SELECT string_agg(table_schema || '.' || table_name, ' ') FROM information_schema.tables " \
            "WHERE table_schema IN (" + ",".join(f"'{s}'" for s in SCHEMAS) + ") AND table_type = 'BASE TABLE';"
    body = ["SET default_transaction_read_only = on;"]
    body += [f"SELECT json_build_object('t','{t}','r',row_to_json(x))::text FROM public.{t} x;" for t in TABLES]
    # ★원격에 임시 파일을 쓰지 않는다 — 조회문은 표준 입력(here-doc)으로만 넘긴다
    return (f"T=$(docker exec -i {container} sh -c '{PSQL}' <<'SQL_EOF'\n" + names + "\nSQL_EOF\n)\n"
            "{ cat <<'SQL_EOF'\n" + "\n".join(body) + "\nSQL_EOF\n"
            "for t in $T; do echo \"SELECT json_build_object('t','$t','r',row_to_json(x))::text FROM $t x;\"; done; } | "
            f"docker exec -i {container} sh -c '{PSQL}'\n")


def fetch(ssh: str, container: str, out: Path, remote_shell: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    target = out / "reference.jsonl"
    if target.exists():
        raise SystemExit(f"이미 있다 — 덮어쓰지 않는다: {target}")
    started = datetime.now(KST).isoformat()
    res = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", ssh, remote_shell],
                         input=_script(container).encode("utf-8"), capture_output=True, timeout=1800)
    if res.returncode:
        print(res.stderr.decode("utf-8", "replace")[-2000:])
        raise SystemExit(res.returncode)
    counts: dict[str, int] = {}
    with target.open("x", encoding="utf-8", newline="\n") as fh:
        for line in res.stdout.decode("utf-8").splitlines():
            if line.startswith("{"):
                counts[json.loads(line)["t"]] = counts.get(json.loads(line)["t"], 0) + 1
                fh.write(line + "\n")
    meta = {"ssh_alias": ssh, "started_kst": started, "finished_kst": datetime.now(KST).isoformat(), "counts": counts,
            "read_only": "default_transaction_read_only=on", "tables": TABLES, "schemas": SCHEMAS}
    (out / "reference.meta.json").open("x", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def load(db: str, out: Path, tenant: str) -> dict:
    import psycopg

    from .seed import assert_test_db

    assert_test_db(db)
    counts: dict[str, int] = {}
    with psycopg.connect(db.replace("postgresql+psycopg://", "postgresql://")) as conn, conn.cursor() as cur:
        cur.execute("SET session_replication_role = replica")      # 표 사이 FK 순서를 신경 쓰지 않게 — 시험 DB 에서만
        with (out / "reference.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                o = json.loads(line)
                table = o["t"] if "." in o["t"] else f"public.{o['t']}"
                row = o["r"]
                if "tenant_id" in row:
                    row["tenant_id"] = tenant
                cur.execute(f"INSERT INTO {table} SELECT * FROM json_populate_record(NULL::{table}, %s::json) ON CONFLICT DO NOTHING",
                            (json.dumps(row),))
                counts[o["t"]] = counts.get(o["t"], 0) + cur.rowcount
        conn.commit()
    return counts


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("fetch", "load"))
    ap.add_argument("--ssh", default="x600")
    ap.add_argument("--remote-shell", default="wsl -u root -e sh -s")
    ap.add_argument("--container")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db")
    ap.add_argument("--tenant", default="demo")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.action == "fetch":
        if not args.container:
            raise SystemExit("--container 필요")
        print(json.dumps(fetch(args.ssh, args.container, args.out, args.remote_shell), ensure_ascii=False))
    else:
        print(json.dumps(load(args.db, args.out, args.tenant), ensure_ascii=False))


if __name__ == "__main__":
    main()
