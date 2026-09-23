from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import acop_basement.core.settings as settings_module
from acop_basement.presentation import security
from acop_basement.presentation.api.app import create_app
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.infrastructure.messaging.worker import OutboxWorker

from ..controller.test_controller_integration import db  # noqa: F401


def _unknown(conn, tenant: str, *, topic: str = "test.resolve") -> str:
    message_id = uuid4()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO outbox (message_id,tenant_id,topic,dedupe_key,payload_json,status,last_error) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (message_id, tenant, topic, str(message_id), '{"reference":"x"}', "unknown", "timeout"))
    conn.commit()
    return str(message_id)


@pytest.fixture()
def outbox_client(db, monkeypatch):
    conn, tenant = db
    original = settings_module.get_settings()
    configured = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: configured)
    monkeypatch.setattr(security, "get_settings", lambda: configured)
    token = security._development_key("action:approve", original.secret_key)
    return conn, tenant, TestClient(create_app()), {"Authorization": f"Bearer {token}"}


def test_unknown_is_visible_in_ops_screen(outbox_client):
    conn, tenant, client, _ = outbox_client
    message_id = _unknown(conn, tenant)
    response = client.get("/ops/outbox")
    assert response.status_code == 200
    assert str(message_id) in response.text
    assert "배달 확인됨" in response.text


def test_resolution_requires_a_note(outbox_client):
    conn, tenant, client, headers = outbox_client
    message_id = _unknown(conn, tenant)
    response = client.post(f"/v1/outbox/{message_id}/resolve", headers=headers,
                           json={"resolution": "confirmed_delivered", "note": " ", "resolved_by": "operator"})
    assert response.status_code == 422


@pytest.mark.parametrize("resolution", ["confirmed_delivered", "confirmed_not_delivered"])
def test_terminal_resolution_does_not_publish(outbox_client, resolution):
    conn, tenant, client, headers = outbox_client
    message_id = _unknown(conn, tenant)
    response = client.post(f"/v1/outbox/{message_id}/resolve", headers=headers,
                           json={"resolution": resolution, "note": "checked downstream log", "resolved_by": "operator"})
    assert response.status_code == 200
    with conn.cursor() as cur:
        cur.execute("SELECT status, attempts, resolution FROM outbox WHERE message_id=%s", (message_id,))
        assert cur.fetchone() == ("resolved", 0, resolution)
    calls = []
    assert OutboxWorker(get_connection, calls.append, tenant_id=tenant).process_once() is False
    assert calls == []


def test_requeue_is_pending_and_worker_can_claim_it(outbox_client):
    conn, tenant, client, headers = outbox_client
    message_id = _unknown(conn, tenant)
    response = client.post(f"/v1/outbox/{message_id}/resolve", headers=headers,
                           json={"resolution": "requeue", "note": "delivery absent in downstream log", "resolved_by": "operator"})
    assert response.status_code == 200
    with conn.cursor() as cur:
        cur.execute("SELECT status, attempts FROM outbox WHERE message_id=%s", (message_id,))
        assert cur.fetchone() == ("pending", 0)
    calls = []
    assert OutboxWorker(get_connection, calls.append, tenant_id=tenant).process_once() is True
    assert len(calls) == 1


def test_other_tenant_is_not_resolvable(outbox_client):
    conn, tenant, client, headers = outbox_client
    foreign = "foreign_" + uuid4().hex
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (foreign, "foreign"))
    message_id = _unknown(conn, foreign)
    response = client.post(f"/v1/outbox/{message_id}/resolve", headers=headers,
                           json={"resolution": "requeue", "note": "checked", "resolved_by": "operator"})
    assert response.status_code == 404
    with conn.cursor() as cur:
        cur.execute("DELETE FROM outbox WHERE message_id=%s", (message_id,))
        cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (foreign,))
    conn.commit()


def test_resolved_row_cannot_be_resolved_again(outbox_client):
    conn, tenant, client, headers = outbox_client
    message_id = _unknown(conn, tenant)
    payload = {"resolution": "confirmed_delivered", "note": "checked", "resolved_by": "operator"}
    assert client.post(f"/v1/outbox/{message_id}/resolve", headers=headers, json=payload).status_code == 200
    response = client.post(f"/v1/outbox/{message_id}/resolve", headers=headers, json=payload)
    # ★404 가 아니라 409 다 — 계약(S-UNKNOWN-OPS-SCREEN.md)이 명시한 구분:
    #   행이 없거나 남의 tenant 것 = 404, 행은 있는데 이미 처리됨(status != 'unknown') = 409.
    #   구현(app/presentation/api/outbox.py)은 이 구분을 지키는데 이 테스트만 404 를
    #   기대하고 있었다 — 실측 재현: 두 번째 요청은 실제로 409 를 반환한다.
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status"
