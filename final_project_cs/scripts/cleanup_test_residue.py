"""테스트가 남긴 테넌트 잔재를 **세어 보여 준다.** 기본은 아무것도 안 지운다.

    python -m scripts.cleanup_test_residue            # 세기만 한다(기본)
    python -m scripts.cleanup_test_residue --apply    # 실제로 지운다

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
"""
from __future__ import annotations

import argparse
import sys

from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection

#: 테스트 픽스처가 쓰는 테넌트 접두어. ★여기 없는 것은 **건드리지 않는다.**
#:  `LIKE 'test%'` 같은 넓은 패턴을 쓰지 않는 이유는, 언젠가 `testbed` 처럼
#:  진짜 테넌트가 그 이름으로 생기면 조용히 지워 버리기 때문이다.
#:  ★`test\_api\_` 를 따로 넣지 않는다 — `test\_%` 가 이미 그것을 포함한다.
#:   처음엔 둘 다 넣었다가 **모든 수를 두 번 셌다**(2026-09-07, 테넌트 256을
#:   344로 보고했다). 겹치는 패턴은 세는 것도 지우는 것도 두 번 한다.
PREFIXES = ("test\\_", "live\\_classifier\\_")

#: FK 순서. ★하나라도 빠지면 트랜잭션이 통째로 롤백되어 **아무것도 안 지워진다.**
DELETE_ORDER = (
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
    return sorted({p for p in PREFIXES})


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="실제로 지운다. 없으면 세기만 한다(기본)")
    args = parser.parse_args()

    with get_connection() as conn:
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
            print("  ★지우기 전에 위 숫자를 사람이 본다 — 되돌릴 수 없다.")
            return 0

        # ★한 트랜잭션이다. 중간에 막히면 통째로 롤백되어 **반쯤 지워진 상태**가
        #   남지 않는다. FK 로 막히면 그 사실이 예외로 그대로 올라온다.
        with conn.transaction():
            with conn.cursor() as cur:
                for table, where in DELETE_ORDER:
                    for prefix in PREFIXES:
                        cur.execute(f"DELETE FROM {table} WHERE {where}", (prefix + "%",))
        print()
        print(f"지웠다: {total} 행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
