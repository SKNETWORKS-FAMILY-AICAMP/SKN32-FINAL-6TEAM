from __future__ import annotations

import argparse
import json
from datetime import date

from app.application.feedback_job import run_daily_feedback
from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    tenant_id = get_settings().tenant_id
    with get_connection() as conn, conn.transaction():
        report = run_daily_feedback(conn, report_date=args.date, tenant_id=tenant_id)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
