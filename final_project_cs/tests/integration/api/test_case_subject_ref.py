"""`POST /v1/cases` 의 `subject_ref` — 서버가 소유를 확인하고, 확인기가 없으면 조용히 무시하지 않는다.

★`[결정 2026-09-17]` wiki `external/rest-endpoints.md` 「subject_ref」.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.itinerary import Item, TripStore
from app.modules.travel_ops.subjects import resolve_subject
from app.presentation import security
from app.presentation.api.app import create_app
from app.presentation.api.cases import build_router

KST = ZoneInfo("Asia/Seoul")


def _classifier(message):
    return {"intent": "incident_report", "issue_code": "dining_hours", "sentiment": "negative"}


@pytest.fixture()
def world(monkeypatch):
    original = settings_module.get_settings()
    tenant = "subjectref_" + uuid4().hex[:10]
    settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "subject ref"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "owner"))
            owner = cur.fetchone()[0]
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id",
                        (tenant, "stranger"))
            stranger = cur.fetchone()[0]
        item = Item(item_id=uuid4(), seq=1, kind="dining", title="점심", place_id=None,
                    starts_at=datetime(2026, 9, 20, 12, tzinfo=KST), ends_at=datetime(2026, 9, 20, 13, tzinfo=KST))
        with conn.transaction():
            trip_id, _ = TripStore(tenant).create_trip(conn, customer_id=owner, title="하루", locale="ko",
                                                       party_size=2, items=[item])
    auth = {"Authorization": "Bearer " + security._development_key("case:write", original.secret_key)}
    yield {"tenant": tenant, "owner": owner, "stranger": stranger, "trip_id": trip_id, "item": item,
           "auth": auth}
    cleanup_tenant(tenant)


def _body(world, customer, **subject):
    return {"request_id": "req-" + uuid4().hex[:6], "customer_id": str(customer), "message": "점심에 늦어요",
            "channel": "api", "subject_ref": {"kind": "trip", "id": str(world["trip_id"]), **subject}}


def test_a_case_keeps_the_verified_subject(world):
    client = TestClient(create_app(classifier=_classifier, domain_routers=[], subject_resolver=resolve_subject))
    response = client.post("/v1/cases", headers=world["auth"],
                           json=_body(world, world["owner"], part_id=str(world["item"].item_id)))
    assert response.status_code == 201, response.text
    with get_connection() as conn:
        case = repository.get_case(conn, tenant_id=world["tenant"], case_id=response.json()["case_id"])
    state = case["state_json"]
    assert state["subject_ref"]["id"] == str(world["trip_id"]) and state["subject_ref"]["part_id"] == str(world["item"].item_id)
    assert state["routing_hint"] == "dining" and state["routing_hint_verified"] is True
    assert state["trigger_source"] == "customer"


def test_someone_elses_trip_is_not_found(world):
    client = TestClient(create_app(classifier=_classifier, domain_routers=[], subject_resolver=resolve_subject))
    response = client.post("/v1/cases", headers=world["auth"], json=_body(world, world["stranger"]))
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (world["tenant"],))
        assert cur.fetchone()[0] == 0             # ★Case 도 만들지 않는다


def test_a_subject_without_a_resolver_is_refused_not_ignored(world):
    app = FastAPI()
    app.include_router(build_router(_classifier, None, None))
    response = TestClient(app).post("/v1/cases", headers=world["auth"], json=_body(world, world["owner"]))
    # ★요청 형식 오류도 422 다 — 코드까지 봐야 「확인기 없음」인지 안다(이 앱엔 공통 오류 처리기가 없어 detail 안에 있다)
    assert response.status_code == 422 and response.json()["detail"]["error"]["code"] == "subject_ref_unsupported"
