"""Apply all SQL migrations, safely repeatable."""
from pathlib import Path
import argparse
import hashlib
import json

from app.infrastructure.db.session import get_connection
from app.infrastructure.db.migration_plan import migration_files
from app.infrastructure.db.migration_sql import atomic_sql

MIGRATION_DIR = Path(__file__).with_name("migrations")


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


def apply_all(conn) -> None:
    """전체 사전검사 후 한 트랜잭션에 적용한다. 중첩 호출은 savepoint로 지원한다.

    실패하면 표·행 변경은 묶음 전체가 롤백된다. 성공한 중첩 호출의 최종 커밋은
    호출자 책임이다. SQL 원문은 유지하며 파일 바깥의 단순 BEGIN/COMMIT만 제거한다.
    """
    sql = compiled_sql()
    with conn.transaction():
        conn.execute(sql)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate artifacts without connecting to DB")
    if parser.parse_args().check:
        print(json.dumps(safety_manifest(), sort_keys=True))
        return
    with get_connection() as conn:
        apply_all(conn)
    print(f"Applied migrations from {MIGRATION_DIR}")


if __name__ == "__main__":
    main()
