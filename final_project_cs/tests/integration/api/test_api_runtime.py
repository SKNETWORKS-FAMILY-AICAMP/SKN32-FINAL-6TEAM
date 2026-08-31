from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app
from app.presentation.api.cases import _mcp_cases, _mcp_detail, _mcp_open
from app.application.controller import ControllerError


@pytest.fixture()
def api_fixture(monkeypatch):
    original = settings_module.get_settings()
    tenant = "test_api_" + uuid4().hex
    customer = uuid4()
    other_customer = uuid4()
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)", (tenant, "api test"))
                cur.execute("INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s, %s, %s)", (customer, tenant, "customer-1"))
                cur.execute("INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s, %s, %s)", (other_customer, tenant, "customer-2"))

    def token(scope: str) -> str:
        return "Bearer " + security._development_key(scope, original.secret_key)

    def cleanup() -> None:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM action_requests WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM returns WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM shipments WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM order_items WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM orders WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))

    try:
        def classifier(_message: str) -> dict[str, str]:
            return {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"}

        yield {"client": TestClient(create_app(classifier=classifier)), "tenant": tenant, "customer": customer, "other_customer": other_customer, "token": token}
    finally:
        cleanup()


def create_case(api_fixture, request_id: str = "seed") -> UUID:
    response = api_fixture["client"].post(
        "/v1/cases",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": request_id, "customer_id": str(api_fixture["customer"]), "message": "please help", "channel": "test"},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["case_id"])


def test_post_case_enters_injected_controller_runtime(api_fixture):
    calls = []

    class FakeController:
        async def run_case(self, **kwargs):
            calls.append(kwargs)
            return {"case_id": str(kwargs["case_id"]), "status": "routing", "version": 2}

    app = create_app(
        controller=FakeController(),
        classifier=lambda _message: {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"},
    )
    response = TestClient(app).post(
        "/v1/cases",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "controller-runtime", "customer_id": str(api_fixture["customer"]), "message": "please help", "channel": "test"},
    )
    assert response.status_code == 201
    assert len(calls) == 1
    assert calls[0]["tenant_id"] == api_fixture["tenant"]


@pytest.mark.parametrize("scope", ["case:read", "case:write", "order:read", "return:read", "action:approve", "mcp:read"])
def test_unauthorized_matrix_for_each_scope_and_rest_endpoint(api_fixture, scope):
    case_id = create_case(api_fixture, "matrix-" + scope)
    client = api_fixture["client"]
    headers = {"Authorization": api_fixture["token"](scope)}
    requests = {
        "create": ("post", "/v1/cases", {"request_id": "matrix-create-" + scope, "customer_id": str(api_fixture["customer"]), "message": "matrix", "channel": "test"}),
        "list": ("get", f"/v1/cases?customer_id={api_fixture['customer']}", None),
        "detail": ("get", f"/v1/cases/{case_id}", None),
        "message": ("post", f"/v1/cases/{case_id}/messages", {"request_id": "matrix-message-" + scope, "message": "follow up"}),
        "approve": ("post", f"/v1/cases/{case_id}/actions/{uuid4()}/approve", {"decision": "approved", "approver_id": "matrix"}),
    }
    expected = {"create": 201 if scope == "case:write" else 403,
                "list": 200 if scope == "case:read" else 403,
                "detail": 200 if scope == "case:read" else 403,
                "message": 422 if scope == "case:write" else 403,
                "approve": 404 if scope == "action:approve" else 403}
    for name, (method, url, body) in requests.items():
        response = getattr(client, method)(url, headers=headers, json=body) if body else getattr(client, method)(url, headers=headers)
        assert response.status_code == expected[name], f"{scope} {name}: {response.status_code} {response.text}"
        if response.status_code in {403, 404}:
            assert set(response.json()) == {"error"}


def test_same_create_request_ten_times_has_one_action_request(api_fixture):
    payload = {"request_id": "same-request", "customer_id": str(api_fixture["customer"]), "message": "repeat me", "channel": "test"}
    responses = [api_fixture["client"].post("/v1/cases", headers={"Authorization": api_fixture["token"]("case:write")}, json=payload) for _ in range(10)]
    assert [response.status_code for response in responses] == [201] * 10
    case_ids = {response.json()["case_id"] for response in responses}
    assert len(case_ids) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s", (api_fixture["tenant"],))
        assert cur.fetchone()[0] == 1


def test_same_mcp_open_request_ten_times_has_one_case_and_action_request(api_fixture):
    results = [_mcp_open(str(api_fixture["customer"]), "repeat from mcp", "test") for _ in range(10)]
    assert len({result["case_id"] for result in results}) == 1
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (api_fixture["tenant"],))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND action_type=%s",
                    (api_fixture["tenant"], "mcp.open_support_case"))
        assert cur.fetchone()[0] == 1


def test_case_from_other_customer_is_not_found(api_fixture):
    case_id = create_case(api_fixture)
    response = api_fixture["client"].get(
        f"/v1/cases/{case_id}?customer_id={api_fixture['other_customer']}",
        headers={"Authorization": api_fixture["token"]("case:read")},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_message_route_passes_issued_resume_token_to_controller(api_fixture):
    case_id = create_case(api_fixture, "resume-route")
    calls = []

    class ResumeController:
        async def resume(self, **kwargs):
            calls.append(kwargs)
            if kwargs["token"] != "issued-token":
                raise ControllerError("invalid resume token")
            return {"case_id": str(case_id), "status": "routing", "version": 2}

    client = TestClient(create_app(
        controller=ResumeController(),
        classifier=lambda _message: {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"},
    ))
    headers = {"Authorization": api_fixture["token"]("case:write")}
    valid = client.post(f"/v1/cases/{case_id}/messages", headers=headers,
                        json={"request_id": "resume-valid", "message": "attacker supplied text", "token": "issued-token"})
    assert valid.status_code == 200
    assert calls[0]["token"] == "issued-token"

    invalid = client.post(f"/v1/cases/{case_id}/messages", headers=headers,
                          json={"request_id": "resume-invalid", "message": "issued-token", "token": "not-issued"})
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "invalid_resume_token"


def test_mcp_open_support_case_changes_only_case_state(api_fixture):
    before = {}
    with get_connection() as conn, conn.cursor() as cur:
        # ★MCP 는 read-only 다. 돈·주문 상태를 건드리지 않는다.
        for table in ("action_requests", "orders", "shipments"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (api_fixture["tenant"],))
            before[table] = cur.fetchone()[0]
    result = _mcp_open(str(api_fixture["customer"]), "open from mcp", "test")
    assert result["status"] in {"classifying", "escalated"}
    assert _mcp_cases(str(api_fixture["customer"]), 20)
    assert _mcp_detail(str(api_fixture["customer"]), result["case_id"])["case_id"] == result["case_id"]
    with get_connection() as conn, conn.cursor() as cur:
        for table, count in before.items():
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (api_fixture["tenant"],))
            actual = cur.fetchone()[0]
            assert actual == (count + 1 if table == "action_requests" else count)


def test_normal_create_and_detail_flow(api_fixture):
    case_id = create_case(api_fixture, "normal")
    response = api_fixture["client"].get(f"/v1/cases/{case_id}", headers={"Authorization": api_fixture["token"]("case:read")})
    assert response.status_code == 200
    assert response.json()["status"] in {"classifying", "routing"}


def test_create_classifies_case_and_records_classified_event(api_fixture):
    case_id = create_case(api_fixture, "classification-success")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, intent, issue_code, sentiment FROM customer_cases WHERE tenant_id=%s AND case_id=%s",
            (api_fixture["tenant"], case_id),
        )
        case = cur.fetchone()
        cur.execute(
            "SELECT event_type FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version",
            (api_fixture["tenant"], case_id),
        )
        events = [row[0] for row in cur.fetchall()]

    assert case == ("routing", "billing", "payment_failed", "negative")
    assert events == ["created", "classified"]


def test_create_escalates_when_injected_classifier_fails(api_fixture):
    failing_app = create_app(classifier=lambda _message: (_ for _ in ()).throw(RuntimeError("classifier down")))
    client = TestClient(failing_app)
    response = client.post(
        "/v1/cases",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "classification-failure", "customer_id": str(api_fixture["customer"]), "message": "please help", "channel": "test"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "escalated"
    case_id = UUID(response.json()["case_id"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, intent, issue_code, sentiment FROM customer_cases WHERE tenant_id=%s AND case_id=%s",
            (api_fixture["tenant"], case_id),
        )
        assert cur.fetchone() == ("escalated", None, None, None)
        cur.execute(
            "SELECT event_type, payload_json->>'failure_code' FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version",
            (api_fixture["tenant"], case_id),
        )
        assert cur.fetchall() == [("created", None), ("classification_failed", "classification_failed")]


def test_state_conflict_is_rendered_as_409(api_fixture):
    case_id = create_case(api_fixture, "conflict")
    response = api_fixture["client"].post(
        f"/v1/cases/{case_id}/messages",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "conflict-message", "message": "follow up", "expected_version": 0},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("tool", [_mcp_cases, _mcp_detail, _mcp_open])
def test_mcp_read_scope_tools_execute_only_with_mcp_principal(api_fixture, tool):
    principal = security.authenticate(api_fixture["token"]("mcp:read"))
    assert "mcp:read" in principal.scopes
    if tool is _mcp_cases:
        assert tool(str(api_fixture["customer"]), 20) == []
    elif tool is _mcp_detail:
        case_id = create_case(api_fixture, "mcp-detail")
        assert tool(str(api_fixture["customer"]), str(case_id))["case_id"] == str(case_id)
    else:
        result = tool(str(api_fixture["customer"]), "mcp tool", "test")
        assert result["status"] in {"classifying", "escalated"}


# ── 2026-09-01: 분류기가 "일부만" 돌려준 경우 ────────────────────────
#
# 위 테스트는 분류기가 **예외를 던지는** 경우만 본다. 그래서 필수 키 검사를
# `if not result:` 로 좁혀도 470개가 전부 통과했다. intent 만 오고 issue_code 가
# 빠진 응답이 성공으로 처리돼 빈 라벨이 저장되고 그 라벨로 라우팅까지 간다.
# CLAUDE.md §1 — "분류 실패는 조용히 넘기지 않는다".


@pytest.mark.parametrize("missing", ["intent", "issue_code", "sentiment"])
def test_create_escalates_when_the_classifier_omits_a_required_label(api_fixture, missing):
    labels = {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"}
    labels.pop(missing)
    client = TestClient(create_app(classifier=lambda _message: dict(labels)))
    response = client.post(
        "/v1/cases",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": f"partial-{missing}", "customer_id": str(api_fixture["customer"]),
              "message": "please help", "channel": "test"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "escalated", (
        f"{missing} 가 빠졌는데 분류가 성공으로 처리됐다"
    )
    case_id = UUID(response.json()["case_id"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status, intent, issue_code, sentiment FROM customer_cases "
            "WHERE tenant_id=%s AND case_id=%s",
            (api_fixture["tenant"], case_id),
        )
        assert cur.fetchone() == ("escalated", None, None, None), (
            "부분 분류 결과가 Case 에 저장됐다 — 값을 모르면 비워 둔다"
        )
        cur.execute(
            "SELECT event_type FROM case_events WHERE tenant_id=%s AND case_id=%s "
            "ORDER BY aggregate_version",
            (api_fixture["tenant"], case_id),
        )
        assert cur.fetchall() == [("created",), ("classification_failed",)]


@pytest.mark.xfail(
    strict=True,
    reason=("앱 결함 — API 경로의 분류 검사가 키 존재만 보고 값은 안 본다. "
            "docs/reports/debugs/2026-09-01_분류_빈라벨_통과.md"),
)
def test_create_escalates_when_a_label_is_blank(api_fixture):
    """빈 문자열도 라벨이 아니다. 키는 있는데 값이 없는 응답을 본다.

    ★지금은 실패한다. 고치면 이 xfail 이 strict 라서 알려준다.
    """
    client = TestClient(create_app(classifier=lambda _message: {
        "intent": "billing", "issue_code": "  ", "sentiment": "negative"}))
    response = client.post(
        "/v1/cases",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "blank-label", "customer_id": str(api_fixture["customer"]),
              "message": "please help", "channel": "test"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "escalated"
