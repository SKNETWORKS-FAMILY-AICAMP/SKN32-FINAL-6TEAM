"""Apply all SQL migrations, safely repeatable."""
from pathlib import Path
import argparse
import hashlib
import json

from app.infrastructure.db.session import get_connection
from app.infrastructure.db.migration_plan import migration_files

MIGRATION_DIR = Path(__file__).with_name("migrations")


def apply_all(conn) -> None:
    """실행 계획에 포함된 현재 SQL만 파일명 순서대로 **한 트랜잭션**에서 돌린다. ★매번 전부 다시 돌기 때문에 파일마다
    「데이터가 있는 DB 에 다시 돌려도」 깨지지 않아야 한다(`tests/integration/db/test_migrations_rerun.py`)."""
    sql = "\n".join(p.read_text(encoding="utf-8") for p in migration_files(MIGRATION_DIR)[0])
    with conn.transaction():
        conn.execute(sql)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate the local migration plan without connecting to a database')
    args = parser.parse_args()
    if args.check:
        current, historical = migration_files(MIGRATION_DIR)
        print(json.dumps({'current': [{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                                      for p in current], 'historical':[p.name for p in historical]}))
        return
    with get_connection() as conn:
        apply_all(conn)
    print(f"Applied migrations from {MIGRATION_DIR}")


if __name__ == "__main__":
    main()
