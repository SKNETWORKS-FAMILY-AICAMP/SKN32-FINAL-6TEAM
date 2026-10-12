"""고객 웹·SSE 입구에서 기능 안내 검색, 일정 불변, 인증, 중복을 확인한다."""
import pytest
from fastapi.testclient import TestClient

from app.domains.travel_ops.components.conversation import trip_messages
from app.domains.travel_ops.entry.trip_api import build_trip_router
from app.infrastructure.db.session import get_connection
from app.presentation.api.app import create_app
from tests.helpers.plugin_bindings import publish_fixed_mobility
from tests.unit.travel.test_service_help import ServiceModel, chunk

from .test_web_api import _fresh_limit_cache, _h, _session, _web_body, api  # noqa: F401


@pytest.fixture
def help_client(api, monkeypatch):
    monkeypatch.setattr(trip_messages, "_decision_mode", lambda chat, tenant=None: "on")
    requests = []

    def search(**kwargs):
        requests.append(kwargs)
        return [chunk()]

    client = TestClient(create_app(domain_routers=[build_trip_router(
        chat_factory=ServiceModel, policy_search_factory=lambda: search)]))
    publish_fixed_mobility(client.app, source="service_help_test")
    me = _session(api)
    response = client.post("/v1/web/trips", json=_web_body(api, request_id="service-trip"), headers=_h(me["user_key"]))
    assert response.status_code == 201, response.text
    trip = response.json()
    return client, me, trip, requests


def test_service_help_resolves_without_changing_trip_and_is_idempotent(help_client, api):
    client, me, trip, requests = help_client
    path = f"/v1/web/trips/{trip['trip_id']}"
    before = client.get(path, headers=_h(me["user_key"])).json()
    payload = {"request_id": "service-query", "message": "너가 할 수 있는 게 뭐야?"}
    response = client.post(path + "/messages", headers=_h(me["user_key"]), json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "answered" and body["reason"] == "decision_answer_service"
    assert "triPilot 여행 도우미" in body["answer"] and "basis" not in body
    after = client.get(path, headers=_h(me["user_key"])).json()
    assert (after["version"], after["items"]) == (before["version"], before["items"])
    assert requests[0]["tenant_id"] == api["tenant"] and requests[0]["allowed_scopes"] == ["travel_service"]
    duplicate = client.post(path + "/messages", headers=_h(me["user_key"]), json=payload).json()
    assert duplicate["status"] == "duplicate" and len(requests) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT state_json FROM customer_cases WHERE case_id=%s", (body["case_id"],))
        state = cur.fetchone()[0]
    assert state["trip_outcome"]["basis"]["sources"] == ["t_service_01#c1"]


def test_service_help_cannot_read_another_customers_trip(help_client, api):
    client, _, trip, requests = help_client
    stranger = _session(api)
    response = client.post(f"/v1/web/trips/{trip['trip_id']}/messages", headers=_h(stranger["user_key"]),
                           json={"request_id": "stranger-help", "message": "사용법 알려줘"})
    assert response.status_code == 404 and not requests


def test_service_help_sse_returns_the_same_grounded_answer(help_client):
    client, me, trip, requests = help_client
    response = client.post(f"/v1/web/trips/{trip['trip_id']}/messages",
                           headers={**_h(me["user_key"]), "Accept": "text/event-stream"},
                           json={"request_id": "service-stream", "message": "어떤 기능이 있어?"})
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    assert "decision_answer_service" in response.text and "triPilot 여행 도우미" in response.text
    assert len(requests) == 1
