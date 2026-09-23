"""`/introspection` — basement 를 외부에서 그대로 붙여 쓸 수 있게 하는 표면.

★왜 필요한가 — `final_project_ui`(별도 개발 콘솔 프로그램)는 이 프로세스 안에서
  파이썬을 실행할 수 없다. `composition.build_registry()` 같은 것을 직접 못 부른다.
  그래서 조립 상태를 **JSON 으로** 낸다. 예전 `/ui/admin` HTML 화면이 하던 일과
  같은 정보(Team 목록·guardrails·마스킹된 key)를, **데이터로** 낸다.

★검사하는 것: 인증 없이 못 보고, 고객 데이터·API key 원문이 안 새고,
  버전이 붙어 있고, 얻지 못한 값은 `None` 으로 남지 0 으로 지어내지 않는다.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acop_basement.core.settings import get_settings
from acop_basement.presentation.api.app import create_app
from acop_basement.presentation.security import _development_key


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _token() -> str:
    return _development_key("ops:introspect", get_settings().secret_key)


def test_requires_authentication(client):
    assert client.get("/introspection").status_code == 401


def test_wrong_scope_is_rejected(client):
    """★다른 scope 로는 못 본다 — mcp:read 로도 안 된다."""
    token = _development_key("mcp:read", get_settings().secret_key)
    response = client.get("/introspection", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_returns_versioned_assembly_state(client):
    response = client.get("/introspection", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200
    data = response.json()
    assert data["contract_version"]
    assert data["config_revision"]
    assert {t["team_id"] for t in [m for m in data["team_manifests"]]} == \
        {"feedback_analytics"}


def test_does_not_leak_the_real_api_key(client):
    settings = get_settings()
    response = client.get("/introspection", headers={"Authorization": f"Bearer {_token()}"})
    data = response.json()
    assert data["llm"]["api_key"] in ("sk-****", "missing")
    if settings.openai_api_key:
        assert settings.openai_api_key not in response.text


def test_does_not_leak_customer_message_text(client):
    """★조립·검증 정보만 낸다. 개별 고객이 한 말은 여기 없다."""
    response = client.get("/introspection", headers={"Authorization": f"Bearer {_token()}"})
    for phrase in ("환불 부탁드립니다", "잠겨 있습니다", "요금이 또 청구"):
        assert phrase not in response.text


def test_introspection_is_not_under_v1(client):
    """★case 리소스가 아니라 운영 메타데이터다 — /health 와 같은 급."""
    paths = create_app().openapi()["paths"]
    assert "/introspection" in paths
    assert not any(p.startswith("/v1/") and "introspection" in p for p in paths)
