"""환경 점검 — 매 Phase 시작 시 실행한다.

무엇이 되고 무엇이 안 되는지를 있는 그대로 출력한다.
★안 되는 것을 "아마 될 것"으로 넘기지 않는다(RULE.md §1.2).

    python -m scripts.check_env
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CHECKS: list[tuple[str, str]] = []  # (라벨, 결과문자열) — 실패도 그대로 싣는다
FAILED = 0


def record(label: str, ok: bool, detail: str) -> None:
    global FAILED
    mark = "OK  " if ok else "FAIL"
    if not ok:
        FAILED += 1
    CHECKS.append((f"[{mark}] {label}", detail))


def check_python() -> None:
    v = sys.version_info
    record("python", v >= (3, 12), f"{v.major}.{v.minor}.{v.micro}")


def check_settings() -> None:
    try:
        from acop_basement.core.settings import get_settings

        s = get_settings()
        record("settings(.env)", True, f"env={s.env} tenant={s.tenant_id} model={s.llm_model}")
        record(
            "openai key",
            bool(s.openai_api_key),
            f"len={len(s.openai_api_key)}" if s.openai_api_key else "비어 있음",
        )
    except Exception as exc:  # noqa: BLE001 — 무엇이 왜 실패했는지 그대로 보여준다
        record("settings(.env)", False, f"{type(exc).__name__}: {exc}")
        record("openai key", False, "settings 실패로 확인 불가")


def check_guardrails() -> None:
    try:
        from acop_basement.core.settings import get_guardrails

        g = get_guardrails()
        budget = g.get("context.token_budget")
        sections = g.get("context.sections")
        total = sum(sections.values())
        record("guardrails 로드", True, f"{g.source.name} (token_budget={budget})")
        # ★섹션 합이 총 예산과 다르면 그 자체가 결함이다 (v5 §9-1)
        record(
            "토큰 예산 정합",
            total == budget,
            f"섹션 합 {total} vs token_budget {budget}",
        )
        record(
            "임베딩 차원",
            g.get("rag.embedding_dim") == 1536,
            f"{g.get('rag.embedding_dim')} (DDL vector(1536) 과 일치해야 함)",
        )
    except Exception as exc:  # noqa: BLE001
        record("guardrails 로드", False, f"{type(exc).__name__}: {exc}")


def check_db() -> None:
    try:
        import psycopg

        from acop_basement.core.settings import get_settings

        dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("select version()")
            ver = cur.fetchone()[0].split(",")[0]
            record("PostgreSQL 연결", True, ver)

            cur.execute("select extname from pg_extension")
            installed = {r[0] for r in cur.fetchall()}
            cur.execute(
                "select name from pg_available_extensions where name in ('vector','pgcrypto')"
            )
            available = {r[0] for r in cur.fetchall()}
            for ext in ("vector", "pgcrypto"):
                if ext in installed:
                    record(f"extension {ext}", True, "설치됨")
                elif ext in available:
                    record(f"extension {ext}", False, "available 이지만 미설치 — 마이그레이션 필요")
                else:
                    record(f"extension {ext}", False, "available 하지 않음")

            cur.execute(
                "select count(*) from information_schema.tables where table_schema='public'"
            )
            record("테이블", True, f"public 스키마 {cur.fetchone()[0]}개")
    except Exception as exc:  # noqa: BLE001
        record("PostgreSQL 연결", False, f"{type(exc).__name__}: {exc}")


def check_baseline_hash() -> None:
    """DoD 1 — 원본 v4 계획서가 변경되지 않았다."""
    import hashlib

    original = REPO_ROOT.parent / "A-COP_구현계획서(4).md"
    if not original.is_file():
        record("v4 원본 존재", False, f"찾을 수 없음: {original}")
        return
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    record("v4 원본 존재", True, f"sha256={digest[:16]}... ({original.stat().st_size} bytes)")


def main() -> int:
    check_python()
    check_settings()
    check_guardrails()
    check_db()
    check_baseline_hash()

    width = max(len(label) for label, _ in CHECKS)
    print("=" * (width + 60))
    print("A-COP 환경 점검")
    print("=" * (width + 60))
    for label, detail in CHECKS:
        print(f"{label.ljust(width)}  {detail}")
    print("=" * (width + 60))
    print(f"실패 {FAILED}건 / 전체 {len(CHECKS)}건")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
