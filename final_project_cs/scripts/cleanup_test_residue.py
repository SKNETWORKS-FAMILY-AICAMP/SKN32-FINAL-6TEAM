"""테스트가 남긴 테넌트 잔재를 **세어 보여 준다.** 기본은 아무것도 안 지운다.

    python -m scripts.cleanup_test_residue                  # 세기만 한다(기본)
    python -m scripts.cleanup_test_residue --apply          # 백업하고 지운다
    python -m scripts.cleanup_test_residue --restore <dir>  # 백업을 되돌린다

★왜 필요한가 (2026-09-07 실측). 개발 DB 에 테스트 테넌트가 **256개** 쌓여 있고
  그 아래 Case 187건이 남아 있다. 실제 운영 테넌트(`demo`)의 Case 는 6건인데,
  상태를 세면 `routing 125건` 처럼 보인다 — 실제로는 그중 119건이 테스트 잔재다.
  **측정이 거짓말을 하게 만든다.** 실제로 이 세션에서 그 숫자를 보고 한 번
  오독했다.

★왜 쌓였나. 픽스처는 `finally` 로 제대로 치운다 — 전체 실행 3회를 앞뒤로 세어
  **늘어나지 않는 것**을 확인했다. 남은 것은 **중단된 실행**의 잔재다.
  프로세스가 죽으면 `finally` 는 돌지 않는다. 이 저장소는 그런 일을 겪었다
  (크래시 `3221226505`, 고아 파이썬 프로세스 38개 정리 등).

★그래서 이 도구는 **기본이 dry-run** 이다. 지우는 것은 되돌릴 수 없고, 무엇이
  지워지는지 사람이 먼저 봐야 한다.

★`--apply` 는 **지우기 전에 반드시 백업한다.** 끄는 옵션을 두지 않았다 —
  "이번만 백업 없이" 가 사고가 나는 자리다. 백업은 되살릴 수 있어야 백업이므로
  `--restore` 를 같이 넣었고, 왕복(백업→삭제→복원→행 수 일치)을 실측했다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Json

from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection

REPO_ROOT = Path(__file__).resolve().parents[1]

#: 백업이 놓이는 곳. `var/` 는 gitignore 라 커밋되지 않는다.
BACKUP_ROOT = REPO_ROOT / "var" / "test_residue_backup"

#: 테스트 픽스처가 쓰는 테넌트 접두어. ★여기 없는 것은 **건드리지 않는다.**
#:  `LIKE 'test%'` 같은 넓은 패턴을 쓰지 않는 이유는, 언젠가 `testbed` 처럼
#:  진짜 테넌트가 그 이름으로 생기면 조용히 지워 버리기 때문이다.
#:  ★`test\_api\_` 를 따로 넣지 않는다 — `test\_%` 가 이미 그것을 포함한다.
#:   처음엔 둘 다 넣었다가 **모든 수를 두 번 셌다**(2026-09-07, 테넌트 256을
#:   344로 보고했다). 겹치는 패턴은 세는 것도 지우는 것도 두 번 한다.
#:  ★`other\_`·`voc\_other\_` 는 **테넌트 격리 테스트**가 쓴다
#:   (`test_db_integration.py:124`·`test_feedback.py:40`). 이름이 `test` 로
#:   시작하지 않아 1차 정리에서 통째로 빠졌다 — 접두어를 코드에서 찾아 세지 않고
#:   짐작한 탓이다(2026-09-07). 테스트가 새 접두어를 쓰기 시작하면 여기도 는다.
PREFIXES = ("test\\_", "live\\_classifier\\_", "other\\_", "voc\\_other\\_")

#: FK 순서. ★하나라도 빠지면 트랜잭션이 통째로 롤백되어 **아무것도 안 지워진다.**
#:  복원은 이 순서를 **거꾸로** 탄다(부모부터 넣어야 자식의 FK 가 성립한다).
DELETE_ORDER = (
    # 지식 자료 — chunks 가 documents 를 참조한다
    ("knowledge_chunks",
     "document_id IN (SELECT document_id FROM knowledge_documents WHERE tenant_id LIKE %s ESCAPE '\\')"),
    ("knowledge_documents", "tenant_id LIKE %s ESCAPE '\\'"),
    # ★부모가 없는 표들. `tenants` 로의 FK 가 없어서 테넌트를 지워도 **살아남는다** —
    #   1차 정리에서 이걸 빠뜨려 `products` 368행을 고아로 만들었다(2026-09-07).
    ("products", "tenant_id LIKE %s ESCAPE '\\'"),
    ("feedback_analytics_reports", "tenant_id LIKE %s ESCAPE '\\'"),
    ("llm_calls", "run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id LIKE %s ESCAPE '\\')"),
    ("team_tasks", "run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id LIKE %s ESCAPE '\\')"),
    ("agent_runs", "tenant_id LIKE %s ESCAPE '\\'"),
    ("action_approvals",
     "action_id IN (SELECT action_id FROM action_requests WHERE tenant_id LIKE %s ESCAPE '\\')"),
    ("action_requests", "tenant_id LIKE %s ESCAPE '\\'"),
    ("case_events", "tenant_id LIKE %s ESCAPE '\\'"),
    ("outbox", "tenant_id LIKE %s ESCAPE '\\'"),
    ("returns", "tenant_id LIKE %s ESCAPE '\\'"),
    ("shipments", "tenant_id LIKE %s ESCAPE '\\'"),
    ("order_items", "tenant_id LIKE %s ESCAPE '\\'"),
    ("orders", "tenant_id LIKE %s ESCAPE '\\'"),
    ("customer_cases", "tenant_id LIKE %s ESCAPE '\\'"),
    ("customers", "tenant_id LIKE %s ESCAPE '\\'"),
    ("tenants", "tenant_id LIKE %s ESCAPE '\\'"),
)


def _check_coverage(conn) -> None:
    """`tenant_id` 를 가진 표가 **전부** 목록에 있는가 — 스키마에 대고 센다.

    ★1차 정리가 `products`·`feedback_analytics_reports`·`knowledge_documents` 를
      빠뜨렸다. 목록을 `api_fixture` 의 cleanup 에서 **베껴 왔기** 때문이다.
      베낀 목록은 원본이 자라면 조용히 낡는다 — 이 프로젝트가 되풀이해 온
      바로 그 무늬다. 그래서 이제 **짐작하지 않고 스키마를 묻는다.**

    ★`tenants` 로의 FK 가 있는 표는 `customers` 하나뿐이다. 나머지는 테넌트 행을
      지워도 **살아남아 고아가 된다** — 빠뜨리면 안 지우느니만 못하다.
    """
    with conn.cursor() as cur:
        cur.execute("""SELECT table_name FROM information_schema.columns
                       WHERE table_schema='public' AND column_name='tenant_id'""")
        in_schema = {r[0] for r in cur.fetchall()}
    covered = {table for table, _ in DELETE_ORDER}
    missing = sorted(in_schema - covered)
    if missing:
        raise SystemExit(
            "★중단한다 — tenant_id 를 가진 표가 삭제 목록에 없다: "
            + ", ".join(missing)
            + "\n  빠뜨린 채 지우면 그 표의 행이 고아로 남는다. DELETE_ORDER 에 더한다.")


def _guard(conn) -> list[str]:
    """운영 테넌트가 이 패턴에 걸리면 **아무것도 하지 않는다.**

    ★설정된 `tenant_id` 가 접두어에 걸리면 이 스크립트는 실제 데이터를 지운다.
      그건 되돌릴 수 없다. 걸리면 그 자리에서 멈춘다.
    """
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
            path = directory / f"{table}.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            written[table] = len(rows)
    (directory / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prefixes": list(PREFIXES),
        # ★삭제 순서를 그대로 적는다. 복원은 이걸 뒤집어서 쓴다.
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
                    placeholders = ", ".join(["%s"] * len(columns))
                    cur.execute(
                        f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})',
                        values)
                    count += 1
                restored[table] = count
    return restored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="백업한 뒤 실제로 지운다. 없으면 세기만 한다(기본)")
    parser.add_argument("--restore", metavar="DIR",
                        help="백업 폴더를 되돌린다")
    args = parser.parse_args()

    if args.restore:
        directory = Path(args.restore)
        if not (directory / "manifest.json").is_file():
            raise SystemExit(f"★백업이 아니다 — manifest.json 이 없다: {directory}")
        with get_connection() as conn:
            restored = _restore(conn, directory)
        total = sum(restored.values())
        for table, n in restored.items():
            if n:
                print(f"   {table:20s} {n:6d}")
        print(f"복원했다: {total} 행  ({directory})")
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
                print(f"   {table:20s} {n:6d}")
        if not total:
            print("   (남은 것 없음)")
            return 0
        print(f"   {'합계':20s} {total:6d}")

        if not args.apply:
            print()
            print("★아무것도 지우지 않았다. 실제로 지우려면 --apply 를 준다.")
            print("  --apply 는 지우기 전에 백업한다. 되돌리려면 --restore <폴더>.")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        directory = BACKUP_ROOT / stamp
        written = _dump(conn, directory)
        if sum(written.values()) != total:
            # ★백업한 수와 지울 수가 다르면 **지우지 않는다.** 그 사이 뭔가
            #   바뀌었다는 뜻이고, 덜 받아 적은 백업으로는 되돌릴 수 없다.
            raise SystemExit(
                f"★중단한다 — 백업 {sum(written.values())} 행 ≠ 대상 {total} 행")
        print()
        print(f"백업: {directory}")

        # ★한 트랜잭션이다. 중간에 막히면 통째로 롤백되어 **반쯤 지워진 상태**가
        #   남지 않는다. FK 로 막히면 그 사실이 예외로 그대로 올라온다.
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
