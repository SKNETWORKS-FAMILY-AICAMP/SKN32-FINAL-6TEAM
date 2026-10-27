"""Resolve current SQL inputs and preserve explicitly retired SQL as history."""
import json
from pathlib import Path

def migration_files(directory: Path) -> tuple[list[Path], list[Path]]:
    plan = json.loads((directory / "migration-plan.json").read_text(encoding="utf-8"))
    if plan.get("version") != 1:
        raise ValueError("Unsupported migration plan version")
    names = plan["historical_files"]
    if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
        raise ValueError("Historical SQL names must be a list of strings")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate historical SQL name")
    for name in names:
        if Path(name).name != name or "/" in name or "\\" in name or not name.endswith(".sql"):
            raise ValueError("Historical SQL must be a local SQL filename")
        if not (directory / name).is_file():
            raise ValueError(f"Missing historical SQL: {name}")
    historical = [directory / n for n in sorted(names)]
    return [p for p in sorted(directory.glob("*.sql")) if p.name not in names], historical


def lock_policy(directory: Path) -> dict:
    """마이그레이션 세션의 잠금 대기 제한 · 교착 재시도 값 — `migration-plan.json` 의 `lock_policy` 한 곳.

    `[2026-10-27]` 2026-10-26 x600 배포가 실서비스 폴링과의 교착으로 두 번 실패했다. 값이 없거나 틀리면 시작하지 않는다
    (코드에 박은 기본값으로 조용히 돌지 않는다). `retry_wait_seconds` 는 시도 사이 대기라 `attempts - 1` 개다.
    """
    plan = json.loads((directory / "migration-plan.json").read_text(encoding="utf-8"))
    policy = plan.get("lock_policy")
    if not isinstance(policy, dict) or set(policy) != {"lock_timeout_ms", "attempts", "retry_wait_seconds"}:
        raise ValueError("migration-plan.json lock_policy must define lock_timeout_ms, attempts, retry_wait_seconds")
    timeout, attempts, waits = policy["lock_timeout_ms"], policy["attempts"], policy["retry_wait_seconds"]
    if type(timeout) is not int or timeout <= 0:
        raise ValueError("lock_policy.lock_timeout_ms must be a positive integer")
    if type(attempts) is not int or attempts < 1:
        raise ValueError("lock_policy.attempts must be a positive integer")
    if (not isinstance(waits, list) or len(waits) != attempts - 1
            or any(type(w) not in (int, float) or w < 0 for w in waits)):
        raise ValueError("lock_policy.retry_wait_seconds must list attempts-1 nonnegative numbers")
    return policy
