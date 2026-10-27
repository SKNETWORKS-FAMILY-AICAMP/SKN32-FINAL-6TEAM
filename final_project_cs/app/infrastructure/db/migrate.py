"""Apply all SQL migrations, safely repeatable."""
from pathlib import Path
import argparse
from contextlib import contextmanager
import hashlib
import json
import sys
import threading
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


class MigrationAttemptTimeout(RuntimeError):
    """한 시도가 자기 제한 시간(`attempt_timeout_s`)을 넘어 취소 · 되돌려졌다 — 다시 하지 않는다.

    ★`[2026-10-28 독립 검토 · 실제 PostgreSQL 16]` `statement_timeout` 은 한 번에 보낸 여러 문장의 문장마다 걸려(PG13+)
      111개 SQL 한 시도를 묶지 못한다. 시도마다 따로 재는 이 제한이 시도 하나의 상한이다.
    """

    def __init__(self, *, sqlstate: str | None, attempts: int, limit_seconds: float):
        super().__init__(f"migration attempt {attempts} exceeded {limit_seconds}s sqlstate={sqlstate}")
        self.error, self.sqlstate, self.attempts = "MigrationAttemptTimeout", sqlstate, attempts
        self.migration_attempts = attempts


class _AttemptLimit:
    """시도 하나의 벽시계 제한. 넘으면 다른 스레드에서 서버에 취소를 보낸다. 끝난 뒤에는 절대 보내지 않는다."""

    def __init__(self, conn, seconds: float):
        self.fired, self._armed, self._lock = False, True, threading.Lock()
        self._conn = conn
        self._timer = threading.Timer(seconds, self._fire)
        self._timer.daemon = True

    def _fire(self) -> None:
        # 잠금을 쥔 채 취소를 보낸다 — disarm() 이 돌아온 뒤에는 늦은 취소가 다음 문장에 닿지 않는다
        with self._lock:
            if not self._armed:
                return
            self.fired = True
            cancel = getattr(self._conn, "cancel_safe", None) or self._conn.cancel
            try:
                cancel()
            except Exception:  # noqa: BLE001 - 취소 실패는 시도 쪽이 fired 로 보고 되돌린다
                pass

    def __enter__(self):
        self._timer.start()
        return self

    def __exit__(self, *exc) -> None:
        with self._lock:
            self._armed = False
        self._timer.cancel()


@contextmanager
def _no_limit():
    yield None


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


def apply_all(conn, *, sleep=time.sleep, attempt_timeout_s: float | None = None) -> None:
    """전체 사전검사 후 한 트랜잭션에 적용한다. 중첩 호출은 savepoint로 지원한다.

    실패하면 표·행 변경은 묶음 전체가 롤백된다. 성공한 중첩 호출의 최종 커밋은
    호출자 책임이다. SQL 원문은 유지하며 파일 바깥의 단순 BEGIN/COMMIT만 제거한다.

    ★`[2026-10-27]` 맨 바깥 호출(배포 job — x600 guard · 아마존 CD)은 매 시도 트랜잭션 안에서 `lock_timeout` 을 먼저 걸고,
      교착 · 잠금 대기 초과로 되돌려지면 `migration-plan.json` `lock_policy` 의 횟수만큼 다시 한다(2026-10-26 x600 교착 실패 두 번).
      그 밖의 오류는 다시 하지 않는다. 중첩 호출(바깥 트랜잭션 안)은 바깥 잠금을 쥔 채 다시 하지 않는다 — 한 번만.
    ★`[2026-10-28]` `attempt_timeout_s`(아마존 CD Job)를 주면 **시도마다 새로** 벽시계 제한을 건다(BEGIN 부터 COMMIT 까지).
      넘으면 서버에 취소를 보내 그 시도를 되돌리고 `MigrationAttemptTimeout` 으로 끝낸다(다시 하지 않는다). 그래서 최악 시간은
      `attempts × attempt_timeout_s + 사이 대기 합` 이다. COMMIT 도중 난 오류에는 `migration_commit_uncertain` 을 붙인다
      (반영됐는지 모른다 — 「되돌림 확정」으로 보고하지 않게).
    """
    if attempt_timeout_s is not None and (type(attempt_timeout_s) not in (int, float) or attempt_timeout_s <= 0):
        raise ValueError("attempt_timeout_s must be a positive number of seconds")
    sql = compiled_sql()
    if conn.info.transaction_status != TransactionStatus.IDLE:
        if attempt_timeout_s is not None:
            # 중첩 경로는 바깥 트랜잭션 안에서 한 번만 돈다 — 시도 제한을 걸 수 없으니 조용히 빼지 않고 거절한다
            raise ValueError("attempt_timeout_s needs an idle connection (outermost call)")
        with conn.transaction():
            conn.execute(sql)
        return
    policy = lock_policy(MIGRATION_DIR)
    attempts, waits = policy["attempts"], policy["retry_wait_seconds"]
    for attempt in range(1, attempts + 1):
        committing = False
        limit = None
        try:
            with (_AttemptLimit(conn, attempt_timeout_s) if attempt_timeout_s is not None else _no_limit()) as limit:
                with conn.transaction():
                    conn.execute(f"SET LOCAL lock_timeout = '{int(policy['lock_timeout_ms'])}ms'")
                    if limit is not None and limit.fired:
                        raise MigrationAttemptTimeout(sqlstate=None, attempts=attempt, limit_seconds=attempt_timeout_s)
                    conn.execute(sql)
                    if limit is not None and limit.fired:
                        # 취소가 문장 사이(유휴)에 닿아 무시됐어도 제한을 넘긴 시도는 커밋하지 않는다
                        raise MigrationAttemptTimeout(sqlstate=None, attempts=attempt, limit_seconds=attempt_timeout_s)
                    committing = True                       # 이 블록을 나가며 COMMIT 한다
            return
        except MigrationAttemptTimeout:
            raise
        except RETRYABLE as exc:
            if attempt == attempts:
                raise MigrationLockFailed(error=type(exc).__name__, sqlstate=exc.sqlstate, attempts=attempts) from exc
            _line(migration="retry", attempt=attempt, attempts=attempts, error=type(exc).__name__,
                  sqlstate=exc.sqlstate, wait_seconds=waits[attempt - 1])
            sleep(waits[attempt - 1])
        except BaseException as exc:
            # 다시 하지 않는 실패 — 몇 번째 시도에서 났는지만 붙여 그대로 올린다(배포 기록이 「시도 2」를 「1」로 적지 않게)
            if committing:
                exc.migration_commit_uncertain = True
            elif limit is not None and limit.fired and isinstance(exc, psycopg.errors.QueryCanceled):
                raise MigrationAttemptTimeout(sqlstate=exc.sqlstate, attempts=attempt,
                                              limit_seconds=attempt_timeout_s) from exc
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
