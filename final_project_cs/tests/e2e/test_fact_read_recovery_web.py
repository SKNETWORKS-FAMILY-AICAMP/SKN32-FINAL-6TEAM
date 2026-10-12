"""합성 DB·실제 HTTP로 읽기 중단 복구와 질문 문맥 격리를 확인한다."""
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h  # noqa: F401
from .test_web_conversation_resume import _post, _saved


class ReadInterrupted(RuntimeError):
    pass


def _interrupt(decided, monkeypatch, stage, *, transform=None):
    from app.domains.travel_ops.components.conversation import trip_messages
    from app.domains.travel_ops.components.conversation.decision_unit import fact_first, labels
    from app.application.classification import classify_case
    from app.core.case_lifecycle.events import EventType
    from app.core.transition import transition_case
    from app.infrastructure.db import repository

    actual = trip_messages._run_decision

    def interrupted(conn, **kwargs):
        if stage in ("routing", "running"):
            decision = fact_first(kwargs["decision"])
            classify_case(conn, tenant_id=kwargs["tenant"], case_id=kwargs["case_id"],
                          text=kwargs["message"], classifier=lambda text: labels(decision), actor_id="read-test")
        if stage == "running":
            case = repository.get_case(conn, tenant_id=kwargs["tenant"], case_id=kwargs["case_id"])
            transition_case(conn, tenant_id=kwargs["tenant"], case_id=kwargs["case_id"], expected_version=case["version"],
                            event_type=EventType.ROUTED,
                            payload={"owner_team_id": "dining", "capability": "trip_desk.answer_fact"},
                            actor_type="api", actor_id="read-test")
        conn.commit()  # 실제 DB에 각 중단 지점을 남긴 뒤 요청 실행만 중단한다.
        raise ReadInterrupted("synthetic interruption; no customer data")

    if transform:
        original_open = trip_messages._open_message_case

        def create(conn, **kwargs):
            kwargs["extra"] = transform(dict(kwargs["extra"]))
            return original_open(conn, **kwargs)

        monkeypatch.setattr(trip_messages, "_open_message_case", create)
    monkeypatch.setattr(trip_messages, "_run_decision", interrupted)
    return actual


def _case_for(request_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s", (request_id,))
        rows = cur.fetchall()
    assert len(rows) == 1
    return str(rows[0][0])


def _public_conflict(response):
    assert response.status_code == 409, response.text
    assert response.json()["error"] == {
        "code": "state_conflict", "message": "업무 상태가 바뀌었거나 답변할 업무를 지정해야 합니다"}


def _unchanged(case_id, before):
    assert _saved(case_id) == before
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM agent_runs WHERE case_id=%s", (case_id,))
        assert cur.fetchone()[0] == 0


@pytest.mark.parametrize("stage", ["classifying", "routing", "running"])
def test_interrupted_read_reuses_same_case_original_input_and_one_completion(decided, monkeypatch, stage):
    from app.domains.travel_ops.components.conversation import trip_messages
    request = f"safe-read-{stage}"
    actual = _interrupt(decided, monkeypatch, stage)
    with pytest.raises(ReadInterrupted):
        _post(decided, "성수 점심 식당 알려줘", request)
    case_id = _case_for(request)
    saved = _saved(case_id)
    assert saved[0] == stage
    assert saved[3]["fact_read_snapshot"]["at"] == "2030-01-01T09:00:00+09:00"
    assert "location" not in saved[3]["fact_read_snapshot"]
    monkeypatch.setattr(trip_messages, "_run_decision", actual)
    # 재전송에서 바뀐 시각·선택을 사용하지 않는다.
    answer = _post(decided, "성수 점심 식당 알려줘", request,
                   at="2035-01-01T20:00:00+09:00", item_id=str(uuid4()))
    assert answer.status_code == 200, answer.text
    assert answer.json()["case_id"] == case_id and answer.json()["case_status"] == "resolved"
    assert "성수 점심" in answer.json()["answer"]
    again = _post(decided, "성수 점심 식당 알려줘", request)
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    assert again.json()["choices"] == answer.json()["choices"]
    assert len(decided["decider"].prompts) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY aggregate_version", (case_id,))
        assert [r[0] for r in cur.fetchall()] == ["created", "classified", "routed", "completed"]
        cur.execute("SELECT count(*) FROM agent_runs WHERE case_id=%s", (case_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 1


@pytest.mark.parametrize("kind", ["no_snapshot", "location", "business_snapshot"])
def test_unsupported_interrupted_read_requires_new_request_without_business_execution(decided, monkeypatch, kind):
    from app.domains.travel_ops.components.conversation import trip_messages
    request = f"unsafe-read-{kind}"
    transform = None
    text = "성수 점심 식당 알려줘"
    if kind == "no_snapshot":
        def transform(extra):
            extra.pop("fact_read_snapshot")
            return extra
    elif kind == "location":
        text = "지금 위치에서 성수 점심 가는 길"
    else:
        def transform(extra):
            extra["decision"]["action"] = "apply_change"
            return extra
    actual = _interrupt(decided, monkeypatch, "classifying", transform=transform)
    with pytest.raises(ReadInterrupted):
        _post(decided, text, request)
    case_id = _case_for(request)
    before = _saved(case_id)
    monkeypatch.setattr(trip_messages, "_run_decision", actual)
    response = _post(decided, text, request)
    _public_conflict(response)
    _unchanged(case_id, before)
    assert len(decided["decider"].prompts) == 1


def test_legacy_cached_read_answer_is_returned_without_reclassification(decided, monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages
    def legacy(extra):
        extra.pop("fact_read_snapshot")
        extra["answer"] = "보관된 성수 점심 상세 안내"
        return extra
    actual = _interrupt(decided, monkeypatch, "classifying", transform=legacy)
    with pytest.raises(ReadInterrupted):
        _post(decided, "성수 점심 식당 알려줘", "legacy-read-cache")
    monkeypatch.setattr(trip_messages, "_run_decision", actual)
    response = _post(decided, "성수 점심 식당 알려줘", "legacy-read-cache")
    assert response.status_code == 200 and response.json()["answer"] == "보관된 성수 점심 상세 안내"
    assert len(decided["decider"].prompts) == 1


def test_legacy_off_defer_stored_answer_has_no_model_decision_and_is_not_reexecuted(decided, monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages

    def old_off(extra):
        extra.pop("fact_read_snapshot")
        extra.pop("decision")
        extra["answer"] = "저장된 성수 점심 안내"
        return extra

    actual = _interrupt(decided, monkeypatch, "classifying", transform=old_off)
    with pytest.raises(ReadInterrupted):
        _post(decided, "성수 점심 식당 자세히 알려줘", "legacy-off-defer-read")
    monkeypatch.setattr(trip_messages, "_run_decision", actual)
    response = _post(decided, "성수 점심 식당 자세히 알려줘", "legacy-off-defer-read")
    assert response.status_code == 200 and response.json()["answer"] == "저장된 성수 점심 안내", response.text
    assert len(decided["decider"].prompts) == 1


def test_changed_itinerary_does_not_rebase_interrupted_fact_read(decided, api, monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages
    actual = _interrupt(decided, monkeypatch, "routing")
    with pytest.raises(ReadInterrupted):
        _post(decided, "성수 점심 식당 알려줘", "read-old-version")
    case_id = _case_for("read-old-version")
    before = _saved(case_id)
    with get_connection() as conn, conn.transaction():
        trip, items = api["store"].latest(conn, UUID(decided["trip"]["trip_id"]))
        api["store"].append_version(conn, trip_id=trip["trip_id"], base_version=trip["version"],
                                    items=[replace(i) for i in items], reason="read_recovery_test", causes=[])
    monkeypatch.setattr(trip_messages, "_run_decision", actual)
    response = _post(decided, "성수 점심 식당 알려줘", "read-old-version")
    _public_conflict(response)
    _unchanged(case_id, before)
    assert len(decided["decider"].prompts) == 1


def test_same_read_lock_conflict_returns_409_without_waiting_or_consuming_case(decided, monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages
    actual = _interrupt(decided, monkeypatch, "classifying")
    with pytest.raises(ReadInterrupted):
        _post(decided, "성수 점심 식당 알려줘", "read-lock")
    case_id = _case_for("read-lock")
    before = _saved(case_id)
    monkeypatch.setattr(trip_messages, "_run_decision", actual)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id FROM customer_cases WHERE case_id=%s FOR UPDATE", (case_id,))
        assert cur.fetchone()
        response = _post(decided, "성수 점심 식당 알려줘", "read-lock")
        _public_conflict(response)
    _unchanged(case_id, before)
    assert len(decided["decider"].prompts) == 1
    assert _post(decided, "성수 점심 식당 알려줘", "read-lock").status_code == 200


@pytest.mark.parametrize("phase,change_on", [("context", 2), ("fresh", 3)])
def test_version_changes_between_handle_and_read_queries_do_not_consume_case(
        decided, api, monkeypatch, phase, change_on):
    from app.domains.travel_ops.components.conversation import trip_messages
    from app.domains.travel_ops.components.itinerary.itinerary import TripStore

    request = f"read-version-gap-{phase}"
    actual_run = _interrupt(decided, monkeypatch, "classifying")
    with pytest.raises(ReadInterrupted):
        _post(decided, "성수 점심 식당 알려줘", request)
    case_id = _case_for(request)
    before = _saved(case_id)
    monkeypatch.setattr(trip_messages, "_run_decision", actual_run)
    actual_latest = TripStore.latest
    calls = []

    def latest(store, connection, trip_id):
        if str(trip_id) == decided["trip"]["trip_id"]:
            calls.append(str(trip_id))
            if len(calls) == change_on:
                # 별도 실제 DB 연결이 판을 바꾼다. 조회 결과만 꾸미지 않는다.
                with get_connection() as writer, writer.transaction():
                    trip, items = actual_latest(store, writer, trip_id)
                    store.append_version(writer, trip_id=trip["trip_id"], base_version=trip["version"],
                                         items=[replace(i) for i in items],
                                         reason="read_version_gap_test", causes=[])
        return actual_latest(store, connection, trip_id)

    monkeypatch.setattr(TripStore, "latest", latest)
    response = _post(decided, "성수 점심 식당 알려줘", request)
    _public_conflict(response)
    _unchanged(case_id, before)
    assert len(calls) == change_on
    assert len(decided["decider"].prompts) == 1
    with get_connection() as conn:
        trip, _ = actual_latest(api["store"], conn, UUID(decided["trip"]["trip_id"]))
        assert trip["version"] == 2


def test_component_lookup_rollback_does_not_rollback_case_transitions(decided, monkeypatch):
    from app.domains.travel_ops.components.conversation import trip_messages

    calls = []

    def rollback_extras(connection, *args):
        calls.append(connection)
        connection.rollback()
        return ""

    monkeypatch.setattr(trip_messages, "_place_extras", rollback_extras)
    response = _post(decided, "성수 점심 식당 알려줘", "read-extra-rollback")
    assert response.status_code == 200, response.text
    assert response.json()["case_status"] == "resolved"
    assert len(calls) == 1 and len(decided["decider"].prompts) == 1
    case_id = response.json()["case_id"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT event_type FROM case_events WHERE case_id=%s ORDER BY aggregate_version", (case_id,))
        assert [r[0] for r in cur.fetchall()] == ["created", "classified", "routed", "completed"]
        cur.execute("SELECT count(*) FROM agent_runs WHERE case_id=%s", (case_id,))
        assert cur.fetchone()[0] == 0
