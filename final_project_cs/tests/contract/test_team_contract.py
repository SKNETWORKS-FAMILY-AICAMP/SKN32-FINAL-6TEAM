# -*- coding: utf-8 -*-
"""등록된 Team 이 계약(`TeamModule` 프로토콜 · `TeamManifest`)을 지키는가.

★2026-09-10 — 전에는 `VocStoreManagerTeam` **하나만** 봤다. 나머지 다섯이
  계약을 어겨도 초록이었고, 도메인이 바뀌자 그 하나가 사라져 검사 자체가
  없어질 뻔했다. 지금은 `build_registry()` 가 주는 **등록된 전부**를 본다.

★`max_steps` 를 6 으로 못 박지 않는다. 팀마다 필요한 도구 수가 다르다 —
  잠긴 예약 팀(Lodging/Flight)은 조회 하나면 끝난다. 대신 **선언돼 있고
  1 이상인지**를 본다(0 이면 도구를 한 번도 못 부른다).
"""
from __future__ import annotations

import pytest

from app.composition import build_registry
from app.core.contracts import TeamManifest, TeamModule

REGISTERED = [(m.team_id, m) for m in build_registry().manifests()]


def test_at_least_one_team_is_registered():
    """★목록이 비면 아래 검사가 전부 통과한다."""
    assert REGISTERED, "등록된 Team 이 없다 — config/project.yaml 을 확인한다."


# invariant: INV-CS-TEAM-001
@pytest.mark.parametrize("team_id,manifest", REGISTERED, ids=lambda v: v if isinstance(v, str) else "")
def test_team_manifests_implement_protocol(team_id: str, manifest: TeamManifest):
    module = build_registry().get(team_id).module
    assert isinstance(module, TeamModule), (
        f"{team_id} 가 TeamModule 프로토콜을 만족하지 않는다 "
        f"(manifest 속성과 async execute 가 있어야 한다).")
    assert isinstance(manifest, TeamManifest)
    assert manifest.contract_name == "a_cop.team_task"
    assert manifest.supported_contract_versions == ["1.0"]
    assert manifest.max_steps >= 1, (
        f"{team_id}.max_steps 가 {manifest.max_steps} 다 — 도구를 한 번도 못 부른다.")
    assert manifest.active


# invariant: INV-CS-TEAM-002
@pytest.mark.parametrize("team_id,manifest", REGISTERED, ids=lambda v: v if isinstance(v, str) else "")
def test_manifest_scopes_are_exact(team_id: str, manifest: TeamManifest):
    """★선언은 **정확**해야 한다. 중복도 빈 값도 실수의 신호다."""
    assert manifest.allowed_tools, f"{team_id} 가 도구를 하나도 선언하지 않았다."
    assert len(set(manifest.allowed_tools)) == len(manifest.allowed_tools), (
        f"{team_id}.allowed_tools 에 중복이 있다: {manifest.allowed_tools}")
    assert manifest.knowledge_scope, f"{team_id} 가 knowledge_scope 를 비워 뒀다."
    assert manifest.capabilities, f"{team_id} 가 capability 를 하나도 선언하지 않았다."
    if manifest.default_capability is not None:
        assert manifest.default_capability in manifest.capabilities, (
            f"{team_id}.default_capability 가 선언되지 않은 capability 를 가리킨다.")
