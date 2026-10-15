"""기존 비활성 실행 우회를 확인한다. 제품 수정·DB·네트워크 호출 없음."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.core.registry import RegistryError, TeamRegistry
from app.core.remote_team.executor import LocalTeamExecutor


class DiningProbe:
    manifest = SimpleNamespace(
        team_id="dining", supported_contract_versions=["1.0"],
        accepted_case_types=["dining"], active=False, allowed_tools=[],
    )

    async def execute(self, task):
        return "inactive_team_was_executed"


def main():
    registry = TeamRegistry([DiningProbe()])
    observations = {}
    try:
        registry.resolve(case_type="dining")
    except RegistryError as exc:
        observations["inactive_auto_route"] = str(exc)
    observations["inactive_direct_get_active"] = registry.get("dining").manifest.active
    coroutine = LocalTeamExecutor(registry).execute(
        SimpleNamespace(team_id="dining", allowed_tools=[])
    )
    try:
        coroutine.send(None)
    except StopIteration as result:
        observations["inactive_direct_execute"] = result.value
    try:
        TeamRegistry().get("dining")
    except RegistryError as exc:
        observations["absent_get"] = str(exc)
    assert observations["inactive_auto_route"].startswith("case must resolve")
    assert observations["inactive_direct_get_active"] is False
    assert observations["inactive_direct_execute"] == "inactive_team_was_executed"
    assert observations["absent_get"] == "unknown team: dining"
    paths = [
        "app/core/registry.py", "app/core/remote_team/executor.py",
        "app/core/project_config.py", "app/composition.py",
        "app/application/controller.py", "app/application/runtime.py",
        "app/domains/travel_ops/components/conversation/case_dispatch.py",
        "app/domains/travel_ops/entry/trip_api.py",
    ]
    print(json.dumps({
        "observation_checks": {"matched": 4, "total": 4},
        "meaning": "existing behavior reproduction, not target acceptance tests",
        "observations": observations,
        "source_sha256": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
