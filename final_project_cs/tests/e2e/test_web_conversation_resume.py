"""실제 등록 팀·로컬 DB로 웹의 같은 업무 재개와 단일 적용을 확인한다."""
from uuid import uuid4

from app.infrastructure.db.session import get_connection
from .test_decision_unit_web import decided, _say as _decision_say  # noqa: F401
from .test_web_api import api, _fresh_limit_cache, _h  # noqa: F401
from tests.helpers import relative_dates as reldate

# ★`[2026-10-28]` 박아 둔 날짜는 실행 날 기준으로 옮긴다 — 전부-과거 가드(`all_dates_before_today`)가 실제 시계를 읽는다.
#   요일 · 순서 · 간격은 원래 자료와 같다(`tests/helpers/relative_dates.py`).
D_2026_09_23 = reldate.day("2026-09-23")


def _say(decided, text, request_id, **fields):
    return _decision_say(decided, text, request_id,
                         **{"at": f"{D_2026_09_23}T12:30:00+09:00", **fields})


def _delay(decided):
    original = decided["decider"].structured

    def structured(system, user, schema, *, num_predict=160):
        if user.rsplit("고객 문장:", 1)[-1].strip() == "식당에 늦어요":
            decided["decider"].prompts.append(user)
            return {"action": "report_delay", "target_item": "none", "target_change": "none",
                    "fact": "none", "minutes": 0, "question": "몇 분쯤 늦으세요?"}
        return original(system, user, schema, num_predict=num_predict)
    decided["decider"].structured = structured


def _saved(case_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status,version,owner_team_id,state_json FROM customer_cases WHERE case_id=%s", (case_id,))
        return cur.fetchone()


def _post(decided, text, request_id, **fields):
    return decided["client"].post(f"/v1/web/trips/{decided['trip']['trip_id']}/messages",
                                 headers=_h(decided["key"]), json={"request_id": request_id, "message": text,
                                    "at": "2030-01-01T09:00:00+09:00", **fields})


def test_missing_minutes_waits_and_reply_reaches_same_real_team(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "resume-start")
    assert first["case_status"] == "waiting_input" and first["resume_token"]
    assert "minutes" in first["required_input_schema"]["required"]
    before = _saved(first["case_id"])
    assert first["resume_token"] not in str(before[3])
    invalid = _say(decided, "아직 몰라요", "resume-unknown", case_id=first["case_id"],
                   resume_token=first["resume_token"], expected_version=first["version"])
    assert invalid["case_status"] == "waiting_input" and invalid["case_id"] == first["case_id"]
    answer = _say(decided, "30분이요", "resume-valid", case_id=first["case_id"],
                  resume_token=invalid["resume_token"], expected_version=invalid["version"])
    assert answer["case_id"] == first["case_id"] and answer["case_status"] == "resolved", (answer, _saved(first["case_id"]))
    after = _saved(first["case_id"])
    assert after[2] == "dining" and after[3]["customer_input"] == "30분이요"
    assert after[3]["customer_input_history"] == ["아직 몰라요", "30분이요"]
    # ★`[2026-10-13]` 형식에 안 맞는 답(「아직 몰라요」)은 새 요청인지 해석 모델이 한 번 읽어 본다 — 완결된 요청이 아니라서 대기 건의 답으로 넘긴다.
    #   형식에 맞는 답(「30분이요」)은 모델을 다시 부르지 않는다.
    assert len(decided["decider"].prompts) == 2
    assert decided["decider"].prompts[1].rsplit("고객 문장:", 1)[1].strip() == "아직 몰라요"


def test_initial_request_retry_does_not_consume_waiting_token(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "resume-first-retry")
    before = _saved(first["case_id"])
    again = _say(decided, "식당에 늦어요", "resume-first-retry")
    assert again["status"] == "duplicate" and _saved(first["case_id"]) == before
    assert _post(decided, "다른 답변", "resume-first-retry").status_code == 409
    assert _saved(first["case_id"]) == before


def test_authenticated_web_reply_after_refresh_does_not_require_raw_token(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "resume-refresh-start")
    reply = _say(decided, "30분이요", "resume-refresh-answer")
    assert reply["case_id"] == first["case_id"] and reply["case_status"] == "resolved", (reply, _saved(first["case_id"]))


def test_bad_token_and_stale_version_preserve_pending_case(decided):
    _delay(decided)
    first = _say(decided, "식당에 늦어요", "resume-security-start")
    before = _saved(first["case_id"])
    assert _post(decided, "30분이요", "resume-bad-token", case_id=first["case_id"], resume_token="wrong").status_code == 401
    assert _saved(first["case_id"]) == before
    assert _post(decided, "30분이요", "resume-stale", case_id=first["case_id"], expected_version=0).status_code == 409
    assert _saved(first["case_id"]) == before
    assert _post(decided, "30분이요", "resume-other-case", case_id=str(uuid4())).status_code == 404


def test_change_uses_team_proposal_and_duplicate_does_not_apply_or_notify_twice(decided):
    first = _say(decided, "점심 다른 데로 바꿔", "resume-single-change")
    assert first["status"] == "adjusted" and first["outcome"]["version"] == 2, first
    state = _saved(first["case_id"])[3]
    assert len(state["applied_actions"]) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM agent_runs WHERE case_id=%s", (first["case_id"],))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT action_type,count(*) FROM action_requests WHERE case_id=%s AND status='succeeded' "
                    "GROUP BY action_type", (first["case_id"],))
        assert dict(cur.fetchall()) == {"case.create": 1, "itinerary.apply": 1}
    for _ in range(3):
        assert _say(decided, "점심 다른 데로 바꿔", "resume-single-change")["status"] == "duplicate"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM outbox WHERE dedupe_key=%s", (f"{decided['trip']['trip_id']}:v2",))
        assert cur.fetchone()[0] == 1


def test_target_reply_can_route_same_case_to_another_registered_team(decided):
    first = _say(decided, "바꿔", "resume-cross-start")
    assert first["case_status"] == "waiting_input"
    choices = first["choices"]
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT item_id,kind FROM itinerary_items WHERE trip_id=%s AND version=1", (decided["trip"]["trip_id"],))
        kinds = {str(row[0]): row[1] for row in cur.fetchall()}
    initial = _saved(first["case_id"])[2]
    target = next((c for c in choices if kinds.get(c.get("item_id")) != initial), None)
    assert target is not None, choices
    answer = _say(decided, target["message"], "resume-cross-reply", case_id=first["case_id"])
    assert answer["case_id"] == first["case_id"] and answer["case_status"] == "resolved", answer
    assert _saved(first["case_id"])[2] == kinds[target["item_id"]]


def test_free_text_reply_is_interpreted_once_and_routes_to_dining(decided):
    first = _say(decided, "바꿔", "resume-free-start")
    calls = []

    def extract(system, text):
        calls.append(text)
        return {"type": "delay", "minutes": 30}

    decided["decider"].json = extract
    reply = _say(decided, "점심에 30분 늦어요", "resume-free-answer", case_id=first["case_id"])
    assert reply["case_id"] == first["case_id"] and reply["case_status"] == "resolved", reply
    assert _saved(first["case_id"])[2] == "dining"
    assert calls == ["점심에 30분 늦어요"]


def test_alternative_selection_resumes_the_same_case_and_applies_once(decided):
    def propose(system, user, schema, *, num_predict=160):
        return {"action": "propose_alternatives", "target_item": decided["decider"]._alias(user, "성수 점심"),
                "target_change": "none", "fact": "none", "minutes": 0, "choices": []}

    decided["decider"].structured = propose
    first = _say(decided, "점심 다른 데 알아봐 줘", "resume-options-start")
    assert first["case_status"] == "waiting_input" and first["status"] == "asked", first
    reply = _say(decided, "1번", "resume-options-answer", case_id=first["case_id"])
    assert reply["case_id"] == first["case_id"] and reply["status"] == "adjusted", reply
    assert reply["case_status"] == "resolved" and reply["outcome"]["version"] == 2
    assert _say(decided, "1번", "resume-options-answer")["status"] == "duplicate"


def test_delayed_protected_meal_keeps_itinerary_and_answers_with_actual_question(decided):
    _delay(decided)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE itinerary_items SET locked=true WHERE trip_id=%s AND version=1 AND title LIKE '성수 점심%%'",
                    (decided["trip"]["trip_id"],))
    first = _say(decided, "식당에 늦어요", "resume-protected-start", at=f"{D_2026_09_23}T13:00:00+09:00")
    reply = _say(decided, "70분이요", "resume-protected-answer", case_id=first["case_id"])
    assert reply["status"] == "asked" and reply["case_status"] == "resolved", reply
    assert "바꿨" not in reply["answer"] and "바꾸지 않았어요" in reply["answer"] and "어떻게 할까요?" in reply["answer"], reply
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM itinerary_versions WHERE trip_id=%s", (decided["trip"]["trip_id"],))
        assert cur.fetchone()[0] == 1


def test_a_complete_new_request_while_a_question_waits_is_handled_as_a_new_request(decided):
    """되묻기를 기다리는 중에 웹이 대기 건 번호를 붙여 보내도, 새 문장이 혼자서 완결된 요청이면 새로 처리한다.
    전에는 무엇을 말해도 같은 되묻기만 돌아왔다(x600 서버 웹 채팅 시험 2026-10-13: 20건)."""
    first = _say(decided, "바꿔", "resume-new-start")
    assert first["case_status"] == "waiting_input"
    asked = _saved(first["case_id"])
    question = _say(decided, "성수 점심 식당 알려줘", "resume-new-question", case_id=first["case_id"],
                    resume_token=first.get("resume_token"), expected_version=first["version"])
    assert question["case_id"] != first["case_id"] and question["status"] == "answered", question
    assert "성수 점심" in question["answer"]
    assert _saved(first["case_id"])[:2] == asked[:2]            # 앞의 대기 건은 건드리지 않았다
    change = _say(decided, "점심 다른 데로 바꿔", "resume-new-change", case_id=first["case_id"])
    assert change["case_id"] != first["case_id"] and change["status"] == "adjusted", change


def test_an_incomplete_reply_still_answers_the_waiting_question(decided):
    """혼자서는 뜻이 안 서는 말은 지금처럼 대기 중인 질문의 답으로 넘긴다."""
    first = _say(decided, "바꿔", "resume-incomplete-start")
    reply = _say(decided, "음 글쎄", "resume-incomplete-reply", case_id=first["case_id"])
    assert reply["case_id"] == first["case_id"], reply
