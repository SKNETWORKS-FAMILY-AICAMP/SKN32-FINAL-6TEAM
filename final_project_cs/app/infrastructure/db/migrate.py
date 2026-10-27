"""Apply all SQL migrations, safely repeatable."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

import psycopg
from psycopg.pq import TransactionStatus

from app.infrastructure.db.session import get_connection
from app.infrastructure.db.migration_plan import lock_policy, migration_files
from app.infrastructure.db.migration_sql import atomic_sql

MIGRATION_DIR = Path(__file__).with_name("migrations")
#: PostgreSQL 이 트랜잭션 전체를 되돌린 것이 **확정**인 잠금 실패 — 교착(40P01) · 잠금 대기 초과(55P03). 이것만 다시 한다.
RETRYABLE = (psycopg.errors.DeadlockDetected, psycopg.errors.LockNotAvailable)


class MigrationLockFailed(RuntimeError):
    """정해진 횟수만큼 잠금 실패(교착 · 잠금 대기 초과)로 되돌려졌다 — 표 · 행 변경은 하나도 남지 않았다."""

    def __init__(self, *, error: str, sqlstate: str | None, attempts: int):
        super().__init__(f"migration lock failure {error} sqlstate={sqlstate} attempts={attempts}")
        self.error, self.sqlstate, self.attempts = error, sqlstate, attempts


def _line(**fields) -> None:
    # 배포 기록(deploy.log · 파드 로그)이 읽는 한 줄 — 종류 · SQLSTATE · 횟수만. 오류 메시지 · SQL 은 싣지 않는다
    print(json.dumps(fields, ensure_ascii=False), flush=True)


def compiled_sql() -> str:
    return "\n".join(atomic_sql(p.read_text(encoding="utf-8"), p.name)
                     for p in migration_files(MIGRATION_DIR)[0])


def safety_manifest() -> dict:
    """Read-only artifact check, with no DB connection (also used at build time)."""
    current, historical = migration_files(MIGRATION_DIR)
    required = {"002_domain_commerce.sql", "006_products_catalog.sql",
                "007_returns_order_item.sql", "008_products_return_restriction.sql"}
    if {p.name for p in historical} != required:
        raise ValueError("Required historical migration exclusions differ")
    compiled_sql()
    paths = [Path(__file__), Path(__file__).with_name("migration_plan.py"),
             Path(__file__).with_name("migration_sql.py"), MIGRATION_DIR / "migration-plan.json",
             *current, *historical]
    return {"contract_version": 2, "historical": sorted(required), "current_count": len(current),
            "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def apply_all(conn, *, sleep=time.sleep) -> None:
    """전체 사전검사 후 한 트랜잭션에 적용한다. 중첩 호출은 savepoint로 지원한다.

    실패하면 표·행 변경은 묶음 전체가 롤백된다. 성공한 중첩 호출의 최종 커밋은
    호출자 책임이다. SQL 원문은 유지하며 파일 바깥의 단순 BEGIN/COMMIT만 제거한다.

    ★`[2026-10-27]` 맨 바깥 호출(배포 job — x600 guard · 아마존 CD)은 매 시도 트랜잭션 안에서 `lock_timeout` 을 먼저 걸고,
      교착 · 잠금 대기 초과로 되돌려지면 `migration-plan.json` `lock_policy` 의 횟수만큼 다시 한다(2026-10-26 x600 교착 실패 두 번).
      그 밖의 오류는 다시 하지 않는다. 중첩 호출(바깥 트랜잭션 안)은 바깥 잠금을 쥔 채 다시 하지 않는다 — 한 번만.
    """
    sql = compiled_sql()
    if conn.info.transaction_status != TransactionStatus.IDLE:
        with conn.transaction():
            conn.execute(sql)
        return
    policy = lock_policy(MIGRATION_DIR)
    attempts, waits = policy["attempts"], policy["retry_wait_seconds"]
    for attempt in range(1, attempts + 1):
        try:
            with conn.transaction():
                conn.execute(f"SET LOCAL lock_timeout = '{int(policy['lock_timeout_ms'])}ms'")
                conn.execute(sql)
            return
        except RETRYABLE as exc:
            if attempt == attempts:
                raise MigrationLockFailed(error=type(exc).__name__, sqlstate=exc.sqlstate, attempts=attempts) from exc
            _line(migration="retry", attempt=attempt, attempts=attempts, error=type(exc).__name__,
                  sqlstate=exc.sqlstate, wait_seconds=waits[attempt - 1])
            sleep(waits[attempt - 1])
        except BaseException as exc:
            # 다시 하지 않는 실패 — 몇 번째 시도에서 났는지만 붙여 그대로 올린다(배포 기록이 「시도 2」를 「1」로 적지 않게)
            exc.migration_attempts = attempt
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate artifacts without connecting to DB")
    if parser.parse_args().check:
        print(json.dumps(safety_manifest(), sort_keys=True))
        return
    try:
        with get_connection() as conn:
            apply_all(conn)
    except MigrationLockFailed as exc:
        _line(migration="failed", error=exc.error, sqlstate=exc.sqlstate, attempts=exc.attempts)
        sys.exit(1)
    except (psycopg.Error, ValueError) as exc:
        # ★실패 원인을 배포 기록에 남긴다 — 종류 · SQLSTATE · 시도 횟수만(메시지에는 표 이름 · 값 · 접속 정보가 섞일 수 있다).
        #   ValueError 는 산출물 · lock_policy 검사 실패다(시도 0 — SQL 을 보내기 전)
        _line(migration="failed", error=type(exc).__name__, sqlstate=getattr(exc, "sqlstate", None),
              attempts=getattr(exc, "migration_attempts", 0 if isinstance(exc, ValueError) else 1))
        sys.exit(1)
    print(f"Applied migrations from {MIGRATION_DIR}")


if __name__ == "__main__":
    main()
