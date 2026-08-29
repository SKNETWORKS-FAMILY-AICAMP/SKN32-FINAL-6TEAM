from __future__ import annotations

from app.introspection.contract import snapshot
from app import composition
from app.core.project_config import load_project_config
from app.application.composer_service import revision


def test_snapshot_has_composition_only_shape_and_redacts_key(monkeypatch):
    class Settings:
        llm_provider = "openai"
        llm_model = "test-model"
        openai_api_key = "sk-real-secret"

    class Guardrails:
        def as_dict(self):
            return {"reliability": {"team_timeout_seconds": 90}}

    class Module:
        def __init__(self, enabled):
            self.enabled = enabled

    class Config:
        modules = {"vector_rag": Module(True), "graph_store": Module(True)}
        ports = type("Ports", (), {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"})()
        teams = [type("Team", (), {"team_id": "team-a", "active": True, "implementation_ref": "pkg:Team"})()]

        def module_enabled(self, name):
            return self.modules[name].enabled

        def model_dump(self, mode="json"):
            return {
                "modules": {key: {"enabled": value.enabled} for key, value in self.modules.items()},
                "ports": {"team_executor": self.ports.team_executor,
                           "message_broker": self.ports.message_broker,
                           "graph_store": self.ports.graph_store},
                "teams": [{"team_id": team.team_id, "active": team.active,
                           "implementation_ref": team.implementation_ref} for team in self.teams],
                "response_review": {"enabled": False, "owner_team_id": "team-a"},
            }

    manifest = type("Manifest", (), {
        "team_id": "team-a", "display_name": "A", "capabilities": ["read"],
        "allowed_tools": ["read.case"], "knowledge_scope": ["case"], "max_steps": 6,
        "active": True, "implementation_revision": "team-rev",
    })()
    registry = type("Registry", (), {"manifests": lambda self: (manifest,)})()
    executor = type("LocalTeamExecutor", (), {})()

    monkeypatch.setattr("app.core.settings.get_settings", lambda: Settings())
    monkeypatch.setattr("app.core.settings.get_guardrails", lambda: Guardrails())
    monkeypatch.setattr("app.composition.build_broker", lambda **kwargs: object())
    monkeypatch.setattr("app.composition.build_graph_store", lambda **kwargs: object())

    data = snapshot(config=Config(), registry=registry, executor=executor)
    assert set(data) == {
        "contract_version", "config_revision", "modules", "ports", "team_manifests",
        "teams", "registered_ids", "port_implementations", "guardrails", "llm",
    }
    assert data["contract_version"] == "1.0"
    assert data["config_revision"] == revision(Config())
    assert data["registered_ids"] == {
        "modules": ["vector_rag", "graph_store"], "teams": ["team-a"], "ports": []
    }
    assert data["team_manifests"][0]["team_id"] == "team-a"
    assert data["llm"]["api_key"] == "sk-****"
    assert "sk-real-secret" not in str(data)
    assert not any(key in data for key in ("document_count", "chunk_count", "case_statuses", "outbox_statuses"))


def test_snapshot_contains_all_five_active_project_teams(monkeypatch):
    monkeypatch.setattr("app.composition.build_broker", lambda **kwargs: object())
    monkeypatch.setattr("app.composition.build_graph_store", lambda **kwargs: object())
    config = load_project_config()
    registry = composition.build_registry(config=config)
    data = snapshot(
        config=config,
        registry=registry,
        executor=composition.build_team_executor(registry=registry, config=config),
    )
    assert {item["team_id"] for item in data["team_manifests"]} == {
        "voc_store_manager", "response_generation_review", "return_refund",
        "procurement_order_payment", "fulfillment_logistics", "catalog_verification",
    }
    assert all(item["active"] for item in data["team_manifests"])


def test_snapshot_registered_ids_and_revision_match_project_config(monkeypatch):
    monkeypatch.setattr("app.composition.build_broker", lambda **kwargs: object())
    monkeypatch.setattr("app.composition.build_graph_store", lambda **kwargs: object())
    config = load_project_config()
    registry = composition.build_registry(config=config)
    data = snapshot(config=config, registry=registry,
                    executor=composition.build_team_executor(registry=registry, config=config))
    assert data["registered_ids"] == {
        "modules": list(config.modules),
        "teams": [team.team_id for team in config.teams],
        "ports": [],
    }
    assert isinstance(data["config_revision"], str)
    assert data["config_revision"] == revision(config)
