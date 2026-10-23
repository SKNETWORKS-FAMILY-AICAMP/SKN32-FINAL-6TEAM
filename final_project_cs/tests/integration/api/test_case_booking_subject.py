"""`POST /v1/cases` 의 `subject_ref: {kind: "booking"}` → `read.booking` 이 **그 예약**을 읽는다 — `[2026-10-09]`.

전에는 `read.booking` 이 Case 와 상관없이 고객의 가장 임박한 예약을 돌려줬다. 실제 DB 로 접수부터 도구까지 본다.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.scenarios.case_engine import cleanup_tenant
from app.domains.travel_ops.components.core_hooks.subjects import resolve_subject
from app.presentation import security
from app.presentation.api.app import create_app
from app.tools.read_tools import ReadToolbox, ToolContext


def _classifier(message):
    return {"intent": "confirm_request", "issue_code": "activity_other", "sentiment": "neutral"}


@pytest.fixture()
def world(monkeypatch):
    original = settings_module.get_settings()
    tenant = "bookingref_" + uuid4().hex[:10]
    settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "booking ref"))
        ids = {}
        for name in ("owner", "stranger"):
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, name))
            ids[name] = cur.fetchone()[0]
        for name, kind, hours in (("soon", "activity", 5), ("later", "dining", 72)):
            cur.execute("INSERT INTO bookings (tenant_id,customer_id,booking_no,kind,status,starts_at,party_size,capacity) "
                        "VALUES (%s,%s,%s,%s,'confirmed',now()+make_interval(hours=>%s),2,4) RETURNING booking_id",
                        (tenant, ids["owner"], "BK-" + name, kind, hours))
            ids[name] = cur.fetchone()[0]
    auth = {"Authorization": "Bearer " + security._development_key("case:write", original.secret_key)}
    client = TestClient(create_app(classifier=_classifier, domain_routers=[], subject_resolver=resolve_subject))
    yield {"tenant": tenant, "auth": auth, "client": client, **ids}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM bookings WHERE tenant_id=%s", (tenant,))
    cleanup_tenant(tenant)


def _open(world, customer, subject_ref=None):
    body = {"request_id": "req-" + uuid4().hex[:6], "customer_id": str(customer), "message": "이 예약 성립하나요",
            "channel": "api"}
    if subject_ref is not None:
        body["subject_ref"] = subject_ref
    return world["client"].post("/v1/cases", headers=world["auth"], json=body)


def _read_booking(world, case_id):
    scope = ToolContext(tenant_id=world["tenant"], customer_id=world["owner"], case_id=UUID(case_id),
                        knowledge_scope=[])
    return ReadToolbox(get_connection).booking(scope, case_id=case_id)


def test_a_case_about_the_later_booking_reads_the_later_booking(world):
    response = _open(world, world["owner"], {"kind": "booking", "id": str(world["later"])})
    assert response.status_code == 201, response.text
    case_id = response.json()["case_id"]
    with get_connection() as conn:
        state = repository.get_case(conn, tenant_id=world["tenant"], case_id=case_id)["state_json"]
    assert state["subject_ref"] == {"kind": "booking", "id": str(world["later"]), "part_kind": "dining",
                                    "request": None}
    assert state["routing_hint"] == "dining" and state["routing_hint_verified"] is True

    found = _read_booking(world, case_id)
    assert found["booking_id"] == world["later"] and found["matched_by"] == "case"


def test_a_case_without_a_booking_still_reads_the_nearest_and_says_so(world):
    response = _open(world, world["owner"])
    assert response.status_code == 201, response.text

    found = _read_booking(world, response.json()["case_id"])
    assert found["booking_id"] == world["soon"] and found["matched_by"] == "nearest"


def test_someone_elses_booking_is_not_found_and_opens_no_case(world):
    response = _open(world, world["stranger"], {"kind": "booking", "id": str(world["later"])})
    assert response.status_code == 404
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (world["tenant"],))
        assert cur.fetchone()[0] == 0
