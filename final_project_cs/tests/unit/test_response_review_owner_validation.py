# -*- coding: utf-8 -*-
"""`response_review` 를 켜면 그 팀이 **등록돼 있어야** 한다.

★2026-09-09 — 도메인 교체로 팀 목록이 통째로 바뀌었는데
  `response_review.owner_team_id` 는 옛 `response_generation_review` 를
  가리킨 채 남았다. `enabled: false` 라 어디서도 안 터졌지만, 켜는 순간
  `Controller._maybe_review` 의 `registry.get()` 이 **고객 요청을 처리하는
  도중** `RegistryError` 로 죽는다. 기동 때 잡는 편이 낫다.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.project_config import ProjectConfig

_MODULES = {"vector_rag": {"enabled": True}, "graph_store": {"enabled": True},
            "a2a_executor": {"enabled": False}, "mcp": {"enabled": True},
            "voc": {"enabled": True}, "ops_ui": {"enabled": True}}
_PORTS = {"team_executor": "local", "message_broker": "outbox", "graph_store": "sql"}
_TEAM = {"team_id": "activity", "active": True,
         "implementation_ref": "app.modules.travel_ops.activity:ActivityTeam"}


def _config(review: dict, *, teams=None):
    return ProjectConfig.model_validate({
        "modules": _MODULES, "ports": _PORTS,
        "teams": teams or [_TEAM], "response_review": review})


def test_enabled_with_an_unregistered_owner_is_rejected():
    with pytest.raises(ValidationError, match="owner_team_id"):
        _config({"enabled": True, "owner_team_id": "response_generation_review"})


def test_enabled_with_a_registered_owner_is_accepted():
    config = _config({"enabled": True, "owner_team_id": "activity"})
    assert config.response_review.owner_team_id == "activity"


def test_disabled_with_a_stale_owner_is_accepted():
    """★도메인 교체 중에 옛 이름이 남는 것은 「아직 대체 팀이 없다」는 사실이다.
    그것까지 막으면 교체 자체를 못 한다 — 지금 `config/project.yaml` 이 이 상태다."""
    config = _config({"enabled": False, "owner_team_id": "response_generation_review"})
    assert config.response_review.enabled is False


def test_an_inactive_owner_does_not_count_as_registered():
    """★`active: false` 인 팀은 조립이 라우팅에 쓰지 않는다. 검토 팀도 마찬가지다."""
    teams = [_TEAM, {"team_id": "dining", "active": False,
                     "implementation_ref": "app.modules.travel_ops.dining:DiningTeam"}]
    with pytest.raises(ValidationError, match="owner_team_id"):
        _config({"enabled": True, "owner_team_id": "dining"}, teams=teams)
