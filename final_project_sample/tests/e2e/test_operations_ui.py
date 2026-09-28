from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Json

import acop_basement.core.settings as settings_module
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.presentation import security
from acop_basement.presentation.api.app import create_app
from acop_basement.presentation.ui import mount_ui
import acop_basement.presentation.ui.routes as ui


ui_app = create_app()
mount_ui(ui_app)


@pytest.fixture()
def ui_fixture(monkeypatch):
    original = settings_module.get_settings()
    tenant = "test_ui_" + uuid4().hex
    customer = uuid4()
    case_id = uuid4()
    evidence_action = uuid4()
    empty_action = uuid4()
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)
    monkeypatch.setattr(ui, "_tenant", lambda: tenant)

    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "UI test"))
        cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)", (customer, tenant, "masked-customer"))
        cur.execute("""INSERT INTO customer_cases (case_id,tenant_id,customer_id,status,subject,state_json,intent,issue_code,sentiment,owner_team_id,version)
                       VALUES (%s,%s,%s,'waiting_approval',%s,%s,%s,%s,%s,%s,1)""",
                    (case_id, tenant, customer, "seed UI case", '{"answer":"masked answer"}', "billing", "post_cancel_charge", "negative", "Billing"))
        cur.execute("""INSERT INTO case_events (tenant_id,case_id,aggregate_version,event_type,payload_json,actor_type,actor_id)
                       VALUES (%s,%s,1,'approval_required',%s,'system','masked-actor')""", (tenant, case_id, '{"action_id":"seed"}'))
        for action_id, evidence in ((evidence_action, [{"source_type": "policy", "source_id": "doc#1", "claim": "policy claim"}]), (empty_action, [])):
            cur.execute("""INSERT INTO action_requests (action_id,tenant_id,case_id,action_type,arguments_json,idempotency_key,status)
                           VALUES (%s,%s,%s,'refund.request',%s,%s,'pending_approval')""",
                        (action_id, tenant, case_id, Json({"amount": 100, "risk_level": "high", "evidence": evidence}), "idem-" + str(action_id)))

    try:
        yield {"client": TestClient(ui_app), "tenant": tenant, "case_id": case_id, "evidence_action": evidence_action, "empty_action": empty_action}
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
            cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM feedback_analytics_reports WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
            cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def test_cases_detail_and_trace_render_seed_data(ui_fixture):
    client = ui_fixture["client"]
    case_id = ui_fixture["case_id"]
    assert "post_cancel_charge" in client.get("/ops/cases").text
    detail = client.get(f"/ops/cases/{case_id}").text
    assert "masked answer" in detail and "policy" not in detail
    trace = client.get(f"/ops/cases/{case_id}/trace").text
    assert "append-only" in trace and "v1" in trace
    assert str(case_id) in trace and "seed UI case" in trace and "waiting_approval" in trace


def test_waiting_approval_scenario_is_visible_end_to_end(ui_fixture):
    client = ui_fixture["client"]
    case_id = ui_fixture["case_id"]
    listing = client.get("/ops/cases").text
    assert str(case_id)[:4] in listing
    assert "pill--warn" in listing
    assert "waiting_approval" in listing
    trace = client.get(f"/ops/cases/{case_id}/trace").text
    assert "approval_required" in trace
    assert trace.index("v1") < trace.index("approval_required")
    approvals = client.get("/ops/approvals").text
    assert "rationale evidence" in approvals
    assert "policy claim" in approvals
    assert f"/ops/approvals/{case_id}/{ui_fixture['empty_action']}" in approvals
    assert "name='decision' value='approved' disabled" in approvals


def test_evidence_free_proposal_has_disabled_decision(ui_fixture):
    text = ui_fixture["client"].get("/ops/approvals").text
    assert "근거 없음" in text
    assert f"/ops/approvals/{ui_fixture['case_id']}/{ui_fixture['empty_action']}" in text
    assert "name='decision' value='approved' disabled" in text


def test_degraded_case_detail_has_visible_warning(ui_fixture):
    case_id = ui_fixture["case_id"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE customer_cases SET state_json=%s WHERE case_id=%s",
                    (Json({"answer": "masked answer", "degraded": True,
                           "omissions": ["policy_context"]}), case_id))
    detail = ui_fixture["client"].get(f"/ops/cases/{case_id}").text
    assert "degraded" in detail
    assert "ContextPack" in detail
    assert "policy_context" in detail
    assert "notice--critical" in detail


def test_approval_uses_rest_endpoint(ui_fixture):
    response = ui_fixture["client"].post(f"/ops/approvals/{ui_fixture['case_id']}/{ui_fixture['evidence_action']}", data={"decision": "rejected"}, follow_redirects=False)
    assert response.status_code == 303
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT decision FROM action_approvals WHERE action_id=%s", (ui_fixture["evidence_action"],))
        assert cur.fetchone()[0] == "rejected"


def test_voc_without_report_says_none(ui_fixture):
    assert "리포트 없음" in ui_fixture["client"].get("/ops/voc").text


# ★"조립 상태를 보여준다" 는 더 이상 이 파일의 책임이 아니다.
#   `/ui/admin` 은 지워졌다 — `final_project_ui` 가 별도 프로그램으로 그 역할을 한다.
#   같은 내용(team 목록·guardrails·마스킹된 key)은 이제 `/introspection` 이 낸다.
#   해당 검사는 `tests/e2e/test_introspection_endpoint.py` 에 있다.
