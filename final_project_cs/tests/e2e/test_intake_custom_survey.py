from uuid import UUID

from app.domains.travel_ops.components.intake import survey_answers
from app.domains.travel_ops.instances.mobility.wiring import modes_from_survey
from app.infrastructure.db.session import get_connection
from .test_trip_api import api  # noqa: F401
from .test_intake_survey_questions import _intake, _answer, _view
from .test_trip_intake_api import _full_client, _key


def test_custom_save_clear_and_reentry_keep_history_and_effective_preference(api):
    client, _, _ = _full_client()
    headers = _key(client)
    intake_id = _intake(client, headers)["intake_id"]
    _answer(client, headers, intake_id, {"preferred_mobility": {"custom": "택시 + 버스"}})
    assert _view(client, headers, intake_id)["questions"][0]["custom_answer"] == "택시 + 버스"
    assert _answer(client, headers, intake_id, {"preferred_mobility": None})["answered"] == []
    cleared = _view(client, headers, intake_id)["questions"][0]
    assert cleared["answer"] is None and cleared["custom_answer"] is None
    _answer(client, headers, intake_id, {"preferred_mobility": {"custom": "지하철 + 택시"}})
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT tenant_id FROM trip_intakes WHERE intake_id=%s", (UUID(intake_id),))
        tenant = cur.fetchone()[0]
        effective = survey_answers.to_survey(survey_answers.stored(conn, tenant_id=tenant, intake_id=UUID(intake_id)),
                                            survey_answers.stored_resolved(conn, tenant_id=tenant, intake_id=UUID(intake_id)))
        assert modes_from_survey({"survey": effective}) == ["subway", "taxi", "walk"]
        cur.execute("SELECT option_id FROM trip_intake_survey_answers WHERE tenant_id=%s AND intake_id=%s ORDER BY seq", (tenant, UUID(intake_id)))
        assert [row[0] for row in cur.fetchall()] == ["custom:택시 + 버스", survey_answers.CLEARED_ANSWER, "custom:지하철 + 택시"]


def test_cleared_answer_is_not_revived_in_a_new_intake(api):
    client, _, _ = _full_client()
    headers = _key(client)
    old = _intake(client, headers)["intake_id"]
    _answer(client, headers, old, {"preferred_mobility": "taxi"})
    _answer(client, headers, old, {"preferred_mobility": None})
    assert _intake(client, headers)["questions"][0]["answer"] is None


def test_custom_write_and_clear_do_not_cross_customer_boundary(api):
    client, _, _ = _full_client()
    mine, other = _key(client), _key(client)
    intake_id = _intake(client, mine)["intake_id"]
    _answer(client, mine, intake_id, {"priority": {"custom": "활동 + 이동"}})
    _answer(client, other, intake_id, {"priority": None}, 404)
    _answer(client, other, intake_id, {"priority": {"custom": "음식"}}, 404)
    assert _view(client, mine, intake_id)["questions"][1]["custom_answer"] == "활동 + 이동"
