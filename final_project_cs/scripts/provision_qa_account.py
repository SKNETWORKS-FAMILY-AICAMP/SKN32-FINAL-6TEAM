"""전용 QA 고객 하나와 본인 여행용 키를 만들고 이용 횟수 예외를 감사 기록에 남긴다."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.core.settings import get_settings
from app.domains.travel_ops.modules.web_account import qa_account
from app.domains.travel_ops.modules.web_account.web_session import add_key
from app.infrastructure.db.session import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", required=True, type=Path, help="Git 밖의 새 비공개 파일")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    if not args.actor.strip() or not args.reason.strip():
        parser.error("작업자·사유를 명시해야 합니다.")
    tenant = get_settings().tenant_id
    # 기존 자격 파일이 있으면 새 계정을 만들지 않는다. 키 원문은 출력하지 않는다.
    with os.fdopen(os.open(args.credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as output:
        with get_connection() as conn, conn.transaction():
            current = qa_account.status(conn, tenant)
            current = qa_account.change(conn, tenant, args.actor, enabled=True,
                                        expected_revision=current['revision'], reason=args.reason)
            customer = current['customer_id']
            key = add_key(conn, tenant_id=tenant, customer_id=customer)
            json.dump({"tenant_id": tenant, "customer_id": str(customer), "user_key": key}, output)
        print(json.dumps({"customer_id": str(customer), "usage_exempt": True}))


if __name__ == "__main__":
    main()
