"""초기 접수 커밋 뒤 필수 계산 실패를 실제 HTTP·합성 로컬 DB로 재현한다."""
import pytest

from app.core.team_availability import TeamUnavailable
from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401
from .test_web_conversation_resume import _post, _saved


@pytest.mark.parametrize("mode", ["on", "off"])
@pytest.mark.parametrize("stage", ["prepare", "team"])
def test_committed_initial_failure_reuses_saved_plan_without_model_reclassification(decided, monkeypatch, mode, stage):
    from app.application import classification
    from app.domains.travel_ops.components.conversation import trip_messages, case_dispatch

    monkeypatch.setattr(trip_messages, "_decision_mode", lambda *a, **k: mode)
    original_classify = classification.classify_case
    counts = {"classification": 0, "extraction": 0}

    def classify(*args, **kwargs):
        counts["classification"] += 1
        return original_classify(*args, **kwargs)

    def extract(*args, **kwargs):
        counts["extraction"] += 1
        return {"type": "change"}

    monkeypatch.setattr(classification, "classify_case", classify)
    monkeypatch.setattr(trip_messages, "extract", extract)
    blocked = [True]
    if stage == "prepare":
        original = case_dispatch._prepare_candidates

        def prepare(*args, **kwargs):
            if blocked[0]:
                raise TeamUnavailable("mobility", "engine_unavailable")
            return original(*args, **kwargs)

        monkeypatch.setattr(case_dispatch, "_prepare_candidates", prepare)
    else:
        executor = decided["client"].app.state.runtime.published_snapshot().controller.team_executor
        original_execute = executor.execute

        async def execute(task):
            if blocked[0]:
                raise TeamUnavailable("mobility", "engine_unavailable")
            return await original_execute(task)

        monkeypatch.setattr(executor, "execute", execute)
    request_id = f"committed-initial-{mode}-{stage}"
    first = _post(decided, "점심 다른 데로 바꿔", request_id)
    assert first.status_code == 503, first.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s", (request_id,))
        case_id = str(cur.fetchone()[0])
    before = _saved(case_id)
    plan = before[3]["conversation_dispatch"]
    assert plan["team_id"] == "dining" and plan["subject_ref"]["base_version"] == 1
    assert plan["subject_ref"]["request"]["action"] == "apply_change"
    assert before[0] == ("routing" if stage == "prepare" else "running")
    repeated = _post(decided, "점심 다른 데로 바꿔", request_id)
    assert repeated.status_code == 503, repeated.text
    assert _post(decided, "저녁 다른 데로 바꿔", request_id).status_code == 409
    blocked[0] = False
    done = _post(decided, "점심 다른 데로 바꿔", request_id)
    assert done.status_code == 200, done.text
    assert done.json()["case_id"] == case_id and done.json()["status"] == "adjusted", done.text
    duplicate = _post(decided, "점심 다른 데로 바꿔", request_id)
    assert duplicate.status_code == 200 and duplicate.json()["status"] == "duplicate"
    assert counts == {"classification": 1, "extraction": int(mode == "off")}
    assert len(decided["decider"].prompts) == int(mode == "on")
    assert len(_saved(case_id)[3]["applied_actions"]) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s", (request_id,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (f"{decided['trip']['trip_id']}:v2",))
        assert cur.fetchone()[0] == 1


def test_rule_mode_extraction_failure_keeps_classification_audit(decided, monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages
    from app.infrastructure.ollama_chat import OllamaError

    monkeypatch.setattr(trip_messages, "_decision_mode", lambda *a, **k: "off")

    def failed(*a, **k):
        raise OllamaError("synthetic extraction failure")

    monkeypatch.setattr(trip_messages, "extract", failed)
    answer = _post(decided, "점심 다른 데로 바꿔", "rule-extraction-failed")
    assert answer.status_code == 200 and answer.json()["case_status"] == "escalated", answer.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY aggregate_version",
                    (answer.json()["case_id"],))
        events = [row[0] for row in cur.fetchall()]
    assert events == ["created", "classified", "routing_failed"]


@pytest.mark.parametrize("mode", ["on", "off"])
def test_initial_retry_rejects_changed_itinerary_without_rebasing(decided, monkeypatch, mode):
    from app.domains.travel_ops.components.conversation import trip_messages, case_dispatch

    monkeypatch.setattr(trip_messages, "_decision_mode", lambda *a, **k: mode)
    monkeypatch.setattr(trip_messages, "extract", lambda *a, **k: {"type": "change"})
    original = case_dispatch._prepare_candidates
    blocked = [True]

    def prepare(*args, **kwargs):
        if blocked[0]:
            raise TeamUnavailable("mobility", "engine_unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(case_dispatch, "_prepare_candidates", prepare)
    request_id = f"stale-initial-{mode}"
    assert _post(decided, "점심 다른 데로 바꿔", request_id).status_code == 503
    blocked[0] = False
    changed = _post(decided, "점심 다른 데로 바꿔", f"new-change-{mode}")
    assert changed.status_code == 200 and changed.json()["status"] == "adjusted", changed.text
    again = _post(decided, "점심 다른 데로 바꿔", request_id)
    assert again.status_code == 409, again.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT state_json FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s", (request_id,))
        state = cur.fetchone()[0]
    assert state["conversation_dispatch"]["subject_ref"]["base_version"] == 1
    assert not state.get("applied_actions")


def test_initial_descriptor_and_created_event_keep_existing_redaction(decided, monkeypatch):
    from app.domains.travel_ops.components.conversation import case_dispatch

    def prepare(*args, **kwargs):
        raise TeamUnavailable("mobility", "engine_unavailable")

    monkeypatch.setattr(case_dispatch, "_prepare_candidates", prepare)
    original = decided["decider"].structured

    def structured(system, user, schema, *, num_predict=160):
        result = original(system, user, schema, num_predict=num_predict)
        result["question"] = "연락처 010-1234-5678, synthetic@example.org"
        return result

    decided["decider"].structured = structured
    result = _post(decided, "점심 다른 데로 바꿔 010-1234-5678 synthetic@example.org", "initial-redaction")
    assert result.status_code == 503, result.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id,subject,state_json FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s",
                    ("initial-redaction",))
        case_id, subject, state = cur.fetchone()
        cur.execute("SELECT payload_json FROM case_events WHERE case_id=%s ORDER BY aggregate_version", (case_id,))
        events = cur.fetchall()
    stored = str((subject, state, events))
    assert "010-1234-5678" not in stored and "synthetic@example.org" not in stored
    assert "010-****-5678" in stored and "s***@example.org" in stored
    assert "conversation_dispatch" in str(state)
