# -*- coding: utf-8 -*-
"""실제 앱 경로로 Case 버전 — `POST /v1/cases`(subject_ref) → 백그라운드 실행 → Team → 일정 버전·통지.

★`[2026-09-17]` 하루 대조 시험(`tests/scenario/test_case_version_day.py`)은 조립기(`case_engine`)로
  Case 를 연다. 이 시험은 **HTTP 접수 · 대상 확인기 주입 · 떼어낸 실행**까지 제품 경로 그대로 지난다.
  바꿔 끼우는 것은 바깥 소스(재생)와 LLM(분류 · 신고 추출)뿐이다 — Controller 는 운영 조립 함수로 만든다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.composition as composition
import app.core.settings as settings_module
from app.core.project_config import load_project_config
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.presentation import security
from app.presentation.api.app import create_app
from app.tools.read_tools import ReadToolbox
from tests.scenario.test_case_version_day import (REPORTS, Clock, _at, _classifier, _extractor, _seed,
                                                  _sources)


@pytest.fixture()
def rest(monkeypatch):
    original = settings_module.get_settings()
    tenant = "caserest_" + uuid4().hex[:10]
    settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("08:00"))
    check, route_events = _sources(clock)
    tools = ReadToolbox(get_connection, policy_search=lambda *a, **k: [], travel=None, check=check,
                        route_events=route_events, report_extractor=_extractor)
    config = load_project_config()
    controller = composition.build_controller(
        registry=composition.build_registry(tools=tools, llm=None, config=config), llm=None, config=config)
    client = TestClient(create_app(controller=controller, classifier=_classifier, domain_routers=[]))
    def auth(scope):
        return {"Authorization": "Bearer " + security._development_key(scope, original.secret_key)}
    yield {"client": client, "auth": auth, "customer": customer, "trip_id": trip_id, "store": store,
           "tenant": tenant}
    cleanup_tenant(tenant)


def _post(rest, kind, **subject):
    report = REPORTS[kind]
    return rest["client"].post("/v1/cases", headers=rest["auth"]("case:write"), json={
        "request_id": f"rest-{kind}", "customer_id": str(rest["customer"]), "message": report["message"],
        "channel": "personal_ai",
        "subject_ref": {"kind": "trip", "id": str(rest["trip_id"]),
                        "request": {"at": _at(report["at"]).isoformat()}, **subject}})


def test_a_delay_sentence_changes_the_trip_through_the_rest_path(rest):
    response = _post(rest, "delay")
    assert response.status_code == 201, response.text
    case_id = response.json()["case_id"]
    # ★TestClient 는 응답 뒤 백그라운드 작업(떼어낸 run_case)을 끝까지 돌린다
    detail = rest["client"].get(f"/v1/cases/{case_id}", headers=rest["auth"]("case:read")).json()
    assert detail["status"] == "resolved", detail
    assert "브레이크타임" in (detail.get("answer") or "") or detail.get("answer")
    with get_connection() as conn:
        trip, _ = rest["store"].latest(conn, rest["trip_id"])
        with conn.cursor() as cur:
            cur.execute("SELECT case_id FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s AND version=2",
                        (rest["tenant"], rest["trip_id"]))
            version_case = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM outbox WHERE tenant_id=%s AND topic='trip.notice'", (rest["tenant"],))
            notices = cur.fetchone()[0]
    assert trip["version"] == 2 and str(version_case) == case_id and notices == 1


def test_a_stock_question_is_answered_without_changing_the_trip(rest):
    case_id = _post(rest, "stock_out").json()["case_id"]
    detail = rest["client"].get(f"/v1/cases/{case_id}", headers=rest["auth"]("case:read")).json()
    assert detail["status"] == "resolved" and "[미확인]" in detail["answer"], detail
    with get_connection() as conn:
        assert rest["store"].latest(conn, rest["trip_id"])[0]["version"] == 1
