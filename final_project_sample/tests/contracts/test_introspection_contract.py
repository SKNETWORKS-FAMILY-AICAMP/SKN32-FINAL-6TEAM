from __future__ import annotations

from acop_basement.introspection import introspect


def test_introspection_contract_has_versioned_redacted_shape(monkeypatch):
    class Settings:
        llm_provider = "openai"
        llm_model = "test-model"
        openai_api_key = "sk-real-secret"

    class Guardrails:
        def as_dict(self):
            return {"reliability": {"team_timeout_seconds": 30}}

    class Config:
        revision = "cfg-rev"
        modules = {"ops_ui": type("M", (), {"enabled": True})()}
        ports = type("P", (), {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"})()

    manifest = type("Manifest", (), {"team_id": "team-a", "display_name": "A", "capabilities": ["read"], "allowed_tools": ["read.case"], "active": True, "implementation_revision": "team-rev"})()
    registry = type("Registry", (), {"manifests": lambda self: (manifest,)})()
    executor = type("LocalTeamExecutor", (), {})()
    monkeypatch.setattr("app.composition.build_registry", lambda **kwargs: registry)
    monkeypatch.setattr("app.composition.build_team_executor", lambda **kwargs: executor)
    monkeypatch.setattr("acop_basement.core.settings.get_settings", lambda: Settings())
    monkeypatch.setattr("acop_basement.core.settings.get_guardrails", lambda: Guardrails())

    data = introspect(config=Config())
    # ★1.1 (2026-08-31) — 실행 중인 조립과 저장소의 선언을 구분하는 필드가 늘었다.
    #   그 전에는 `config_revision` 하나뿐이었고, 그 값은 저장소를 다시 읽어
    #   계산한 것이라 **실행 중인** revision 이 아니었다.
    assert data["contract_version"] == "1.1"
    assert data["team_manifests"][0]["revision"] == "team-rev"
    assert data["llm"]["api_key"] == "sk-****"
    assert "sk-real-secret" not in str(data)

    # runtime 을 안 줬으므로 실행 중인 revision 은 **모른다**. 저장소에서 읽은
    # 값을 실행 중인 것처럼 적지 않는다.
    assert data["desired_revision"] == "cfg-rev"
    assert data["active_revision"] is None
    assert data["reload_state"] == "unknown"
