"""대기 업무가 독립 문의를 가로채지 않고 초기 실패를 같은 업무로 복구한다."""
import copy
from datetime import UTC, datetime, timedelta

from app.core.service_bindings import BindingTable
from app.infrastructure.db.session import get_connection
from .test_web_conversation_resume import _delay, _post, _saved, _say
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401


def _disable(decided, team):
    runtime = decided["client"].app.state.runtime
    old = runtime.published_snapshot()
    controller = copy.copy(old.controller)
    controller.registry = copy.copy(old.controller.registry)
    # 등록 구현의 연결·lock은 공유하고 등록표의 사전만 새 판으로 분리한다.
    for name, value in vars(old.controller.registry).items():
        if isinstance(value, dict):
            setattr(controller.registry, name, dict(value))
    controller.registry.declare_unavailable(team, "disabled")
    controller.service_bindings = BindingTable(dict(old.controller.service_bindings.values), controller.registry, old.revision)
    runtime.swap(controller, old.revision)
    return lambda: runtime.swap(old.controller, old.revision)


def _expire(case_id):
    # 시험 자료의 시간만 앞당긴다. 제품 상태 변경은 Controller의 WAIT_EXPIRED가 수행한다.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE customer_cases SET state_json=jsonb_set(state_json,'{resume_token_expires_at}',to_jsonb(%s::text)) "
                    "WHERE case_id=%s", ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), case_id))


def test_pending_delay_does_not_capture_a_new_fact_question(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "isolation-wait")
    before = _saved(first["case_id"])
    fact = _say(decided, "성수 점심 식당 알려줘", "isolation-fact")
    assert fact["case_id"] != first["case_id"] and fact["status"] == "answered", fact
    assert fact["decision"]["action"] == "answer_fact"
    assert _saved(first["case_id"]) == before
    reply = _say(decided, "30분이요", "isolation-answer")
    assert reply["case_id"] == first["case_id"] and reply["case_status"] == "resolved"


def test_pending_delay_does_not_capture_a_new_change_request(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "isolation-change-wait")
    before = _saved(first["case_id"])
    changed = _say(decided, "점심 다른 데로 바꿔", "isolation-change")
    assert changed["case_id"] != first["case_id"] and changed["status"] == "adjusted", changed
    assert _saved(first["case_id"]) == before


def test_disabled_pending_owner_allows_independent_fact_but_preserves_reply(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "isolation-disabled-wait")
    before = _saved(first["case_id"])
    enable = _disable(decided, "dining")
    fact = _post(decided, "성수 점심 식당 알려줘", "isolation-disabled-fact")
    assert fact.status_code == 200 and fact.json()["case_id"] != first["case_id"], fact.text
    assert _post(decided, "30분이요", "isolation-disabled-reply").status_code == 503
    assert _saved(first["case_id"]) == before
    enable()
    assert _say(decided, "30분이요", "isolation-disabled-reply")["case_id"] == first["case_id"]


def test_expired_implicit_reply_becomes_a_new_message_without_discarding_it(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "isolation-expired-wait")
    _expire(first["case_id"])
    reply = _post(decided, "30분이요", "isolation-expired-reply")
    assert reply.status_code == 200 and reply.json()["case_id"] != first["case_id"], reply.text
    assert _saved(first["case_id"])[0] == "escalated"
    assert not _saved(first["case_id"])[3].get("customer_input_history")


def test_expired_explicit_reply_retains_the_existing_token_error(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "isolation-explicit-expired-wait")
    _expire(first["case_id"])
    reply = _post(decided, "30분이요", "isolation-explicit-expired-reply", case_id=first["case_id"],
                  resume_token=first["resume_token"])
    assert reply.status_code == 401, reply.text
    assert _saved(first["case_id"])[0] == "escalated"


def test_two_pending_cases_allow_facts_and_a_short_reply_goes_to_the_latest_question(decided):
    """★`[2026-10-15 사용자 지시 — 코어]` 답을 기다리는 질문이 둘이어도 짧은 답(「30분이요」)은 거절하지 않고 **가장 나중에 보인 질문**의 건으로 잇는다(`case_dispatch.resume_pending`).
    앞 판은 409 를 기대했다. 먼저 만든 건은 그대로 답을 기다린다."""
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "isolation-multi-first")
    second = _say(decided, "식당에 늦어요", "isolation-multi-second")
    assert second["case_id"] != first["case_id"]
    before = [_saved(case["case_id"]) for case in (first, second)]
    assert _post(decided, "성수 점심 식당 알려줘", "isolation-multi-fact").status_code == 200
    assert _post(decided, "30분이요", "isolation-multi-reply").status_code == 200
    after = [_saved(case["case_id"]) for case in (first, second)]
    assert after[0] == before[0]
    assert after[1] != before[1]


def test_initial_disabled_request_retries_same_case_and_applies_once(decided):
    enable = _disable(decided, "dining")
    first = _post(decided, "점심 다른 데로 바꿔", "isolation-initial-retry")
    assert first.status_code == 503, first.text
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s",
                    ("isolation-initial-retry",))
        case_id = str(cur.fetchone()[0])
    assert _post(decided, "점심 다른 데로 바꿔", "isolation-initial-retry").status_code == 503
    enable()
    reply = _say(decided, "점심 다른 데로 바꿔", "isolation-initial-retry")
    assert reply["case_id"] == case_id and reply["status"] == "adjusted", reply
    assert _say(decided, "점심 다른 데로 바꿔", "isolation-initial-retry")["status"] == "duplicate"
    assert len(decided["decider"].prompts) == 1
    state = _saved(case_id)[3]
    assert len(state["applied_actions"]) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer_cases WHERE state_json->'trip_message'->>'request_id'=%s",
                    ("isolation-initial-retry",))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (f"{decided['trip']['trip_id']}:v2",))
        assert cur.fetchone()[0] == 1
