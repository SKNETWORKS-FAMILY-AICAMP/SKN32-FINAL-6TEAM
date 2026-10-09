# -*- coding: utf-8 -*-
"""Case 가 가리키는 예약 — `[2026-10-09]` `read.booking` 이 고객의 「가장 임박한 예약」이 아니라 **이 Case 의 예약**을 읽는다.

이음은 접수 때 `subject_ref: {"kind": "booking", "id": booking_id}` 로 만든다 — 확인기가 이 테넌트 · 이 고객의 예약인지
보고 `state_json.subject_ref` 에 저장한다(`core_hooks/subjects.py`). 이음이 없는 Case 는 전처럼 가장 임박한 예약을 읽되
`matched_by: "nearest"` 로 추정임을 남긴다. DB 없이 SQL 을 흉내 낸다 — 실제 DB 확인은 통합 시험 몫이다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.subjects import SubjectNotFound
from app.domains.travel_ops.components.core_hooks.subjects import make_subject_interpreter, resolve_subject
from app.tools.read_tools import ReadToolbox, ToolContext

TENANT = "t1"
CUSTOMER = uuid4()
CASE = uuid4()
SOON = datetime.now(timezone.utc) + timedelta(hours=5)
LATER = datetime.now(timezone.utc) + timedelta(days=3)


def _row(booking_id, starts_at, kind="activity"):
    return (booking_id, "BK-" + booking_id[:4], kind, "confirmed", starts_at, 2, 4, 1000, False, "p1")


class FakeDb:
    """`bookings` · `customer_cases` 두 표만 흉내 낸다 — 테넌트 · 고객 조건이 맞을 때만 돌려준다."""

    def __init__(self, bookings, case_subject=None):
        self.bookings = bookings                 # {booking_id: row}
        self.case_subject = case_subject         # 이 Case 의 state_json.subject_ref
        self.queries: list[str] = []

    @contextmanager
    def connect(self):
        yield self

    @contextmanager
    def cursor(self):
        yield self

    def execute(self, sql, params):
        self.queries.append(sql)
        self._result = None
        if "FROM customer_cases" in sql:
            tenant, customer, case_id = params
            ref = self.case_subject or {}
            if (tenant, customer, case_id) == (TENANT, CUSTOMER, CASE) and ref.get("kind") == "booking":
                self._result = (ref.get("id"),)
        elif "SELECT kind FROM bookings" in sql:
            tenant, customer, booking_id = params
            row = self.bookings.get(booking_id)
            if tenant == TENANT and customer == str(CUSTOMER) and row:
                self._result = (row[2],)
        elif "FROM bookings" in sql:
            if params[:2] != (TENANT, CUSTOMER):
                return
            if "booking_id=%s" in sql:
                self._result = self.bookings.get(params[2])
            else:
                rows = sorted(self.bookings.values(), key=lambda r: r[4])
                self._result = rows[0] if rows else None

    def fetchone(self):
        return self._result


SOON_ID, LATER_ID = str(uuid4()), str(uuid4())
BOOKINGS = {SOON_ID: _row(SOON_ID, SOON), LATER_ID: _row(LATER_ID, LATER, kind="dining")}
SCOPE = ToolContext(tenant_id=TENANT, customer_id=CUSTOMER, case_id=CASE, knowledge_scope=[])


def _booking(db, **arguments):
    return ReadToolbox(db.connect).booking(SCOPE, **arguments)


# ── read.booking ─────────────────────────────────────────────

def test_a_case_linked_to_a_booking_reads_that_booking_not_the_nearest():
    db = FakeDb(BOOKINGS, case_subject={"kind": "booking", "id": LATER_ID})
    found = _booking(db, case_id=str(CASE))

    assert found["booking_id"] == LATER_ID and found["matched_by"] == "case"


def test_the_case_id_argument_from_the_team_is_not_trusted():
    """팀이 넘긴 `case_id` 가 아니라 도구 문맥의 Case 로 읽는다."""
    db = FakeDb(BOOKINGS, case_subject={"kind": "booking", "id": LATER_ID})
    found = _booking(db, case_id=str(uuid4()))

    assert found["booking_id"] == LATER_ID


def test_a_linked_booking_that_is_gone_is_unknown_not_another_booking():
    db = FakeDb(BOOKINGS, case_subject={"kind": "booking", "id": str(uuid4())})

    assert _booking(db) is None


def test_a_case_without_a_booking_link_falls_back_to_the_nearest_and_says_so():
    db = FakeDb(BOOKINGS, case_subject={"kind": "trip", "id": str(uuid4())})
    found = _booking(db)

    assert found["booking_id"] == SOON_ID and found["matched_by"] == "nearest"


def test_an_explicit_booking_id_wins():
    db = FakeDb(BOOKINGS, case_subject={"kind": "booking", "id": LATER_ID})
    found = _booking(db, booking_id=SOON_ID)

    assert found["booking_id"] == SOON_ID and found["matched_by"] == "argument"
    assert not any("customer_cases" in q for q in db.queries)


# ── 접수 때 확인 ─────────────────────────────────────────────

def test_the_resolver_keeps_an_owned_booking_and_routes_by_its_kind():
    resolved = resolve_subject(FakeDb(BOOKINGS), tenant_id=TENANT, customer_id=CUSTOMER,
                               subject_ref={"kind": "booking", "id": LATER_ID})

    assert resolved.subject_ref["kind"] == "booking" and resolved.subject_ref["id"] == LATER_ID
    assert resolved.routing_hint == "dining" and resolved.hint_is_verified is True


@pytest.mark.parametrize("ref", [{"kind": "booking", "id": str(uuid4())}, {"kind": "booking", "id": "not-a-uuid"}])
def test_the_resolver_refuses_a_booking_it_cannot_confirm(ref):
    with pytest.raises(SubjectNotFound):
        resolve_subject(FakeDb(BOOKINGS), tenant_id=TENANT, customer_id=CUSTOMER, subject_ref=ref)


def test_the_resolver_refuses_another_customers_booking():
    with pytest.raises(SubjectNotFound):
        resolve_subject(FakeDb(BOOKINGS), tenant_id=TENANT, customer_id=uuid4(),
                        subject_ref={"kind": "booking", "id": SOON_ID})


def test_a_report_type_does_not_send_a_booking_case_to_another_team():
    """신고 종류(지연 → 식당)가 아니라 예약의 종류가 담당이다."""
    interpret = make_subject_interpreter(lambda text: {"type": "delay"})
    reading = interpret(text="늦어요", subject_ref={"kind": "booking", "id": SOON_ID, "part_kind": "activity"})

    assert reading["routing_hint"] == "activity"
