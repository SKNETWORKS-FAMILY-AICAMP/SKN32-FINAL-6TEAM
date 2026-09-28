"""선언형 Team 이 실제 조립 경로를 통과하는지 — 계획서(2026-08-28) §4 핵심 증명.

★지금까지 "같은 구현체를 다른 이름으로 한 번 더 선언"하는 인스턴스 복제가
  안 됐다. `build_registry()` 가 capability 중복을 거부하기 때문이다
  (`app/composition.py`). 선언형 Team 은 인스턴스마다 자기 capability 를
  선언하므로 이 제약을 우회한다 — 그게 이 파일이 증명하는 것이다.
"""
from __future__ import annotations

import pytest
import yaml

from acop_basement.core.project_config import DECLARATIVE_TEAM_REF, load_project_config
from acop_basement.tools.read_tools import ReadToolbox
from app.composition import CompositionError, build_registry


def _declaration(teams: list[dict]) -> dict:
    return {
        "modules": {"vector_rag": {"enabled": True}, "graph_store": {"enabled": True},
                    "mcp": {"enabled": True}, "ops_ui": {"enabled": True}},
        "ports": {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"},
        "teams": teams,
    }


def _declarative(team_id: str, capability: str) -> dict:
    return {
        "team_id": team_id, "active": True, "implementation_ref": DECLARATIVE_TEAM_REF,
        "parameters": {
            "display_name": team_id, "capabilities": [capability],
            "accepted_case_types": ["demo"], "required_context": ["case_state", "policy"],
            "allowed_tools": ["read.policy"], "knowledge_scope": ["demo"],
            "max_steps": 3, "prompt_key": f"declarative.{team_id}",
        },
    }


def _write(tmp_path, declaration) -> object:
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(declaration, allow_unicode=True), encoding="utf-8")
    return load_project_config(path)


def _tools() -> ReadToolbox:
    return ReadToolbox(tool_functions={"read.policy": lambda _ctx, **_kw: "정책"})


def test_two_declarative_instances_of_the_same_implementation_both_assemble(tmp_path):
    """★핵심 — 같은 implementation_ref 를 두 번 쓰는데도 조립된다."""
    config = _write(tmp_path, _declaration([
        _declarative("first_reviewer", "demo.first"),
        _declarative("second_reviewer", "demo.second"),
    ]))
    registry = build_registry(tools=_tools(), config=config)

    manifests = registry.manifests()
    assert sorted(m.team_id for m in manifests) == ["first_reviewer", "second_reviewer"]
    # 각 인스턴스가 선언한 자기 capability 를 갖는다
    caps = sorted(c for m in manifests for c in m.capabilities)
    assert caps == ["demo.first", "demo.second"]


def test_duplicate_capability_across_declarative_instances_is_still_rejected(tmp_path):
    """복제가 된다고 해서 라우팅 모호성까지 허용되는 것은 아니다."""
    config = _write(tmp_path, _declaration([
        _declarative("a_team", "demo.same"),
        _declarative("b_team", "demo.same"),
    ]))
    with pytest.raises(CompositionError, match="duplicate capability"):
        build_registry(tools=_tools(), config=config)


def test_declarative_manifest_carries_declared_values(tmp_path):
    config = _write(tmp_path, _declaration([_declarative("solo", "demo.solo")]))
    registry = build_registry(tools=_tools(), config=config)
    manifest = registry.manifests()[0]

    assert manifest.display_name == "solo"
    assert manifest.allowed_tools == ["read.policy"]
    assert manifest.max_steps == 3
    assert manifest.implementation_revision == "declarative.v1"
