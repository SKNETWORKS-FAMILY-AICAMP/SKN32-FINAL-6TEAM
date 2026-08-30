"""설정 서비스 — 중앙 1곳에서 여러 대상의 구성을 관리한다.

★핵심 성질 셋
  1. 고객 API 가 **없다** — 이 앱은 구성 관리만 한다
  2. 대상을 **요청**이 지정한다(`X-Deployment-Id`). 헤더가 없으면 거부한다 —
     기본 대상으로 떨어지면 남의 설정을 건드리는 사고가 조용히 일어난다
  3. 대상끼리 **격리**된다 — A 를 바꿔도 B 는 그대로다
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient

from acop_basement.core.config_store import PostgresConfigStore
from acop_basement.core.settings import get_settings
from acop_basement.infrastructure.db.session import get_connection
from acop_composer.api import DEPLOYMENT_HEADER
from acop_composer.service_app import create_config_service_app


def _auth(scope: str = "composer:write") -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "config-service-test", "aud": "final_project_sample", "scope": [scope],
         "iat": now, "exp": now + timedelta(minutes=30), "jti": str(uuid4())},
        get_settings().composer_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _headers(deployment_id: str, scope: str = "composer:write") -> dict[str, str]:
    return {**_auth(scope), DEPLOYMENT_HEADER: deployment_id}


def _declaration() -> dict:
    return yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))


def _register(deployment_id: str) -> None:
    PostgresConfigStore(get_connection, deployment_id).create(_declaration())


def _cleanup(*deployment_ids: str) -> None:
    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            for deployment_id in deployment_ids:
                cur.execute("DELETE FROM project_configs WHERE deployment_id = %s",
                            (deployment_id,))
                cur.execute("DELETE FROM composer_audit_events WHERE deployment_id = %s",
                            (deployment_id,))


@pytest.fixture()
def service():
    return TestClient(create_config_service_app())


@pytest.fixture()
def deployments():
    ids = ["test-svc-a-" + uuid4().hex, "test-svc-b-" + uuid4().hex]
    for deployment_id in ids:
        _register(deployment_id)
    try:
        yield ids
    finally:
        _cleanup(*ids)


# ── 이 앱이 무엇이 아닌지 ────────────────────────────────────────────
def test_the_config_service_does_not_serve_the_customer_api(service):
    """★고객 API 가 여기 있으면 안 된다 — 구성 관리 전용이다."""
    paths = create_config_service_app().openapi()["paths"]

    assert "/composer/changes" in paths and "/auth/token" in paths
    assert not [p for p in paths if p.startswith("/v1/")], f"고객 API 가 섞였다: {paths}"
    assert not [p for p in paths if p.startswith("/ops/")], "운영 UI 가 섞였다"


def test_health_says_which_service_this_is(service):
    body = service.get("/health").json()
    assert body["status"] == "ok" and body["service"] == "config"


# ── 대상 지정 ────────────────────────────────────────────────────────
def test_missing_deployment_header_is_refused(service, deployments):
    """★기본 대상으로 떨어지면 남의 설정을 건드린다."""
    response = service.get("/composer/current", headers=_auth("composer:read"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "deployment_required"


def test_reads_the_declaration_of_the_requested_deployment(service, deployments):
    first, _second = deployments
    response = service.get("/composer/current", headers=_headers(first, "composer:read"))

    assert response.status_code == 200
    assert response.json()["config"]["teams"]


def test_unregistered_deployment_is_not_silently_created(service):
    unknown = "test-svc-missing-" + uuid4().hex
    response = service.get("/composer/current", headers=_headers(unknown, "composer:read"))

    assert response.status_code >= 400, "등록 안 된 대상이 조용히 성공하면 안 된다"


# ── 대상 격리 ────────────────────────────────────────────────────────
def test_changing_one_deployment_leaves_the_other_untouched(service, deployments):
    """★중앙 서비스의 핵심 성질 — 대상끼리 서로 안 보인다."""
    first, second = deployments
    revision = service.get("/composer/current",
                           headers=_headers(first, "composer:read")).json()["revision"]

    changed = service.post("/composer/changes", headers=_headers(first), json={
        "operation": "disable", "resource_type": "team",
        "instance_id": "feedback_analytics", "base_revision": revision,
        "reason": "격리 확인"})
    assert changed.status_code == 200, changed.text

    after_first = service.get("/composer/current",
                              headers=_headers(first, "composer:read")).json()
    after_second = service.get("/composer/current",
                               headers=_headers(second, "composer:read")).json()

    assert after_first["config"]["teams"][0]["active"] is False
    assert after_second["config"]["teams"][0]["active"] is True, "다른 대상이 바뀌었다"


def test_audit_is_scoped_to_the_deployment(service, deployments):
    first, second = deployments
    revision = service.get("/composer/current",
                           headers=_headers(first, "composer:read")).json()["revision"]
    service.post("/composer/changes", headers=_headers(first), json={
        "operation": "disable", "resource_type": "team",
        "instance_id": "feedback_analytics", "base_revision": revision,
        "reason": "감사 격리 확인"})

    from acop_basement.core.audit_store import PostgresAuditStore

    assert PostgresAuditStore(get_connection, first).recent(10), "감사가 남아야 한다"
    assert PostgresAuditStore(get_connection, second).recent(10) == [], \
        "다른 대상의 감사가 보이면 안 된다"


def test_catalog_works_per_deployment(service, deployments):
    first, _second = deployments
    response = service.get("/composer/catalog", headers=_headers(first, "composer:read"))

    assert response.status_code == 200
    ids = {e["implementation_id"] for e in response.json()["implementations"]}
    assert "team.declarative.v1" in ids
