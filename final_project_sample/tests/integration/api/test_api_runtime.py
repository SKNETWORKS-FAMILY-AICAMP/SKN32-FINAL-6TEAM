from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import acop_basement.core.settings as settings_module
from acop_basement.core.contracts import StateConflict
from acop_basement.infrastructure.db.repository import get_case
from acop_basement.infrastructure.db.session import get_connection
from acop_basement.presentation import security
from acop_basement.presentation.api.app import create_app
from acop_basement.presentation.api.cases import _mcp_cases, _mcp_detail, _mcp_open


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
                    # ★버그사냥 2026-08-17 (라운드 08) — 이 fixture 는 지금까지
                    #   controller 가 사실상 None 이라 agent_runs 가 생긴 적이
                    #   없었다(레거시 test seam). resume() 을 실제로 태우는
                    #   테스트를 추가하면서 처음 걸렸다: agent_runs 를 안 지우면
                    #   customer_cases 삭제가 FK 위반으로 실패한다.
                    cur.execute("DELETE FROM team_tasks WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM llm_calls WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)", (tenant,))
                    cur.execute("DELETE FROM agent_runs WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM case_events WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM incidents WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM payments WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM entitlements WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM subscriptions WHERE tenant_id=%s", (tenant,))
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


@pytest.mark.parametrize("scope", ["case:read", "case:write", "subscription:read", "technical:read", "action:approve", "mcp:read"])
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


def test_case_from_other_customer_is_not_found(api_fixture):
    case_id = create_case(api_fixture)
    response = api_fixture["client"].get(
        f"/v1/cases/{case_id}?customer_id={api_fixture['other_customer']}",
        headers={"Authorization": api_fixture["token"]("case:read")},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_mcp_open_support_case_changes_only_case_state(api_fixture):
    """★DoD-13 이 지키는 것은 payments/subscriptions 를 안 건드리는 것이다 —
    action_requests 는 이제 idempotency 기록을 위해 정확히 1행 늘어난다
    (버그사냥 2026-08-17 이후, 아래 idempotent 테스트 참조)."""
    before = {}
    with get_connection() as conn, conn.cursor() as cur:
        for table in ("action_requests", "payments", "subscriptions"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (api_fixture["tenant"],))
            before[table] = cur.fetchone()[0]
    result = _mcp_open(str(api_fixture["customer"]), "open from mcp", "test")
    assert result["status"] in {"classifying", "escalated"}
    assert _mcp_cases(str(api_fixture["customer"]), 20)
    assert _mcp_detail(str(api_fixture["customer"]), result["case_id"])["case_id"] == result["case_id"]
    with get_connection() as conn, conn.cursor() as cur:
        for table in ("payments", "subscriptions"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (api_fixture["tenant"],))
            assert cur.fetchone()[0] == before[table]
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s", (api_fixture["tenant"],))
        assert cur.fetchone()[0] == before["action_requests"] + 1


def test_mcp_open_support_case_is_idempotent(api_fixture):
    """★버그사냥 2026-08-17 — request_id 를 계산만 하고 안 써서 같은 재시도가
    매번 새 Case 를 만들고 있었다. REST POST /v1/cases 는 이미 이 보장이
    있었는데(DoD-11) MCP 경로만 빠져 있었다."""
    customer = str(api_fixture["customer"])
    first = _mcp_open(customer, "same message twice", "test")
    second = _mcp_open(customer, "same message twice", "test")
    assert first["case_id"] == second["case_id"], "동일 재시도가 다른 Case 를 만들었다"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM action_requests WHERE tenant_id=%s AND action_type='mcp.open_support_case'",
                    (api_fixture["tenant"],))
        assert cur.fetchone()[0] == 1


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


def test_create_does_not_relabel_a_transition_bug_as_classification_failure(api_fixture, monkeypatch):
    """★버그사냥 2026-08-18 (라운드 08) — `classifier()` 호출뿐 아니라 뒤이은
    `transition_case(...CLASSIFIED...)` 호출 자체의 실패(예: `StateConflict`)까지
    같은 `except Exception:` 이 잡아 `classification_failed` 로 뭉갰다. 상태
    충돌을 "분류 실패" 로 보고하면 원인을 못 찾는다(CLAUDE.md §3 "오류 메시지가
    사실을 잘못 전하지 않게 한다"). classifier 는 정상 값을 반환했는데도
    이렇게 된다는 게 핵심 — classifier 문제가 아니라 전이 자체의 버그다."""
    import acop_basement.presentation.api.cases as cases_module
    real_transition_case = cases_module.transition_case
    calls = {"n": 0}

    def flaky_transition_case(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # the CLASSIFIED transition — not the classifier call
            raise StateConflict("simulated non-classifier transition bug")
        return real_transition_case(*args, **kwargs)

    monkeypatch.setattr(cases_module, "transition_case", flaky_transition_case)
    app = create_app(classifier=lambda _message: {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"})
    # ★raise_server_exceptions=False — 진짜 원인이 앱의 500 핸들러까지 도달하는지
    #   보려는 것이지, pytest 프로세스로 예외가 그대로 새는지 보려는 게 아니다.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/v1/cases",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "transition-bug-" + uuid4().hex, "customer_id": str(api_fixture["customer"]), "message": "please help", "channel": "test"},
    )
    # ★진짜 원인(StateConflict)이 정직하게 500 으로 드러나야 한다 — classifier
    #   실패인 것처럼 201 + classification_failed 로 조용히 넘어가면 안 된다.
    assert response.status_code == 500
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (api_fixture["tenant"],))
        assert cur.fetchone()[0] == 0, "실패한 전이가 있으면 트랜잭션 전체가 롤백돼야 한다"


def _put_case_in_waiting_input(api_fixture, case_id: UUID) -> str:
    """★버그사냥 2026-08-17 (라운드 04·06·08) — 이 REST 계층 테스트를 위해
    실제 발급 토큰을 가진 waiting_input Case 를 직접 만든다. `api_fixture` 는
    테스트 전용 classifier 를 주입해 `create_app()` 이 실제 controller 를
    라우팅에 안 쓴다("legacy test seam" — controller 를 명시로 안 넘기고
    classifier 모듈도 app.composition 이 아니면 runtime_controller=None) —
    그래서 create_case() 뒤 Case 는 'routing' 에 멈춰 있다. ROUTED 까지
    직접 밀어준 뒤, 지금 프로덕션 Team(billing/technical) 은 WAIT_FOR_INPUT
    을 내지 않으므로 raw 로 같은 경로(Controller._event_for_result 의
    MISSING_INPUT 분기)를 재현한다."""
    from acop_basement.application.case_service import CaseService
    from acop_basement.core.transition import transition_case
    from acop_basement.domain.events import EventType

    service = CaseService()
    token = service.new_resume_token()
    metadata = service.resume_metadata(token, "customer_input")
    with get_connection() as conn:
        with conn.transaction():
            case = get_case(conn, tenant_id=api_fixture["tenant"], case_id=case_id)
            transition_case(conn, tenant_id=api_fixture["tenant"], case_id=case_id, expected_version=case["version"],
                            event_type=EventType.ROUTED,
                            payload={"owner_team_id": "demo_team", "capability": "demo.investigate"},
                            actor_type="test")
            transition_case(conn, tenant_id=api_fixture["tenant"], case_id=case_id, expected_version=case["version"] + 1,
                            event_type=EventType.MISSING_INPUT,
                            payload={"required_input_schema": {"type": "object"}, "state_patch": metadata},
                            actor_type="test")
    return token


def _client_with_resume_capable_controller(api_fixture) -> TestClient:
    """★api_fixture 의 기본 앱은 controller=None("legacy test seam" —
    controller 를 명시로 안 넘기고 classifier 모듈도 app.composition 이
    아니면 runtime_controller=None) 이라 /messages 가 500 misconfigured 를
    낸다. resume() 을 실제로 태우려면 controller 를 명시적으로 주입해야
    한다 — 프로덕션과 같은 실제 Controller 를 쓰되, registry 만 이 테스트의
    owner_team_id 와 맞는 최소 fake Team 하나로 채운다."""
    from acop_basement.application.controller import Controller
    from acop_basement.core.contracts import Evidence, NextAction, TeamManifest, TeamResult
    from acop_basement.core.registry import TeamRegistry
    from datetime import UTC, datetime

    class ResumableTeam:
        manifest = TeamManifest(
            team_id="demo_team", display_name="Test Team", contract_name="a_cop.team_task",
            supported_contract_versions=["1.0"], capabilities=["demo.investigate"],
            accepted_case_types=["billing"], required_context=["case_state", "policy", "db_facts", "history"],
            allowed_tools=[], knowledge_scope=["demo"], implementation_revision="test",
        )

        async def execute(self, task):
            evidence = [Evidence(evidence_id="rest:resume", source_type="db", source_id="fake",
                                 claim="deterministic fixture", value={"ok": True}, confidence=1,
                                 observed_at=datetime.now(UTC))]
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=task.team_id, outcome="completed",
                              confidence=1, answer="resolved after resume", evidence=evidence, next_action=NextAction.RESPOND)

    controller = Controller(TeamRegistry([ResumableTeam()]), policy_search=lambda *_: [])
    app = create_app(controller=controller, classifier=lambda _m: {"intent": "billing", "issue_code": "payment_failed", "sentiment": "negative"})
    return TestClient(app)


def test_messages_endpoint_requires_the_real_resume_token(api_fixture):
    """★버그사냥 2026-08-17 (라운드 04·06·08) — REST 계층에서 진짜 토큰
    검증을 확인한다. 가짜 토큰은 401, 진짜 토큰은 재개·완료까지 이어진다."""
    case_id = create_case(api_fixture, "resume-wrong-token")
    real_token = _put_case_in_waiting_input(api_fixture, case_id)
    client = _client_with_resume_capable_controller(api_fixture)

    wrong = client.post(
        f"/v1/cases/{case_id}/messages",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "resume-attempt", "message": "follow up", "token": "not-the-real-token"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_resume_token"
    with get_connection() as conn:
        assert get_case(conn, tenant_id=api_fixture["tenant"], case_id=case_id)["status"] == "escalated"


def test_messages_endpoint_accepts_the_real_resume_token(api_fixture):
    case_id = create_case(api_fixture, "resume-real-token")
    real_token = _put_case_in_waiting_input(api_fixture, case_id)
    client = _client_with_resume_capable_controller(api_fixture)

    response = client.post(
        f"/v1/cases/{case_id}/messages",
        headers={"Authorization": api_fixture["token"]("case:write")},
        json={"request_id": "resume-attempt", "message": "follow up", "token": real_token},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"


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
