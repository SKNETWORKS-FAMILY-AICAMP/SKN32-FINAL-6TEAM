from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Json

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app
from app.presentation.ui import mount_ui
import app.presentation.ui.routes as ui
from app.core.contracts import TeamManifest
from app.core.registry import TeamRegistry


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
    assert "post_cancel_charge" in client.get("/ui/cases").text
    detail = client.get(f"/ui/cases/{case_id}").text
    assert "masked answer" in detail and "policy" not in detail
    trace = client.get(f"/ui/cases/{case_id}/trace").text
    assert "append-only" in trace and "v1" in trace
    assert str(case_id) in trace and "seed UI case" in trace and "waiting_approval" in trace


def test_waiting_approval_scenario_is_visible_end_to_end(ui_fixture):
    client = ui_fixture["client"]
    case_id = ui_fixture["case_id"]
    listing = client.get("/ui/cases").text
    assert str(case_id)[:4] in listing
    assert "pill--warn" in listing
    assert "waiting_approval" in listing
    trace = client.get(f"/ui/cases/{case_id}/trace").text
    assert "approval_required" in trace
    assert trace.index("v1") < trace.index("approval_required")
    approvals = client.get("/ui/approvals").text
    assert "rationale evidence" in approvals
    assert "policy claim" in approvals
    assert f"/ui/approvals/{case_id}/{ui_fixture['empty_action']}" in approvals
    assert "name='decision' value='approved' disabled" in approvals


def test_evidence_free_proposal_has_disabled_decision(ui_fixture):
    text = ui_fixture["client"].get("/ui/approvals").text
    assert "근거 없음" in text
    assert f"/ui/approvals/{ui_fixture['case_id']}/{ui_fixture['empty_action']}" in text
    assert "name='decision' value='approved' disabled" in text


def test_degraded_case_detail_has_visible_warning(ui_fixture):
    case_id = ui_fixture["case_id"]
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE customer_cases SET state_json=%s WHERE case_id=%s",
                    (Json({"answer": "masked answer", "degraded": True,
                           "omissions": ["policy_context"]}), case_id))
    detail = ui_fixture["client"].get(f"/ui/cases/{case_id}").text
    assert "degraded" in detail
    assert "ContextPack" in detail
    assert "policy_context" in detail
    assert "notice--critical" in detail


def test_approval_uses_rest_endpoint(ui_fixture):
    response = ui_fixture["client"].post(f"/ui/approvals/{ui_fixture['case_id']}/{ui_fixture['evidence_action']}", data={"decision": "rejected"}, follow_redirects=False)
    assert response.status_code == 303
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT decision FROM action_approvals WHERE action_id=%s", (ui_fixture["evidence_action"],))
        assert cur.fetchone()[0] == "rejected"


def test_voc_without_report_says_none(ui_fixture):
    assert "리포트 없음" in ui_fixture["client"].get("/ui/voc").text


def test_admin_shows_registered_teams_guardrails_and_masks_key(ui_fixture):
    response = ui_fixture["client"].get("/ui/admin")
    assert response.status_code == 200
    assert "voc_store_manager" in response.text
    assert "12000" in response.text
    assert "sk-****" in response.text
    assert settings_module.get_settings().openai_api_key not in response.text


def test_admin_reflects_a_newly_registered_team(ui_fixture, monkeypatch):
    class FakeTeam:
        manifest = TeamManifest(
            team_id="fake_admin_team", display_name="Fake Admin Team",
            contract_name="a_cop.team_task", supported_contract_versions=["1.0"],
            capabilities=["fake.inspect"], accepted_case_types=["fake"],
            required_context=["case_state"], allowed_tools=["read.fake"],
            knowledge_scope=["fake"], max_steps=1, active=True,
            implementation_revision="test",
        )

    import app.composition as composition
    base_registry = composition.build_registry()
    teams = [base_registry.get("voc_store_manager").module]
    monkeypatch.setattr(composition, "build_registry", lambda: TeamRegistry(teams + [FakeTeam()]))
    response = ui_fixture["client"].get("/ui/admin")
    assert response.status_code == 200
    assert "fake_admin_team" in response.text


def test_outbox_unknown_screen_renders_resolution_form(ui_fixture):
    message_id = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO outbox (message_id, tenant_id, topic, dedupe_key, payload_json, status, last_error) "
            "VALUES (%s,%s,'ui.provider',%s,%s,'unknown','provider timed out')",
            (message_id, ui_fixture["tenant"], "ui-stale-" + uuid4().hex, Json({"provider_ref": "masked-ref"})),
        )
    try:
        response = ui_fixture["client"].get("/ops/outbox")
        assert response.status_code == 200
        assert str(message_id) in response.text
        assert "provider timed out" in response.text
        assert "confirmed_delivered" in response.text
        assert "자동 재실행 없음" in response.text
    finally:
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM outbox WHERE message_id=%s", (message_id,))
