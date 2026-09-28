"""Apply all SQL migrations, safely repeatable."""
from pathlib import Path

from app.infrastructure.db.session import get_connection


def main() -> None:
    migration_dir = Path(__file__).with_name("migrations")
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted(migration_dir.glob("*.sql")))
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(sql)
    print(f"Applied migrations from {migration_dir}")


if __name__ == "__main__":
    main()
