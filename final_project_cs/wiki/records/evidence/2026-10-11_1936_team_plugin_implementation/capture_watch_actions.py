"""합성 감시 시험 실패 때 action 기록의 실제 Case 범위만 보존한다."""
import json
from pathlib import Path

import pytest


class Capture:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        result = outcome.get_result()
        if result.when != "call" or not result.failed or "api" not in item.funcargs:
            return
        from app.infrastructure.db.session import get_connection

        api = item.funcargs["api"]
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT a.action_type,a.status,c.state_json->>'request_id',c.status "
                        "FROM action_requests a JOIN customer_cases c ON c.tenant_id=a.tenant_id AND c.case_id=a.case_id "
                        "WHERE a.tenant_id=%s", (api["tenant"],))
            actions = cur.fetchall()
            cur.execute("SELECT topic,dedupe_key FROM outbox WHERE tenant_id=%s", (api["tenant"],))
            notices = cur.fetchall()
        destination = Path(__file__).with_name("watch-action-scope.json")
        assert not destination.exists()
        destination.write_text(json.dumps({"actions": actions, "outbox": notices}, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
