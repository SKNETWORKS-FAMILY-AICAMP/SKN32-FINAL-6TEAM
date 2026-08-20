from __future__ import annotations

import pytest
from pydantic import ValidationError
from pathlib import Path
import tempfile

from app.composition import CompositionError, build_graph_store, build_registry
from app.core.project_config import ProjectConfig, ProjectConfigError, load_project_config
from app.core.registry import RegistryError
from app.tools.read_tools import ReadToolbox


class IncompleteTeam:
    manifest = object()


def _config(*, teams=None, graph_enabled=True, graph_port="sql", broker="outbox", module_overrides=None):
    modules = {
        "vector_rag": {"enabled": True}, "graph_store": {"enabled": graph_enabled},
        "a2a_executor": {"enabled": False}, "mcp": {"enabled": True},
        "voc": {"enabled": True}, "ops_ui": {"enabled": True},
    }
    modules.update(module_overrides or {})
    return ProjectConfig.model_validate({
        "modules": modules,
        "ports": {"team_executor": "local", "message_broker": broker, "graph_store": graph_port},
        "teams": teams or [{"team_id": "voc_store_manager", "active": True,
                             "implementation_ref": "app.modules.customer_ops:VocStoreManagerTeam"}],
    })


def _tools():
    return ReadToolbox(lambda: None)


def test_declaration_controls_active_routing_and_keeps_inactive_manifest():
    config = _config(teams=[{"team_id": "voc_store_manager", "active": True,
                             "implementation_ref": "app.modules.customer_ops:VocStoreManagerTeam"}])
    registry = build_registry(config=config, tools=_tools(), llm=object())

    assert {manifest.team_id for manifest in registry.manifests()} == {"voc_store_manager"}
    assert registry.get("voc_store_manager").manifest.active is True
    with pytest.raises(RegistryError, match="exactly one active team"):
        registry.resolve(case_type="technical")


def test_duplicate_team_id_is_rejected():
    with pytest.raises(ValidationError, match="duplicate team_id"):
        _config(teams=[
            {"team_id": "same", "active": True, "implementation_ref": "x:y"},
            {"team_id": "same", "active": False, "implementation_ref": "x:y"},
        ])


def test_invalid_implementation_ref_is_rejected_at_build():
    config = _config(teams=[
        {"team_id": "broken", "active": True, "implementation_ref": "not_a_module:Missing"},
    ])
    with pytest.raises(CompositionError, match="implementation_ref cannot be imported"):
        build_registry(config=config, tools=_tools(), llm=object())


def test_enabled_module_without_known_implementation_is_rejected():
    config = _config(module_overrides={"future_module": {"enabled": True}})
    with pytest.raises(CompositionError, match="enabled module has no implementation"):
        build_registry(config=config, tools=_tools(), llm=object())


def test_composer_ui_is_no_longer_a_registered_module():
    """★실측(2026-08-18): `/ui/composer`에 인증이 전혀 없었다 — 고객 접근 가능한
    이 앱에 인증 없는 module/Team/Port 편집 화면이 물려 있었다. 같은 기능은 이제
    `final_project_ui`가 대상의 인증된 `/composer/*` API로만 제공한다
    (`docs/handoff/09_Composer_GUI_계약.md`). 이 테스트는 그 모듈이 이 저장소에서
    다시 조립 가능한 것으로 등록되면 실패한다 — 회귀를 잡는다."""
    config = _config(module_overrides={"composer_ui": {"enabled": True}})
    with pytest.raises(CompositionError, match="enabled module has no implementation"):
        build_registry(config=config, tools=_tools(), llm=object())


def test_duplicate_capability_is_rejected():
    config = _config(teams=[
        {"team_id": "one", "active": True,
         "implementation_ref": "app.modules.customer_ops:VocStoreManagerTeam"},
        {"team_id": "two", "active": True,
         "implementation_ref": "app.modules.customer_ops:VocStoreManagerTeam"},
    ])
    with pytest.raises(CompositionError, match="duplicate capability"):
        build_registry(config=config, tools=_tools(), llm=object())


def test_disabled_graph_store_cannot_be_assembled():
    config = _config(graph_enabled=False)
    with pytest.raises(ProjectConfigError, match="graph_store.*disabled"):
        build_graph_store(connection=None, tenant_id="demo", config=config)


@pytest.mark.parametrize(
    ("graph_port", "broker", "message"),
    [("age", "outbox", "graph_store=age"), ("sql", "redis_streams", "redis_streams")],
)
def test_unsupported_ports_fail_at_build(graph_port, broker, message):
    config = _config(graph_port=graph_port, broker=broker)
    with pytest.raises(CompositionError, match=message):
        build_registry(config=config, tools=_tools(), llm=object())


def test_missing_project_declaration_does_not_fallback():
    missing = Path("config") / "project-file-that-does-not-exist.yaml"
    with pytest.raises(ProjectConfigError, match="does not exist"):
        load_project_config(missing)


def _write_project_config(directory, implementation_ref, *, active=True):
    path = Path(directory) / "project.yaml"
    path.write_text(
        """modules: {vector_rag: {enabled: true}}
ports: {team_executor: local, message_broker: outbox, graph_store: sql}
teams:
  - {team_id: test_team, active: %s, implementation_ref: "%s"}
""" % (str(active).lower(), implementation_ref),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("implementation_ref", "message"),
    [
        ("app.nonexistent:Missing", "cannot be imported"),
        ("app.modules.customer_ops:Missing", "not defined"),
        ("tests.unit.test_project_composition:IncompleteTeam", "TeamModule"),
        ("not-a-ref", "expected 'package.module:Class'"),
    ],
)
def test_load_project_config_rejects_invalid_active_implementation(implementation_ref, message):
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        path = _write_project_config(directory, implementation_ref)
        with pytest.raises(ProjectConfigError, match=message):
            load_project_config(path)


def test_load_project_config_does_not_import_inactive_implementation():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        path = _write_project_config(directory, "app.nonexistent:Missing", active=False)
        config = load_project_config(path)
        assert config.teams[0].active is False


def test_load_project_config_accepts_normal_declaration():
    config = load_project_config(Path("config") / "project.yaml")
    assert {team.team_id for team in config.teams} == {
        "voc_store_manager", "response_generation_review",
        "return_refund", "procurement_order_payment", "fulfillment_logistics",
    }
