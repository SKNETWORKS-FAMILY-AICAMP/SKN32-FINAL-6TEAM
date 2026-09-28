from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.infrastructure.db.session import get_connection
from tests.integration.api.test_api_runtime import api_fixture  # noqa: F401


def _seed_unknown(api_fixture):
    message_id = uuid4()
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO outbox (message_id, tenant_id, topic, dedupe_key, payload_json, status) "
            "VALUES (%s,%s,%s,%s,%s,'unknown')",
            (message_id, api_fixture["tenant"], "test.provider", "resolve-" + uuid4().hex,
             Json({"case_id": str(uuid4()), "provider_ref": "ref-1"})),
        )
    return message_id


def test_outbox_resolution_requires_auth_and_scope_and_records_only_metadata(api_fixture):
    message_id = _seed_unknown(api_fixture)
    client = api_fixture["client"]
    body = {"resolution": "confirmed_delivered", "note": "provider console confirms delivery", "resolved_by": "operator-1"}

    assert client.post(f"/v1/outbox/{message_id}/resolve", json=body).status_code == 401
    assert client.post(f"/v1/outbox/{message_id}/resolve", headers={"Authorization": api_fixture["token"]("case:read")}, json=body).status_code == 403

    response = client.post(f"/v1/outbox/{message_id}/resolve",
                           headers={"Authorization": api_fixture["token"]("action:approve")}, json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "unknown"
    assert result["resolved_by"] == "operator-1"
    assert result["resolution"] == "confirmed_delivered"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, resolved_at, resolved_by, resolution, resolution_note FROM outbox WHERE message_id=%s", (message_id,))
        assert cur.fetchone()[:1] == ("unknown",)
        cur.execute("SELECT status, resolved_at, resolved_by, resolution, resolution_note FROM outbox WHERE message_id=%s", (message_id,))
        status, resolved_at, resolved_by, resolution, note = cur.fetchone()
        assert status == "unknown" and resolved_at is not None
        assert (resolved_by, resolution, note) == ("operator-1", "confirmed_delivered", body["note"])
