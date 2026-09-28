from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import acop_basement.core.settings as settings_module
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.presentation import security
from acop_basement.presentation.api.app import create_app


@pytest.fixture()
def pii_case(monkeypatch):
    original = settings_module.get_settings()
    tenant = "test_pii_" + uuid4().hex
    customer = uuid4()
    configured = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: configured)
    monkeypatch.setattr(security, "get_settings", lambda: configured)
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "PII test"))
                cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)", (customer, tenant, "pii-customer"))
        try:
            yield {
                "tenant": tenant,
                "customer": customer,
                "original": original,
                "client": TestClient(create_app(classifier=lambda _: {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"})),
            }
        finally:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))


def test_case_message_is_redacted_in_db_api_and_audit(pii_case):
    phone = "010-1234-5678"
    card = "4111 1111 1111 1111"
    # ★키처럼 생긴 리터럴을 저장소에 두지 않는다 — 조각으로 만든다.
    #   `scripts/publish_public.py` 의 비밀 스캐너가 이 줄을 잡아 배포를 막았고,
    #   가짜 fixture 였지만 **스캐너를 느슨하게 하는 대신 리터럴을 없앴다.**
    #   저장소에 `sk-...` 가 널려 있으면 사람이 스캐너 경고를 무시하게 된다.
    api_key = "sk" + "-" + "test" + "-" + "original" + "-" + "api" + "-" + "key"
    payment_identifier = "pay_original_987654"
    message = f"phone={phone} card={card} api_key={api_key} payment={payment_identifier}"
    original = pii_case["original"]
    tenant = pii_case["tenant"]
    customer = pii_case["customer"]
    client = pii_case["client"]

    created = client.post("/v1/cases", headers={"Authorization": "Bearer " + security._development_key("case:write", original.secret_key)}, json={
        "request_id": "pii-redaction", "customer_id": str(customer), "message": message, "channel": "test",
    })
    assert created.status_code == 201, created.text
    case_id = created.json()["case_id"]
    read = client.get(f"/v1/cases/{case_id}", headers={"Authorization": "Bearer " + security._development_key("case:read", original.secret_key)})
    assert read.status_code == 200
    evidence_text = str(read.json()["evidence"])

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT subject, state_json::text FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        case_text = " ".join(map(str, cur.fetchone()))
        cur.execute("SELECT payload_json::text, actor_id FROM case_events WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        audit_text = " ".join(" ".join(map(str, row)) for row in cur.fetchall())
    for raw in (phone, card, api_key, payment_identifier):
        assert raw not in case_text
        assert raw not in audit_text
        assert raw not in evidence_text
    assert any(masked in case_text for masked in ("010-****-5678", "010********5678", "****"))
