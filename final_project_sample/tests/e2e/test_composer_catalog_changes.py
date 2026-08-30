"""`GET /composer/catalog`, `POST /composer/changes` — 카탈로그 기반 인스턴스 CRUD.

계획서: `docs/plans/2026-08-28_선언형Team_카탈로그CRUD_계획.md` §3 스트림 B.

★v2(`/current`·`/validate`·`/apply`)는 그대로 둔다. 이건 그 위에 얹는 좁은
  명령 경로다 — UI 가 전체 선언 구조를 몰라도 인스턴스 하나를 만들고 지울 수
  있게 하는 것이 목적이다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient

from acop_basement.core.settings import get_settings
from acop_basement.presentation.api.app import create_app
from acop_composer.api import router as composer_write_router
from acop_composer.auth import router as composer_auth_router


def _auth(scope: str = "composer:write") -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "test-actor", "aud": "final_project_sample", "scope": [scope],
         "iat": now, "exp": now + timedelta(minutes=30), "jti": str(uuid4())},
        get_settings().composer_jwt_secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def config_dir():
    path = Path(".composer-changes-e2e-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def _declaration(tmp: Path) -> Path:
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    path = tmp / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def _client(path: Path) -> TestClient:
    app = create_app(composer_write_router=composer_write_router,
                     composer_auth_router=composer_auth_router)
    app.state.project_config_path = path
    app.state.composer_audit_path = path.with_name("composer_events.jsonl")
    return TestClient(app)


def _revision(client: TestClient) -> str:
    return client.get("/composer/current", headers=_auth("composer:read")).json()["revision"]


def _change(**kwargs):
    body = {"reason": "테스트", "base_revision": kwargs.pop("base_revision", "")}
    body.update(kwargs)
    return body


# ── catalog ──────────────────────────────────────────────────────────
def test_catalog_lists_implementations_without_exposing_python_paths(config_dir):
    client = _client(_declaration(config_dir))
    response = client.get("/composer/catalog", headers=_auth("composer:read"))
    assert response.status_code == 200
    body = response.json()

    ids = {e["implementation_id"] for e in body["implementations"]}
    assert "team.declarative.v1" in ids
    assert "module.vector_rag" in ids

    serialized = json.dumps(body, ensure_ascii=False)
    assert ":" not in serialized or "app.modules" not in serialized, \
        "Python 경로가 UI 응답에 새면 안 된다"

    declarative = next(e for e in body["implementations"]
                       if e["implementation_id"] == "team.declarative.v1")
    assert declarative["parameters_schema"] is not None
    assert declarative["requires_restart"] is True


def test_catalog_requires_read_scope(config_dir):
    client = _client(_declaration(config_dir))
    assert client.get("/composer/catalog").status_code == 401


# ── changes ──────────────────────────────────────────────────────────
def test_dry_run_validates_without_touching_the_file(config_dir):
    path = _declaration(config_dir)
    client = _client(path)
    before_text, before_mtime = path.read_text(encoding="utf-8"), path.stat().st_mtime_ns

    response = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="disable", resource_type="team", instance_id="feedback_analytics",
        base_revision=_revision(client), dry_run=True))

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert path.read_text(encoding="utf-8") == before_text
    assert path.stat().st_mtime_ns == before_mtime


def test_disable_then_enable_round_trips_and_reports_pending_restart(config_dir):
    path = _declaration(config_dir)
    client = _client(path)

    disabled = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="disable", resource_type="team", instance_id="feedback_analytics",
        base_revision=_revision(client)))
    assert disabled.status_code == 200
    # ★저장됐다고 "적용 완료" 라고 하지 않는다 — 조립은 기동 때 한 번뿐이다.
    assert disabled.json()["activation_state"] == "pending_restart"

    declaration = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert declaration["teams"][0]["active"] is False

    enabled = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="enable", resource_type="team", instance_id="feedback_analytics",
        base_revision=_revision(client)))
    assert enabled.status_code == 200
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["teams"][0]["active"] is True


def test_module_toggle_changes_only_that_module(config_dir):
    path = _declaration(config_dir)
    client = _client(path)
    before = yaml.safe_load(path.read_text(encoding="utf-8"))["modules"]

    response = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="disable", resource_type="module", instance_id="graph_store",
        base_revision=_revision(client)))
    assert response.status_code == 200

    after = yaml.safe_load(path.read_text(encoding="utf-8"))["modules"]
    assert after["graph_store"]["enabled"] is False
    others = {k: v for k, v in after.items() if k != "graph_store"}
    assert others == {k: v for k, v in before.items() if k != "graph_store"}


def test_unknown_implementation_id_is_rejected(config_dir):
    client = _client(_declaration(config_dir))
    response = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="create", resource_type="team", instance_id="x",
        implementation_id="team.does_not_exist", base_revision=_revision(client)))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_implementation"


def test_stale_base_revision_conflicts(config_dir):
    client = _client(_declaration(config_dir))
    response = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="disable", resource_type="team", instance_id="feedback_analytics",
        base_revision="stale-revision"))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "revision_conflict"


def test_same_idempotency_key_applies_once(config_dir):
    path = _declaration(config_dir)
    client = _client(path)
    key = str(uuid4())
    body = _change(operation="disable", resource_type="team",
                   instance_id="feedback_analytics", base_revision=_revision(client),
                   idempotency_key=key)

    first = client.post("/composer/changes", headers=_auth(), json=body)
    assert first.status_code == 200
    after_first = path.read_text(encoding="utf-8")

    # 같은 키로 재시도 — base_revision 은 이미 낡았지만 409 가 아니라
    # 첫 결과를 그대로 돌려줘야 한다(그래야 재시도가 안전하다).
    second = client.post("/composer/changes", headers=_auth(), json=body)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert path.read_text(encoding="utf-8") == after_first, "두 번 쓰면 안 된다"


def test_change_is_recorded_in_the_audit_log(config_dir):
    path = _declaration(config_dir)
    client = _client(path)
    client.post("/composer/changes", headers=_auth(), json=_change(
        operation="disable", resource_type="team", instance_id="feedback_analytics",
        base_revision=_revision(client), reason="감사 확인"))

    events = [json.loads(line) for line in
              path.with_name("composer_events.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    event = events[-1]
    assert event["event"] == "composer.change"
    assert event["operation"] == "disable"
    assert event["instance_id"] == "feedback_analytics"
    assert event["actor"] == "test-actor"
    assert event["previous_revision"] != event["revision"]


def test_changes_requires_write_scope(config_dir):
    client = _client(_declaration(config_dir))
    response = client.post("/composer/changes", headers=_auth("composer:read"), json=_change(
        operation="disable", resource_type="team", instance_id="feedback_analytics",
        base_revision="whatever"))
    assert response.status_code == 403


# ── v3 토글 계약 ─────────────────────────────────────────────────────
def test_toggle_matches_the_v3_contract_shape(config_dir):
    """v3 §2.2 가 정한 요청·응답 필드를 그대로 쓴다."""
    path = _declaration(config_dir)
    client = _client(path)

    response = client.post("/composer/toggle", headers=_auth(), json={
        "target_type": "team", "target_id": "feedback_analytics", "active": False,
        "base_revision": _revision(client), "reason": "점검 중 임시 비활성화"})

    assert response.status_code == 200
    body = response.json()
    assert body["target_type"] == "team"
    assert body["target_id"] == "feedback_analytics"
    assert body["active"] is False
    assert body["config_revision"] and body["audit_id"]
    # ★저장됐다고 런타임이 그 설정으로 도는 것이 아니다 — 감추지 않는다.
    assert body["activation_state"] == "pending_restart"
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["teams"][0]["active"] is False


def test_toggle_shares_the_revision_guard_with_changes(config_dir):
    client = _client(_declaration(config_dir))
    response = client.post("/composer/toggle", headers=_auth(), json={
        "target_type": "team", "target_id": "feedback_analytics", "active": False,
        "base_revision": "stale-revision", "reason": "충돌 확인"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "revision_conflict"


def test_toggle_rejects_targets_that_are_not_declared(config_dir):
    client = _client(_declaration(config_dir))
    response = client.post("/composer/toggle", headers=_auth(), json={
        "target_type": "module", "target_id": "does_not_exist", "active": True,
        "base_revision": _revision(client), "reason": "미등록 대상"})
    assert response.status_code == 422


def test_toggle_is_recorded_as_its_own_audit_event(config_dir):
    """`/changes` 와 저장 경로는 같아도 감사에서는 구분돼야 한다."""
    path = _declaration(config_dir)
    client = _client(path)
    client.post("/composer/toggle", headers=_auth(), json={
        "target_type": "team", "target_id": "feedback_analytics", "active": False,
        "base_revision": _revision(client), "reason": "감사 확인"})

    events = [json.loads(line) for line in
              path.with_name("composer_events.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    assert events[-1]["event"] == "composer.toggle"
    assert events[-1]["instance_id"] == "feedback_analytics"


# ── 스트림 A+B 통합 ──────────────────────────────────────────────────
def test_declarative_team_created_through_the_api_loads_and_assembles(config_dir):
    """★두 스트림을 잇는 증명 — UI 가 보낸 명령만으로 새 Team 이 생긴다.

    코드 배포 없이, 카탈로그에서 고른 선언형 실행기 + 입력값만으로 Team 이
    만들어지고, 그 결과가 실제 로더와 조립을 통과해야 한다.
    """
    from acop_basement.core.project_config import load_project_config
    from acop_basement.tools.read_tools import ReadToolbox
    from app.composition import build_registry

    path = _declaration(config_dir)
    client = _client(path)

    response = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="create", resource_type="team", instance_id="vip_review",
        implementation_id="team.declarative.v1",
        parameters={
            "display_name": "VIP 검토", "capabilities": ["demo.vip_review"],
            "accepted_case_types": ["demo"], "required_context": ["case_state", "policy"],
            "allowed_tools": ["read.policy"], "knowledge_scope": ["demo"],
            "max_steps": 3, "prompt_key": "declarative.vip_review",
        },
        base_revision=_revision(client)))
    assert response.status_code == 200, response.text
    assert response.json()["activation_state"] == "pending_restart"

    # 저장된 선언이 실제 로더를 통과하고, 조립까지 된다.
    config = load_project_config(path)
    registry = build_registry(
        tools=ReadToolbox(tool_functions={"read.policy": lambda _c, **_k: "정책"}),
        config=config)
    manifest = next(m for m in registry.manifests() if m.team_id == "vip_review")
    assert manifest.capabilities == ["demo.vip_review"]
    assert manifest.implementation_revision == "declarative.v1"


def test_declarative_team_with_write_tool_is_rejected_by_the_api(config_dir):
    """★grant ceiling 이 HTTP 경로에서도 걸린다 — 권한 상승을 API 로 우회할 수 없다."""
    client = _client(_declaration(config_dir))
    response = client.post("/composer/changes", headers=_auth(), json=_change(
        operation="create", resource_type="team", instance_id="escalation_attempt",
        implementation_id="team.declarative.v1",
        parameters={
            "display_name": "권한 상승 시도", "capabilities": ["demo.escalate"],
            "accepted_case_types": ["demo"], "required_context": ["case_state"],
            "allowed_tools": ["read.policy", "payments.refund"], "knowledge_scope": ["demo"],
            "max_steps": 3, "prompt_key": "declarative.escalation",
        },
        base_revision=_revision(client)))
    assert response.status_code == 422
    assert "읽기 전용" in response.text


# ── 감사 저장소 배선 (중앙 모드) ─────────────────────────────────────
def test_audit_goes_to_the_injected_store_not_a_file(config_dir):
    """★설정이 중앙을 가리키면 감사도 중앙에 남는다.

    선언만 중앙으로 옮기고 감사를 대상마다의 파일에 두면, 누가 무엇을 바꿨는지가
    수천 군데로 흩어져 감사로서 쓸모가 없다.
    """
    from uuid import uuid4 as _uuid4

    from acop_basement.core.audit_store import PostgresAuditStore
    from acop_basement.infrastructure.db.session import get_connection

    deployment_id = "test-audit-" + _uuid4().hex
    store = PostgresAuditStore(get_connection, deployment_id)

    path = _declaration(config_dir)
    app = create_app(composer_write_router=composer_write_router,
                     composer_auth_router=composer_auth_router)
    app.state.project_config_path = path
    app.state.composer_audit_store = store          # ★파일이 아니라 저장소를 주입
    app.state.composer_audit_path = path.with_name("should_not_be_used.jsonl")
    http = TestClient(app)

    revision = http.get("/composer/current", headers=_auth("composer:read")).json()["revision"]
    try:
        response = http.post("/composer/changes", headers=_auth(), json=_change(
            operation="disable", resource_type="team", instance_id="feedback_analytics",
            base_revision=revision, reason="중앙 감사 확인"))
        assert response.status_code == 200, response.text

        events = store.recent(10)
        assert events and events[0]["event"] == "composer.change"
        assert events[0]["instance_id"] == "feedback_analytics"
        # 파일로는 안 갔다
        assert not path.with_name("should_not_be_used.jsonl").exists()
    finally:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM composer_audit_events WHERE deployment_id = %s",
                            (deployment_id,))


def test_idempotency_is_resolved_through_the_store(config_dir):
    """★재시도 판정도 저장소가 한다 — 파일 전체 스캔이 아니라 인덱스 조회."""
    from uuid import uuid4 as _uuid4

    from acop_basement.core.audit_store import PostgresAuditStore
    from acop_basement.infrastructure.db.session import get_connection

    deployment_id = "test-audit-" + _uuid4().hex
    store = PostgresAuditStore(get_connection, deployment_id)

    path = _declaration(config_dir)
    app = create_app(composer_write_router=composer_write_router,
                     composer_auth_router=composer_auth_router)
    app.state.project_config_path = path
    app.state.composer_audit_store = store
    http = TestClient(app)

    revision = http.get("/composer/current", headers=_auth("composer:read")).json()["revision"]
    key = str(uuid4())
    body = _change(operation="disable", resource_type="team",
                   instance_id="feedback_analytics", base_revision=revision,
                   idempotency_key=key)
    try:
        first = http.post("/composer/changes", headers=_auth(), json=body)
        after_first = path.read_text(encoding="utf-8")
        second = http.post("/composer/changes", headers=_auth(), json=body)

        assert first.status_code == 200 and second.status_code == 200
        assert second.json() == first.json()
        assert path.read_text(encoding="utf-8") == after_first, "두 번 쓰면 안 된다"
    finally:
        with get_connection() as conn:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("DELETE FROM composer_audit_events WHERE deployment_id = %s",
                            (deployment_id,))
