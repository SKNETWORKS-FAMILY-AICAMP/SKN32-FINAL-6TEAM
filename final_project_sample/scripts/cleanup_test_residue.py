"""테스트가 남긴 테넌트 잔재를 **세어 보여 준다.** 기본은 아무것도 안 지운다.

    python -m scripts.cleanup_test_residue                  # 세기만 한다(기본)
    python -m scripts.cleanup_test_residue --apply          # 백업하고 지운다
    python -m scripts.cleanup_test_residue --restore <dir>  # 백업을 되돌린다

★`final_project_cs` 에서 이식했다(2026-09-07). **삭제 목록은 그대로 못 베낀다** —
  두 저장소의 스키마가 다르다(cs 는 orders·products·shipments, 여기는 payments·
  subscriptions·entitlements·incidents). 그래서 `_check_coverage()` 가
  **스키마에 물어서** 빠진 표가 있으면 시작 전에 멈춘다.

  ★cs 에서 그 게이트가 없을 때 실제로 `products` 368행을 고아로 만들었다.
   목록을 베끼면 원본이 자라거나 스키마가 다를 때 조용히 낡는다.

★왜 필요한가. 잔재가 있으면 **측정이 거짓말을 한다.** cs 에서는 운영 테넌트의
  `routing` Case 가 6건인데 전체를 세면 125건으로 보였다(119건이 테스트 잔재).
  여기도 테넌트 4개 중 3개가 잔재다.

★왜 쌓였나. 픽스처는 `finally` 로 제대로 치운다. 남은 것은 **중단된 실행**의
  잔재다 — 프로세스가 죽으면 `finally` 는 돌지 않는다.

★그래서 기본이 dry-run 이고, `--apply` 는 **지우기 전에 반드시 백업한다.**
  끄는 옵션을 두지 않았다 — "이번만 백업 없이" 가 사고가 나는 자리다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Json

from acop_basement.core.settings import get_settings
from acop_basement.infrastructure.db.session import get_connection

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 백업이 놓이는 곳. `var/` 는 gitignore 라 커밋되지 않는다.
BACKUP_ROOT = REPO_ROOT / "var" / "test_residue_backup"

#: 테스트 픽스처가 쓰는 테넌트 접두어. ★코드에서 찾아 적었다 — 짐작하지 않는다.
#:  `test_api_` 는 `test_` 가 이미 포함하므로 따로 넣지 않는다(겹치면 두 번 센다).
#:  `foreign_` 은 `test_outbox_resolution.py:86` 의 tenant 격리 검사가 쓴다.
PREFIXES = ("test\\_", "foreign\\_")

#: FK 순서. ★하나라도 빠지면 트랜잭션이 통째로 롤백되어 **아무것도 안 지워진다.**
#:  복원은 이 순서를 **거꾸로** 탄다(부모부터 넣어야 자식의 FK 가 성립한다).
_BY_TENANT = "tenant_id LIKE %s ESCAPE '\\'"
DELETE_ORDER = (
    ("knowledge_chunks",
     "document_id IN (SELECT document_id FROM knowledge_documents WHERE tenant_id LIKE %s ESCAPE '\\')"),
    ("knowledge_documents", _BY_TENANT),
    ("team_tasks",
     "run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id LIKE %s ESCAPE '\\')"),
    ("agent_runs", _BY_TENANT),
    ("action_requests", _BY_TENANT),
    ("case_events", _BY_TENANT),
    ("outbox", _BY_TENANT),
    ("feedback_analytics_reports", _BY_TENANT),
    # ★`incidents` 는 customers 와 customer_cases 를 둘 다 참조한다 — 앞에 둔다
    ("incidents", _BY_TENANT),
    ("customer_cases", _BY_TENANT),
    # ★`payments` 는 subscriptions 를 참조한다 — 먼저 지운다
    ("payments", _BY_TENANT),
    ("subscriptions", _BY_TENANT),
    ("entitlements", _BY_TENANT),
    ("customers", _BY_TENANT),
    ("tenants", _BY_TENANT),
)


def _check_coverage(conn) -> None:
    """`tenant_id` 를 가진 표가 **전부** 목록에 있는가 — 스키마에 대고 센다.

    ★`tenants` 로의 FK 를 가진 표는 `customers` 하나뿐이다. 나머지는 테넌트 행을
      지워도 **살아남아 고아가 된다** — 빠뜨리면 안 지우느니만 못하다.
      cs 에서 이 게이트가 없을 때 실제로 그 일이 났다(2026-09-07).
    """
    with conn.cursor() as cur:
        cur.execute("""SELECT table_name FROM information_schema.columns
                       WHERE table_schema='public' AND column_name='tenant_id'""")
        in_schema = {r[0] for r in cur.fetchall()}
    missing = sorted(in_schema - {table for table, _ in DELETE_ORDER})
    if missing:
        raise SystemExit(
            "★중단한다 — tenant_id 를 가진 표가 삭제 목록에 없다: " + ", ".join(missing)
            + "\n  빠뜨린 채 지우면 그 표의 행이 고아로 남는다. DELETE_ORDER 에 더한다.")


def _guard(conn) -> list[str]:
    """운영 테넌트가 이 패턴에 걸리면 **아무것도 하지 않는다.**"""
    configured = get_settings().tenant_id
    with conn.cursor() as cur:
        for prefix in PREFIXES:
            cur.execute("SELECT %s LIKE %s ESCAPE '\\'", (configured, prefix + "%"))
            if cur.fetchone()[0]:
                raise SystemExit(
                    f"★중단한다 — 설정된 tenant_id {configured!r} 가 삭제 패턴 "
                    f"{prefix!r} 에 걸린다. 이 스크립트는 운영 데이터를 지우지 않는다.")
    return sorted(set(PREFIXES))


def _survey(conn) -> dict[str, int]:
    """무엇이 얼마나 남아 있는가. **읽기만 한다.**"""
    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        for table, where in DELETE_ORDER:
            total = 0
            for prefix in PREFIXES:
                cur.execute(f"SELECT count(*) FROM {table} WHERE {where}", (prefix + "%",))
                total += cur.fetchone()[0]
            counts[table] = total
    return counts


def _dump(conn, directory: Path) -> dict[str, int]:
    """지우기 **전에** 대상 행을 통째로 받아 적는다.

    ★컬럼 이름을 함께 남긴다. 위치만 남기면 스키마가 한 칸만 바뀌어도 복원이
      조용히 어긋난 열에 값을 넣는다.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    with conn.cursor() as cur:
        for table, where in DELETE_ORDER:
            rows: list[dict[str, Any]] = []
            for prefix in PREFIXES:
                cur.execute(f"SELECT * FROM {table} WHERE {where}", (prefix + "%",))
                columns = [d.name for d in cur.description]
                rows.extend(dict(zip(columns, r)) for r in cur.fetchall())
            with (directory / f"{table}.jsonl").open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            written[table] = len(rows)
    (directory / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prefixes": list(PREFIXES),
        "delete_order": [table for table, _ in DELETE_ORDER],
        "counts": written,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return written


def _restore(conn, directory: Path) -> dict[str, int]:
    """백업을 되돌린다. ★삭제 순서를 **거꾸로** 탄다 — 부모부터 넣어야 FK 가 산다."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    restored: dict[str, int] = {}
    with conn.transaction():
        with conn.cursor() as cur:
            for table in reversed(manifest["delete_order"]):
                path = directory / f"{table}.jsonl"
                if not path.is_file():
                    continue
                count = 0
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    columns = list(row)
                    # ★dict·list 는 jsonb 칸이다. 문자열로 넣으면 타입이 어긋난다.
                    values = [Json(v) if isinstance(v, (dict, list)) else v
                              for v in row.values()]
                    cur.execute(
                        f'INSERT INTO {table} ({", ".join(columns)}) '
                        f'VALUES ({", ".join(["%s"] * len(columns))})', values)
                    count += 1
                restored[table] = count
    return restored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="백업한 뒤 실제로 지운다. 없으면 세기만 한다(기본)")
    parser.add_argument("--restore", metavar="DIR", help="백업 폴더를 되돌린다")
    args = parser.parse_args()

    if args.restore:
        directory = Path(args.restore)
        if not (directory / "manifest.json").is_file():
            raise SystemExit(f"★백업이 아니다 — manifest.json 이 없다: {directory}")
        with get_connection() as conn:
            restored = _restore(conn, directory)
        for table, n in restored.items():
            if n:
                print(f"   {table:26s} {n:6d}")
        print(f"복원했다: {sum(restored.values())} 행  ({directory})")
        return 0

    with get_connection() as conn:
        _check_coverage(conn)
        prefixes = _guard(conn)
        counts = _survey(conn)

        total = sum(counts.values())
        print(f"대상 접두어: {', '.join(p.replace(chr(92), '') for p in prefixes)}")
        print(f"설정된 운영 tenant_id: {get_settings().tenant_id}  (건드리지 않는다)")
        print()
        for table, n in counts.items():
            if n:
                print(f"   {table:26s} {n:6d}")
        if not total:
            print("   (남은 것 없음)")
            return 0
        print(f"   {'합계':26s} {total:6d}")

        if not args.apply:
            print()
            print("★아무것도 지우지 않았다. 실제로 지우려면 --apply 를 준다.")
            print("  --apply 는 지우기 전에 백업한다. 되돌리려면 --restore <폴더>.")
            return 0

        directory = BACKUP_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        written = _dump(conn, directory)
        if sum(written.values()) != total:
            # ★백업한 수와 지울 수가 다르면 **지우지 않는다.**
            raise SystemExit(f"★중단한다 — 백업 {sum(written.values())} 행 ≠ 대상 {total} 행")
        print()
        print(f"백업: {directory}")

        with conn.transaction():
            with conn.cursor() as cur:
                for table, where in DELETE_ORDER:
                    for prefix in PREFIXES:
                        cur.execute(f"DELETE FROM {table} WHERE {where}", (prefix + "%",))
        print(f"지웠다: {total} 행")
        print(f"되돌리려면: python -m scripts.cleanup_test_residue --restore {directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
