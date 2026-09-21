from __future__ import annotations

from fastapi.testclient import TestClient

from app.presentation import security
from app.presentation.api.app import create_app


def test_introspection_requires_scope_and_returns_snapshot(monkeypatch):
    expected = {
        "contract_version": "1.0",
        "modules": {}, "ports": {}, "team_manifests": [], "teams": [],
        "port_implementations": {}, "guardrails": {},
        "llm": {"provider": "openai", "model": "test", "api_key": "sk-****"},
    }
    # ★2026-09-06 — 라우터가 `snapshot(runtime=...)` 로 부른다(계약 1.1). 실행 중인
    #   조립을 `app.state.runtime` 에서 가져가기 때문이다. 가짜도 그 모양을 받는다.
    monkeypatch.setattr("app.presentation.api.introspection.snapshot",
                        lambda **_kwargs: expected)
    client = TestClient(create_app(classifier=lambda _: {"intent": "x", "issue_code": "x", "sentiment": "neutral"}))

    assert client.get("/introspection").status_code == 401
    token = security._development_key("ops:introspect", security.get_settings().secret_key)
    response = client.get("/introspection", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == expected


def test_introspection_denies_other_scope():
    client = TestClient(create_app(classifier=lambda _: {"intent": "x", "issue_code": "x", "sentiment": "neutral"}))
    token = security._development_key("case:read", security.get_settings().secret_key)
    assert client.get("/introspection", headers={"Authorization": f"Bearer {token}"}).status_code == 403
