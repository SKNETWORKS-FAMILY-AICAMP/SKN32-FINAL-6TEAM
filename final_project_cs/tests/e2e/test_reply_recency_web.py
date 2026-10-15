"""실제 HTTP·합성 DB에서 숫자 답의 대상과 이전 질문 보존을 검증한다."""
from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided  # noqa: F401
from .test_web_api import api, _fresh_limit_cache  # noqa: F401
from .test_web_conversation_resume import _say, _post, _saved


def _pending(decided, suffix):
    first = _say(decided, "바꿔", f"recency-{suffix}-question")
    assert first["case_status"] == "waiting_input" and first["choices"], first
    return first


def test_number_after_fact_keeps_old_case_and_wait_token_unchanged(decided):
    first = _pending(decided, "fact")
    before = _saved(first["case_id"])
    fact = _say(decided, "성수 점심 식당 알려줘", "recency-fact-read")
    assert fact["status"] == "answered" and fact["case_id"] != first["case_id"], fact
    reply = _post(decided, "1번", "recency-fact-number")
    assert reply.status_code == 200, reply.text
    assert reply.json()["case_id"] != first["case_id"], reply.json()
    assert _saved(first["case_id"]) == before
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 1


def test_explicit_old_question_can_resume_after_fact_and_replay_once(decided):
    first = _pending(decided, "explicit")
    _say(decided, "성수 점심 식당 알려줘", "recency-explicit-fact")
    reply = _say(decided, "1번", "recency-explicit-reply", case_id=first["case_id"],
                 resume_token=first["resume_token"], expected_version=first["version"])
    assert reply["case_id"] == first["case_id"], reply
    after = _saved(first["case_id"])
    assert after[3]["customer_input_history"] == ["1번"]
    again = _say(decided, "1번", "recency-explicit-reply")
    assert again["case_id"] == first["case_id"] and again["status"] == "duplicate", again
    assert _saved(first["case_id"]) == after


def test_number_for_the_latest_question_resumes_its_same_case(decided):
    first = _pending(decided, "latest")
    reply = _say(decided, "1번", "recency-latest-reply")
    assert reply["case_id"] == first["case_id"], reply
    assert _saved(first["case_id"])[3]["customer_input_history"] == ["1번"]
