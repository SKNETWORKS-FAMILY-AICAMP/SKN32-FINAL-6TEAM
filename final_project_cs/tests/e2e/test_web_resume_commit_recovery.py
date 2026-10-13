"""입력 커밋 후 실행 시작 전 중단도 실제 DB의 같은 답변 이벤트로 복구한다."""
import pytest

from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401
from .test_web_conversation_resume import _post, _say, _saved


def test_committed_valid_input_retries_same_event_with_one_resumed_and_application(decided, monkeypatch):
    first = _say(decided, "바꿔", "commit-recovery-initial")
    assert first["case_status"] == "waiting_input", first
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT item_id FROM itinerary_items WHERE trip_id=%s AND version=1 AND kind='dining'",
                    (decided["trip"]["trip_id"],))
        dining = {str(row[0]) for row in cur.fetchall()}
    choice = next(c for c in first["choices"] if c.get("item_id") in dining)
    controller = decided["client"].app.state.runtime.published_snapshot().controller
    original = controller.run_case
    interrupted = [False]

    async def run_case(**kwargs):
        if not interrupted[0]:
            interrupted[0] = True
            raise RuntimeError("synthetic interruption after VALID_INPUT commit")
        return await original(**kwargs)

    monkeypatch.setattr(controller, "run_case", run_case)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        _post(decided, choice["message"], "commit-recovery-answer", case_id=first["case_id"])
    assert _saved(first["case_id"])[0] == "resuming"
    # 초기 문장은 이미 소비한 답변 이벤트를 대신하지 않는다.
    assert _post(decided, "바꿔", "commit-recovery-initial").status_code == 409
    done = _post(decided, choice["message"], "commit-recovery-answer", case_id=first["case_id"])
    assert done.status_code == 200 and done.json()["case_status"] == "resolved", done.text
    assert done.json()["status"] == "adjusted", done.text
    assert _post(decided, choice["message"], "commit-recovery-answer").json()["status"] == "duplicate"
    state = _saved(first["case_id"])[3]
    assert state["customer_input_history"] == [choice["message"]]
    assert len(state["applied_actions"]) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type,count(*) FROM case_events WHERE case_id=%s "
                    "AND event_type IN ('valid_input','resumed') GROUP BY event_type", (first["case_id"],))
        assert dict(cur.fetchall()) == {"valid_input": 1, "resumed": 1}
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (f"{decided['trip']['trip_id']}:v2",))
        assert cur.fetchone()[0] == 1
