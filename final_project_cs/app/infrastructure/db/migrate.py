"""Apply all SQL migrations, safely repeatable."""
from pathlib import Path

from app.infrastructure.db.session import get_connection

MIGRATION_DIR = Path(__file__).with_name("migrations")


def apply_all(conn) -> None:
    """모든 마이그레이션을 번호 순서대로 **한 트랜잭션**에서 돌린다. ★매번 전부 다시 돌기 때문에 파일마다
    「데이터가 있는 DB 에 다시 돌려도」 깨지지 않아야 한다(`tests/integration/db/test_migrations_rerun.py`)."""
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted(MIGRATION_DIR.glob("*.sql")))
    with conn.transaction():
        conn.execute(sql)


def main() -> None:
    with get_connection() as conn:
        apply_all(conn)
    print(f"Applied migrations from {MIGRATION_DIR}")


if __name__ == "__main__":
    main()
