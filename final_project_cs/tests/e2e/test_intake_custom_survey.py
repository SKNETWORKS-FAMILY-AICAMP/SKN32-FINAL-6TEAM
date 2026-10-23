"""로딩 중 질문의 직접 입력 · 답 취소 — 이력 · 이어받기 · 고객 경계. `[2026-10-09]` · `[2026-10-19 묶음 3 — 직접 입력은 「누구와」의 「기타」]`"""
from uuid import UUID

from app.domains.travel_ops.components.intake import survey_answers
from app.infrastructure.db.session import get_connection
from .test_trip_api import api  # noqa: F401
from .test_intake_survey_questions import _intake, _answer, _view
from .test_trip_intake_api import _full_client, _key


def _party(view):
    return next(q for q in view["questions"] if q["id"] == "party")


def test_custom_save_clear_and_reentry_keep_history_and_effective_preference(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    _answer(client, headers, intake_id, {"party": {"custom": "회사 동료 셋"}})
    assert _party(_view(client, headers, intake_id))["custom_answer"] == "회사 동료 셋"
    assert _answer(client, headers, intake_id, {"party": None})["answered"] == []
    cleared = _party(_view(client, headers, intake_id))
    assert cleared["answer"] is None and cleared["custom_answer"] is None
    _answer(client, headers, intake_id, {"party": {"custom": "부모님"}})
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT tenant_id FROM trip_intakes WHERE intake_id=%s", (UUID(intake_id),))
        tenant = cur.fetchone()[0]
        effective = survey_answers.to_survey(survey_answers.stored(conn, tenant_id=tenant, intake_id=UUID(intake_id)),
                                            survey_answers.stored_resolved(conn, tenant_id=tenant, intake_id=UUID(intake_id)))
        assert effective == {"party": "부모님", "custom_answers": {"party": "부모님"}}
        cur.execute("SELECT option_id FROM trip_intake_survey_answers WHERE tenant_id=%s AND intake_id=%s ORDER BY seq", (tenant, UUID(intake_id)))
        assert [row[0] for row in cur.fetchall()] == ["custom:회사 동료 셋", survey_answers.CLEARED_ANSWER, "custom:부모님"]


def test_cleared_answer_is_not_revived_in_a_new_intake(api):
    client, _, _ = _full_client()
    headers = _key(client)
    old = _intake(client, headers)["intake_id"]
    _answer(client, headers, old, {"party": "friends"})
    _answer(client, headers, old, {"party": None})
    assert _party(_intake(client, headers))["answer"] is None


def test_custom_write_and_clear_do_not_cross_customer_boundary(api):
    client, _, _ = _full_client()
    mine, other = _key(client), _key(client)
    intake_id = _intake(client, mine)["intake_id"]
    _answer(client, mine, intake_id, {"party": {"custom": "친구 둘과 강아지"}})
    _answer(client, other, intake_id, {"party": None}, 404)
    _answer(client, other, intake_id, {"party": {"custom": "혼자"}}, 404)
    assert _party(_view(client, mine, intake_id))["custom_answer"] == "친구 둘과 강아지"
