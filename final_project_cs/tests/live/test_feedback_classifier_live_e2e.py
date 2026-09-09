"""Real end-to-end proof that the production classifier accepts shopping-
mall intents. Marked ``live`` because it makes real LLM calls -- excluded
by default (pytest.ini ``addopts = -m "not live"``), run explicitly with
``pytest -m live``.

Regression this guards: 2026-08-17, ``feedback.INTENTS`` was still the old
subscription domain (``billing``/``technical``) while ``composition
.build_classifier()`` -- the exact function this test exercises -- is the
default classifier wired into ``POST /v1/cases``. Every real shopping-mall
Case would have failed classification silently (safely escalated, but never
routed). See wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md.

★2026-08-17 수정: ``create_app(controller=None)`` 은 "controller 를 안 붙인다"는
뜻이 아니다. ``app/presentation/api/app.py`` 를 보면, classifier 를 주입하지
않아 실제 ``composition.build_classifier()`` 가 쓰이는 순간 ``runtime_controller``
도 ``composition.build_controller()`` 가 만든 **진짜 controller** 가 된다(제품
경로 그대로). 그래서 이 테스트는 분류 이후 실제 Team 실행까지 전부 탄다 —
이 테스트에 필요한 건 "분류가 맞았는가"뿐이므로, 최종 case 상태가 아니라
**CLASSIFIED case_event 의 payload** 로 그것만 정확히 확인한다. Team 실행 결과가
escalated 로 끝나도(주문 데이터가 없는 합성 고객이라 정상적으로 그럴 수 있다)
이 테스트의 관심사가 아니다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.presentation import security
from app.presentation.api.app import create_app


@pytest.fixture()
def live_api_fixture(monkeypatch):
    original = settings_module.get_settings()
    tenant = "live_classifier_" + uuid4().hex
    customer = uuid4()
    test_settings = original.model_copy(update={"tenant_id": tenant})
    monkeypatch.setattr(settings_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(security, "get_settings", lambda: test_settings)

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO tenants (tenant_id, name) VALUES (%s, %s)",
                    (tenant, "live classifier e2e test"),
                )
                cur.execute(
                    "INSERT INTO customers (customer_id, tenant_id, external_id) VALUES (%s, %s, %s)",
                    (customer, tenant, "live-classifier-customer"),
                )

    def token(scope: str) -> str:
        return "Bearer " + security._development_key(scope, original.secret_key)

    def cleanup() -> None:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # ★controller 가 실제로 실행되므로(위 모듈 docstring 참고) agent_runs
                    #   계열 테이블까지 만들어진다 — FK 순서대로 지운다.
                    cur.execute(
                        "DELETE FROM llm_calls WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)",
                        (tenant,),
                    )
                    cur.execute(
                        "DELETE FROM team_tasks WHERE run_id IN (SELECT run_id FROM agent_runs WHERE tenant_id=%s)",
                        (tenant,),
                    )
                    cur.execute("DELETE FROM agent_runs WHERE tenant_id=%s", (tenant,))
                    cur.execute(
                        "DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s)",
                        (tenant,),
                    )
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
        yield {"tenant": tenant, "customer": customer, "token": token}
    finally:
        cleanup()


@pytest.mark.live
def test_real_classifier_accepts_a_shopping_mall_message_via_the_rest_api(live_api_fixture):
    app = create_app(controller=None)
    client = TestClient(app)
    response = client.post(
        "/v1/cases",
        headers={"Authorization": live_api_fixture["token"]("case:write")},
        json={
            "request_id": "live-classifier-e2e",
            "customer_id": str(live_api_fixture["customer"]),
            "message": "배송완료로 떴는데 상품을 못 받았습니다. 확인 부탁드립니다.",
            "channel": "web",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    case_id = body["case_id"]

    # ★이 테스트의 관심사는 "분류가 새 도메인 어휘를 받아들이는가" 하나뿐이다.
    #   controller=None 이라도 실제 classifier(app.composition 소속)를 쓰는 순간
    #   진짜 Team 까지 실행되므로(모듈 docstring 참고), 최종 case 상태는 seed 되지
    #   않은 합성 고객이라 정상적으로 escalated 로 끝날 수 있다 — 그건 이 테스트가
    #   보증할 범위가 아니다. 대신 CLASSIFIED 이벤트 자체를 직접 확인한다.
    with get_connection() as conn:
        events = repository.get_case_events(
            conn, tenant_id=live_api_fixture["tenant"], case_id=case_id
        )
    classified = [e for e in events if e["event_type"] == "classified"]
    assert classified, f"no CLASSIFIED event was recorded -- classifier rejected the message. events={events}"
    payload = classified[0]["payload_json"]
    assert payload["intent"] in {"order", "shipping", "return", "exchange", "other"}, payload
    assert payload["issue_code"]
    assert payload["sentiment"]

    failed = [e for e in events if e["event_type"] == "classification_failed"]
    assert not failed, f"classifier rejected the message: {failed}"
