from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient

import app.presentation.composer_auth as composer_auth
from app.presentation.api.app import create_app


@pytest.fixture()
def configured(monkeypatch):
    settings = SimpleNamespace(composer_jwt_secret="test-jwt-secret", composer_issuer_secret="test-issuer-secret")
    monkeypatch.setattr(composer_auth, "get_settings", lambda: settings)


def _token(scope: str | list[str], *, expired: bool = False, secret: str = "test-jwt-secret") -> str:
    scopes = [scope] if isinstance(scope, str) else scope
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": "test-actor", "aud": "final_project_cs", "scope": scopes,
                       "iat": now - timedelta(hours=2) if expired else now,
                       "exp": now - timedelta(minutes=1) if expired else now + timedelta(minutes=30),
                       "jti": str(uuid4())}, secret, algorithm="HS256")


def _client(tmp_path: Path, monkeypatch) -> tuple[TestClient, Path]:
    source = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    app = create_app(classifier=lambda _: {"intent": "billing", "issue_code": "x", "sentiment": "neutral"})
    app.state.project_config_path = path
    app.state.composer_audit_path = tmp_path / "composer_events.jsonl"
    return TestClient(app), path


def _auth(scope: str | list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(scope)}"}


def test_requires_authentication(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/composer/current")
    assert response.status_code == 401


def test_wrong_scope_is_rejected(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/composer/current", headers=_auth("ops:introspect"))
    assert response.status_code == 403


def test_write_channel_survives_ops_ui_being_disabled(tmp_path, monkeypatch, configured):
    source = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    source["modules"]["ops_ui"]["enabled"] = False
    client, path = _client(tmp_path, monkeypatch)
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    # This repository has no composer_ui module; disabling ops_ui must not disable the API.
    response = client.get("/composer/current", headers=_auth("composer:read"))
    assert response.status_code == 200
    assert response.json()["config"]["modules"]["ops_ui"]["enabled"] is False


def test_validate_does_not_write_the_file(tmp_path, monkeypatch, configured):
    client, path = _client(tmp_path, monkeypatch)
    before = path.read_bytes()
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["implementation_ref"] = "app.nonexistent:Missing"

    response = client.post("/composer/validate", headers=_auth("composer:validate"),
                           json={"config": current["config"]})

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert path.read_bytes() == before
    assert not path.with_suffix(".yaml.bak").exists()


def test_apply_rejects_unimplementable_reference(tmp_path, monkeypatch, configured):
    client, path = _client(tmp_path, monkeypatch)
    before = path.read_bytes()
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["implementation_ref"] = "app.nonexistent:Missing"

    response = client.post("/composer/apply", headers=_auth("composer:write"), json={
        "config": current["config"], "base_revision": current["revision"],
        "reason": "test registry rejection"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_declaration"
    assert path.read_bytes() == before


def test_http_validate_rejects_unknown_active_implementation_reference(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["implementation_ref"] = "os:system"

    response = client.post("/composer/validate", headers=_auth("composer:validate"),
                           json={"config": current["config"]})

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert "not allowed" in response.json()["errors"][0]


def test_http_apply_rejects_unknown_active_implementation_reference_before_revision_check(
    tmp_path, monkeypatch, configured
):
    client, path = _client(tmp_path, monkeypatch)
    before = path.read_bytes()
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["implementation_ref"] = "not.a.real.module:NotAClass"

    response = client.post("/composer/apply", headers=_auth("composer:write"), json={
        "config": current["config"], "base_revision": "stale-revision",
        "reason": "test HTTP registry rejection"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_declaration"
    assert path.read_bytes() == before


def test_http_registry_ignores_unknown_inactive_implementation_reference(
    tmp_path, monkeypatch, configured
):
    client, _ = _client(tmp_path, monkeypatch)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    current["config"]["teams"][0]["active"] = False
    current["config"]["teams"][0]["implementation_ref"] = "not.a.real.module:NotAClass"

    response = client.post("/composer/validate", headers=_auth("composer:validate"),
                           json={"config": current["config"]})

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_apply_writes_an_audit_event_with_actor_and_revision(tmp_path, monkeypatch, configured):
    client, path = _client(tmp_path, monkeypatch)
    audit_path = tmp_path / "composer_events.jsonl"
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    candidate = current["config"]
    candidate["teams"][0]["active"] = not candidate["teams"][0]["active"]

    response = client.post("/composer/apply", headers=_auth("composer:write"), json={
        "config": candidate, "base_revision": current["revision"], "reason": "audit test"})

    assert response.status_code == 200
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["actor"] == "test-actor"
    assert event["previous_revision"] == current["revision"]
    assert event["revision"] == response.json()["revision"]
    assert event["changed_fields"]


def test_expired_token_is_rejected(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/composer/current", headers={"Authorization": f"Bearer {_token('composer:read', expired=True)}"})
    assert response.status_code == 401


def test_forged_signature_is_rejected(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.get("/composer/current", headers={"Authorization": f"Bearer {_token('composer:read', secret='wrong')}"})
    assert response.status_code == 401


def test_token_issue_and_current_endpoint(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    issued = client.post("/auth/token", headers={"Authorization": "Bearer test-issuer-secret"},
                         json={"sub": "final_project_ui", "scope": ["composer:read"]})
    assert issued.status_code == 200
    current = client.get("/composer/current", headers={"Authorization": f"Bearer {issued.json()['access_token']}"})
    assert current.status_code == 200
    assert "revision" in current.json()


def test_concurrent_apply_one_wins_one_gets_409(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    # ★두 팀이 있던 시절엔 팀마다 하나씩 토글해 서로 다른 두 변형을 만들었다.
    #   지금은 팀이 1개라 그 방식으로는 변형을 2개 못 만든다 — 이 테스트가 실제로
    #   재는 건 "같은 base_revision 으로 동시에 apply 하면 하나만 이긴다"는
    #   낙관적 동시성이지 팀 개수가 아니므로, 서로 다른 필드를 하나씩 토글해
    #   변형 2개를 만든다.
    first_team = dict(current["config"]["teams"][0])
    first_team["active"] = not first_team["active"]
    variant_a = dict(current["config"])
    variant_a["teams"] = [first_team] + [dict(item) for item in current["config"]["teams"][1:]]

    variant_b = dict(current["config"])
    variant_b["modules"] = dict(current["config"]["modules"])
    variant_b["modules"]["ops_ui"] = dict(variant_b["modules"]["ops_ui"])
    variant_b["modules"]["ops_ui"]["enabled"] = not variant_b["modules"]["ops_ui"]["enabled"]

    payloads = [variant_a, variant_b]
    results = [None, None]

    def apply(index: int):
        results[index] = client.post("/composer/apply", headers=_auth("composer:write"), json={
            "config": payloads[index], "base_revision": current["revision"], "reason": "concurrent test"})

    threads = [threading.Thread(target=apply, args=(index,)) for index in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert sorted(response.status_code for response in results) == [200, 409]


@pytest.mark.parametrize("target_type,target_id,field", [
    ("module", "vector_rag", "enabled"),
    ("team", "voc_store_manager", "active"),
])
def test_toggle_changes_only_one_registered_flag_and_audits(
    tmp_path, monkeypatch, configured, target_type, target_id, field
):
    client, path = _client(tmp_path, monkeypatch)
    before = yaml.safe_load(path.read_text(encoding="utf-8"))
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    old_value = before["modules"][target_id][field] if target_type == "module" else next(
        team[field] for team in before["teams"] if team["team_id"] == target_id
    )

    response = client.post("/composer/toggle", headers=_auth("composer:write"), json={
        "target_type": target_type, "target_id": target_id, "active": not old_value,
        "base_revision": current["revision"], "reason": "toggle test"})

    assert response.status_code == 200
    body = response.json()
    assert body["active"] is (not old_value)
    assert body["config_revision"] != current["revision"]
    after = yaml.safe_load(path.read_text(encoding="utf-8"))
    if target_type == "module":
        after["modules"][target_id][field] = before["modules"][target_id][field]
    else:
        for team in after["teams"]:
            if team["team_id"] == target_id:
                team[field] = before["teams"][[item["team_id"] for item in before["teams"]].index(target_id)][field]
    assert after == before
    lines = (tmp_path / "composer_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "composer.toggle"
    assert event["target_type"] == target_type
    assert event["target_id"] == target_id
    assert event["previous_active"] is old_value
    assert event["active"] is (not old_value)
    assert event["config_revision"] == body["config_revision"]
    assert event["correlation_id"] == body["audit_id"]


@pytest.mark.parametrize("payload,expected_status", [
    ({"target_type": "module", "target_id": "missing", "active": False}, 422),
    ({"target_type": "port", "target_id": "team_executor", "active": False}, 422),
])
def test_toggle_rejects_unregistered_targets_without_writing(
    tmp_path, monkeypatch, configured, payload, expected_status
):
    client, path = _client(tmp_path, monkeypatch)
    before = path.read_bytes()
    current = client.get("/composer/current", headers=_auth("composer:read")).json()
    payload.update(base_revision=current["revision"], reason="invalid target")
    response = client.post("/composer/toggle", headers=_auth("composer:write"), json=payload)
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == "invalid_declaration"
    assert path.read_bytes() == before


def test_toggle_rejects_stale_revision_without_writing(tmp_path, monkeypatch, configured):
    client, path = _client(tmp_path, monkeypatch)
    before = path.read_bytes()
    response = client.post("/composer/toggle", headers=_auth("composer:write"), json={
        "target_type": "module", "target_id": "vector_rag", "active": False,
        "base_revision": "stale", "reason": "stale test"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "revision_conflict"
    assert path.read_bytes() == before


def test_toggle_requires_composer_write_scope(tmp_path, monkeypatch, configured):
    client, _ = _client(tmp_path, monkeypatch)
    response = client.post("/composer/toggle", headers=_auth("composer:read"), json={
        "target_type": "module", "target_id": "vector_rag", "active": False,
        "base_revision": "irrelevant", "reason": "scope test"})
    assert response.status_code == 403
