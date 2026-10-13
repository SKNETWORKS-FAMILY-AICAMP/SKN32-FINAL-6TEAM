"""Bounded replay of previously masked diagnostics; no customer messages or provider calls."""
import argparse
import json

from app.application.operations_diagnostics import Spool, prune
from app.application.operations_policy import configuration
from app.infrastructure.db.session import get_connection


def run_once(*, connection_factory=get_connection, spool=None, limit=None, prune_expired=False):
    """한정된 회차를 실행한다. 재전송 실패와 보존 정리 실패를 각각 드러낸다."""
    limit = configuration()["diagnostics"]["replay_limit"] if limit is None else limit
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("diagnostic_replay_limit_out_of_range")
    try:
        result = (spool if spool is not None else Spool()).replay(connection_factory, limit=limit)
    except Exception:
        # 디스크/DB 예외의 원문에는 개인 경로·접속 값이 섞일 수 있다.
        result = {"failed": 1, "collection_degraded": 1, "error_code": "DIAGNOSTIC_REPLAY_FAILED"}
    if prune_expired:
        try:
            with connection_factory() as conn, conn.transaction():
                result["pruned"] = prune(conn)
        except Exception:
            result["prune_failed"] = 1
    return result


def main():
    parser = argparse.ArgumentParser(description="진단 기록 재전송과 보존기한 정리")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 1000:
        parser.error("limit must be between 1 and 1000")
    result = run_once(connection_factory=get_connection, limit=args.limit, prune_expired=args.prune)
    print(json.dumps(result))
    return int(any(result.get(name, 0) for name in ("failed", "lost", "collection_degraded", "prune_failed")))


if __name__ == "__main__":
    raise SystemExit(main())
