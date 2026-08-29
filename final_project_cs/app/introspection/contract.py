"""Versioned, read-only description of the assembled application.

This contract deliberately contains composition metadata only.  It must not
include tenant-scoped operational data such as document, case, or outbox
counts; those remain part of the local operations UI.
"""
from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "1.0"


def _manifest(manifest: Any) -> dict[str, Any]:
    return {
        "team_id": manifest.team_id,
        "display_name": manifest.display_name,
        "capabilities": list(manifest.capabilities),
        "allowed_tools": list(manifest.allowed_tools),
        "knowledge_scope": list(getattr(manifest, "knowledge_scope", [])),
        "max_steps": getattr(manifest, "max_steps", None),
        "active": bool(manifest.active),
        "revision": manifest.implementation_revision,
    }


def snapshot(*, config: Any | None = None, registry: Any | None = None,
             executor: Any | None = None) -> dict[str, Any]:
    """Return JSON-safe composition metadata without customer data or secrets."""
    from app import composition
    from app.application.composer_service import revision
    from app.core import settings as settings_module
    from app.infrastructure.db.session import get_connection

    requested_config = config
    config = config or composition.load_project_config()
    if registry is None:
        registry = (composition.build_registry()
                    if requested_config is None
                    else composition.build_registry(config=config))
    executor = executor or composition.build_team_executor(registry=registry, config=config)

    settings = settings_module.get_settings()
    manifests = [_manifest(item) for item in registry.manifests()]
    return {
        "contract_version": CONTRACT_VERSION,
        "config_revision": revision(config),
        "modules": {name: bool(value.enabled) for name, value in config.modules.items()},
        "ports": {
            "team_executor": config.ports.team_executor,
            "message_broker": config.ports.message_broker,
            "graph_store": config.ports.graph_store,
        },
        "team_manifests": manifests,
        "teams": _declared_teams(config, manifests),
        "registered_ids": {
            "modules": list(config.modules),
            "teams": [team.team_id for team in config.teams],
            "ports": [],
        },
        "port_implementations": _port_implementations(config, executor, get_connection),
        "guardrails": settings_module.get_guardrails().as_dict(),
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key": "sk-****" if settings.openai_api_key else "missing",
        },
    }


def _declared_teams(config: Any, manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["team_id"]: item for item in manifests}
    declared = [
        {
            "team_id": team.team_id,
            "active": team.active,
            "implementation_ref": team.implementation_ref,
            "manifest": by_id.get(team.team_id),
        }
        for team in getattr(config, "teams", [])
    ]
    known = {team["team_id"] for team in declared}
    for team_id, manifest in by_id.items():
        if team_id not in known:
            declared.append({
                "team_id": team_id,
                "active": manifest["active"],
                "implementation_ref": None,
                "manifest": manifest,
            })
    return declared


def _port_implementations(config: Any, executor: Any, connection_factory: Any) -> dict[str, str | None]:
    from app import composition

    result: dict[str, str | None] = {
        "team_executor": type(executor).__name__,
        "message_broker": None,
        "graph_store": None,
    }
    try:
        result["message_broker"] = type(composition.build_broker(
            connection_factory=connection_factory, config=config
        )).__name__
    except Exception:
        pass
    try:
        if config.module_enabled("graph_store"):
            result["graph_store"] = type(composition.build_graph_store(
                connection=None, tenant_id="introspection", config=config
            )).__name__
    except Exception:
        pass
    return result


# Compatibility aliases for callers that used the sample contract names.
introspect = snapshot
build_snapshot = snapshot
describe = snapshot
