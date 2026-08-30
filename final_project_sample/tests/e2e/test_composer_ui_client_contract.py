"""`acop_composer_ui` 클라이언트 ↔ 실제 Composer 서버 계약 대조.

★이 파일의 값어치는 여기 있다 — 클라이언트를 가짜 응답으로만 검사하면
  "우리끼리 맞는" 것만 증명된다. 여기서는 **진짜 FastAPI 앱**을 띄우고
  클라이언트를 그 위에 얹어, 경로·payload·scope·상태코드가 실제 서버와
  맞는지 확인한다. 계약이 어긋나면 여기서 깨진다.

  네트워크는 쓰지 않는다. 클라이언트의 `transport` 를 TestClient 로 갈아
  끼운다 — 그래서 클라이언트가 처음부터 전송을 주입 가능하게 설계돼 있다.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from uuid import uuid4

import pytest
import yaml
from fastapi.testclient import TestClient

# ★packages/ 는 별도 배포 단위라 저장소 루트의 sys.path 에 없다. 설치 없이
#   검사할 수 있도록 여기서만 경로를 더한다(제품 코드는 이러지 않는다).
_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "packages" / "acop_composer_ui"
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from acop_composer_ui import ComposerClient  # noqa: E402

from acop_basement.core.settings import get_settings  # noqa: E402
from acop_basement.presentation.api.app import create_app  # noqa: E402
from acop_composer.api import router as composer_write_router  # noqa: E402
from acop_composer.auth import router as composer_auth_router  # noqa: E402


@pytest.fixture()
def config_dir():
    path = Path(".composer-ui-client-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


@pytest.fixture()
def client(config_dir):
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    declaration = config_dir / "project.yaml"
    declaration.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                           encoding="utf-8")

    app = create_app(composer_write_router=composer_write_router,
                     composer_auth_router=composer_auth_router)
    app.state.project_config_path = declaration
    app.state.composer_audit_path = declaration.with_name("composer_events.jsonl")
    http = TestClient(app)

    def transport(method, url, headers, body):
        response = http.request(method, url, headers=headers, content=body)
        return response.status_code, response.content

    composer = ComposerClient("http://target.invalid",
                              issuer_secret=get_settings().composer_issuer_secret,
                              transport=transport)
    return composer, declaration


def test_catalog_round_trips_through_the_real_server(client):
    composer, _ = client
    response = composer.catalog()

    assert response.ok, response.error
    ids = {e["implementation_id"] for e in response.payload["implementations"]}
    assert "team.declarative.v1" in ids
    assert response.payload["config_revision"]


def test_toggle_round_trips_and_reports_pending_restart(client):
    composer, declaration = client
    revision = composer.read_current().payload["revision"]

    response = composer.toggle(target_type="team", target_id="feedback_analytics",
                               active=False, base_revision=revision, reason="UI 클라이언트 검사")

    assert response.ok, response.error
    assert response.payload["activation_state"] == "pending_restart"
    assert yaml.safe_load(declaration.read_text(encoding="utf-8"))["teams"][0]["active"] is False


def test_change_creates_a_declarative_team_without_any_code_deploy(client):
    """★UI 가 보낼 명령만으로 새 Team 이 생긴다 — 이 패키지의 존재 이유."""
    composer, declaration = client
    revision = composer.read_current().payload["revision"]

    response = composer.change(
        operation="create", resource_type="team", instance_id="ui_created",
        implementation_id="team.declarative.v1",
        parameters={"display_name": "UI 가 만든 Team", "capabilities": ["demo.ui_created"],
                    "accepted_case_types": ["demo"], "required_context": ["case_state"],
                    "allowed_tools": ["read.policy"], "knowledge_scope": ["demo"],
                    "max_steps": 3, "prompt_key": "declarative.ui_created"},
        base_revision=revision, reason="UI 클라이언트 검사")

    assert response.ok, response.error
    assert response.payload["activation_state"] == "pending_restart"
    teams = yaml.safe_load(declaration.read_text(encoding="utf-8"))["teams"]
    assert any(t["team_id"] == "ui_created" for t in teams)


def test_dry_run_does_not_touch_the_declaration(client):
    composer, declaration = client
    before = declaration.read_text(encoding="utf-8")
    revision = composer.read_current().payload["revision"]

    response = composer.change(operation="disable", resource_type="team",
                               instance_id="feedback_analytics", base_revision=revision,
                               reason="검증만", dry_run=True)

    assert response.ok, response.error
    assert response.payload["dry_run"] is True
    assert declaration.read_text(encoding="utf-8") == before


def test_stale_revision_surfaces_as_a_conflict_not_a_generic_failure(client):
    """★UI 가 "다시 읽고 재시도" 를 안내할 수 있어야 한다."""
    composer, _ = client
    response = composer.change(operation="disable", resource_type="team",
                               instance_id="feedback_analytics",
                               base_revision="stale", reason="충돌 확인")

    assert not response.ok
    assert response.revision_conflict
    assert response.status == 409


def test_grant_ceiling_is_enforced_by_the_server_not_the_client(client):
    """클라이언트는 판정하지 않는다 — 그대로 보내고 서버가 거부한다."""
    composer, _ = client
    revision = composer.read_current().payload["revision"]

    response = composer.change(
        operation="create", resource_type="team", instance_id="escalation",
        implementation_id="team.declarative.v1",
        parameters={"display_name": "권한 상승 시도", "capabilities": ["demo.escalate"],
                    "accepted_case_types": ["demo"], "required_context": ["case_state"],
                    "allowed_tools": ["read.policy", "payments.refund"],
                    "knowledge_scope": ["demo"], "max_steps": 3,
                    "prompt_key": "declarative.escalation"},
        base_revision=revision, reason="권한 상승 시도")

    assert not response.ok
    assert response.status == 422
    assert "읽기 전용" in json.dumps(response.payload, ensure_ascii=False)


def test_missing_issuer_secret_fails_loudly(config_dir):
    """비밀키가 없으면 조용히 빈 결과를 주지 않고 이유를 말한다."""
    composer = ComposerClient("http://target.invalid", issuer_secret=None)
    response = composer.catalog()
    assert not response.ok
    assert "비밀키" in (response.error or "")


# ── 두 운영 방식 (2026-08-30) ────────────────────────────────────────
def test_direct_mode_sends_no_deployment_header(client):
    """대상에 Composer 가 함께 설치된 방식 — 대상이 자기 하나만 관리한다."""
    composer, _declaration = client
    assert composer.mode == "direct"
    assert composer.catalog().ok


def test_central_mode_targets_a_deployment_through_the_config_service(config_dir):
    """★설정 서비스 한 곳이 여러 대상을 다룬다 — 헤더로 대상을 지정한다."""
    from uuid import uuid4 as _uuid4

    from acop_basement.core.config_store import PostgresConfigStore
    from acop_basement.infrastructure.db.session import get_connection
    from acop_composer.service_app import create_config_service_app

    deployment_id = "test-uiclient-" + _uuid4().hex
    declaration = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    PostgresConfigStore(get_connection, deployment_id).create(declaration)

    service = TestClient(create_config_service_app())

    def transport(method, url, headers, body):
        response = service.request(method, url, headers=headers, content=body)
        return response.status_code, response.content

    composer = ComposerClient("http://config-service.invalid",
                              issuer_secret=get_settings().composer_issuer_secret,
                              deployment_id=deployment_id, transport=transport)
    try:
        assert composer.mode == "central"
        catalog = composer.catalog()
        assert catalog.ok, catalog.error

        current = composer.read_current()
        assert current.ok and current.payload["config"]["teams"]

        changed = composer.change(
            operation="disable", resource_type="team", instance_id="feedback_analytics",
            base_revision=current.payload["revision"], reason="중앙 방식 확인")
        assert changed.ok, changed.error
        assert changed.payload["activation_state"] == "pending_restart"
    finally:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM project_configs WHERE deployment_id = %s",
                            (deployment_id,))
                cur.execute("DELETE FROM composer_audit_events WHERE deployment_id = %s",
                            (deployment_id,))


def test_central_mode_without_a_deployment_id_is_refused_by_the_service(config_dir):
    """★대상을 안 밝히면 설정 서비스가 거부한다 — 남의 설정을 건드리지 않는다."""
    from acop_composer.service_app import create_config_service_app

    service = TestClient(create_config_service_app())

    def transport(method, url, headers, body):
        response = service.request(method, url, headers=headers, content=body)
        return response.status_code, response.content

    # deployment_id 없이 설정 서비스를 부른다 = direct 모드로 중앙에 붙는 실수
    composer = ComposerClient("http://config-service.invalid",
                              issuer_secret=get_settings().composer_issuer_secret,
                              transport=transport)
    response = composer.catalog()

    assert not response.ok
    assert response.status == 400
    assert response.payload["error"]["code"] == "deployment_required"
