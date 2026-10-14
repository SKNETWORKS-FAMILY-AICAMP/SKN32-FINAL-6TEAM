"""합성 시험 실패의 응답·업무 상태만 보존한다. 사용자 키는 수집하지 않는다."""
import json
from pathlib import Path

import pytest


class Capture:
    def pytest_runtest_makereport(self, item, call):
        if call.excinfo is None:
            return
        for frame in call.excinfo.traceback:
            body = frame.frame.f_locals.get("body")
            api = frame.frame.f_locals.get("api")
            if not isinstance(body, dict) or not body.get("case_id") or not isinstance(api, dict):
                continue
            from app.infrastructure.db.session import get_connection
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT status,state_json FROM customer_cases WHERE case_id=%s", (body["case_id"],))
                row = cur.fetchone()
                cur.execute("SELECT event_type,payload_json FROM case_events WHERE case_id=%s ORDER BY aggregate_version", (body["case_id"],))
                events = cur.fetchall()
            payload = {"body": body, "status": row[0], "state": row[1], "events": events}
            target = Path(__file__).with_name("web-chat-response-and-state-v2.json")
            if target.exists():
                raise RuntimeError("evidence already exists")
            target.write_text(json.dumps(payload, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
            break


if __name__ == "__main__":
    raise SystemExit(pytest.main(["tests/e2e/test_web_api.py::test_a_change_request_still_answers_with_what_happened", "-q", "--tb=short"], plugins=[Capture()]))
