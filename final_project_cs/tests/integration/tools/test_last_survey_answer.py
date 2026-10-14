"""`read.last_survey_answer` — 같은 고객이 여행 설문 문항에 마지막으로 고른 답. `[2026-10-14]` 활동 → 코어 전달 8번 회신.

여행을 못 찾은 예약에서 활동 팀이 문항을 다시 물을 때 「지난번에는 …을 고르셨어요」를 알려 주는 데 쓴다. 실제 DB 로 본다.
조건은 여행 등록 때 지난 답을 이어받는 규칙(`survey_answers.inherit`)과 같다 — 지금 질문 묶음 버전 · 뜻이 그대로인 답만.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domains.travel_ops.components.intake import survey_answers
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ReadToolbox, ToolContext


@pytest.fixture()
def world():
    tenant = "lastsurvey_" + uuid4().hex[:10]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "last survey answer"))
        ids = {}
        for name in ("owner", "stranger"):
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (tenant, name))
            ids[name] = cur.fetchone()[0]
    yield {"tenant": tenant, **ids}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM trip_intakes WHERE tenant_id=%s", (tenant,))     # 답 이력은 접수와 같이 지워진다
    cleanup_tenant(tenant)


def _answer(world, option_id, *, customer="owner", version=None, question_id="priority"):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trip_intakes (tenant_id,customer_id) VALUES (%s,%s) RETURNING intake_id",
                    (world["tenant"], world[customer]))
        intake = cur.fetchone()[0]
        slot, value = survey_answers.resolve(question_id, option_id) or (question_id, option_id)
        cur.execute("INSERT INTO trip_intake_survey_answers (tenant_id,intake_id,question_id,option_id,slot,value,bundle_version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (world["tenant"], intake, question_id, option_id, slot, value,
                     version or survey_answers.QUESTION_SET_VERSION))


def _read(world, customer="owner", question_id="priority"):
    scope = ToolContext(tenant_id=world["tenant"], customer_id=world[customer], case_id=uuid4(), knowledge_scope=[])
    return ReadToolbox(get_connection).last_survey_answer(scope, question_id=question_id)


def test_the_latest_answer_of_this_customer_is_returned_with_its_label(world):
    _answer(world, "activity")
    _answer(world, "mobility")                                              # 나중 접수의 답이 이긴다

    found = _read(world)
    question = next(q for q in survey_answers.QUESTIONS if q.id == "priority")
    label = next(option.label for option in question.options if option.id == "mobility")
    assert found == {"option_id": "mobility", "value": "mobility", "label": label}


def test_an_answer_from_an_old_question_set_is_not_offered(world):
    _answer(world, "mobility", version="0-old")

    assert _read(world) is None


def test_a_free_text_answer_is_not_offered_as_a_choice(world):
    _answer(world, survey_answers.CUSTOM_PREFIX + "그때그때 달라요")

    assert _read(world) is None


def test_another_customers_answer_is_never_returned(world):
    _answer(world, "mobility", customer="stranger")

    assert _read(world) is None


def test_an_unknown_question_is_none(world):
    assert _read(world, question_id="no_such_question") is None
