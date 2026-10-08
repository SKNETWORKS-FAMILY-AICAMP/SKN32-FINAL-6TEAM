"""Team 이 파일 하나로 살든 폴더로 살든 같은 등록 문자열로 불린다 (2026-09-28).

팀마다 코드를 `app/domains/travel_ops/instances/` 아래에 두는 방식이 셋이다. 셋 다 허용한다.

    파일 하나      activity.py                     (예전 방식)
    폴더           activity/__init__.py · team.py  (본체는 어느 쪽에 둬도 된다)
    파일 + 엔진    mobility.py + mobility_engine/  (엔진을 다른 이름 폴더로 옆에 둔다)

어느 방식이든 등록 문자열은 `app.domains.travel_ops.instances.<팀>:<클래스>` 그대로다.
여기서는 방식이 섞여 **조용히 틀리는** 경우만 막는다.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import pytest

from app.core.project_config import load_project_config

#: ★`[2026-10-06]` 팀은 `app/domains/travel_ops/instances/` 칸에 산다(D-CS-013). 그 전에는 travel_ops 바로 아래였다.
TRAVEL_OPS = Path("app/domains/travel_ops/instances")


def _teams():
    return [(team.team_id, team.implementation_ref) for team in load_project_config().teams]


def test_a_file_and_a_folder_with_the_same_name_do_not_coexist():
    """★`activity.py` 와 `activity/` 가 같이 있으면 파이썬은 폴더를 먼저 불러온다.

    그러면 `activity.py` 는 **아무 오류 없이 무시된다** — 고쳐도 반영이 안 되고
    시험도 폴더 쪽 코드만 본다. 병합 충돌을 풀다 둘 다 남기기 쉬운 자리라 막는다.
    엔진을 따로 둘 때는 `mobility_engine/` 처럼 다른 이름을 쓴다.
    """
    clashes = sorted(
        path.name for path in TRAVEL_OPS.glob("*.py")
        if (TRAVEL_OPS / path.stem / "__init__.py").is_file())
    assert not clashes, (
        f"같은 이름의 파일과 폴더가 함께 있다: {clashes} — 폴더가 이기고 파일은 무시된다. "
        f"하나만 남긴다(폴더로 옮겼으면 파일을 지운다).")


def test_every_team_folder_has_an_init():
    """`__init__.py` 없는 폴더는 등록 문자열로 부를 수 없다(네임스페이스 패키지가 돼 클래스를 못 찾는다)."""
    registered = {ref.split(":")[0].rsplit(".", 1)[-1] for _, ref in _teams()}
    missing = sorted(
        name for name in registered
        if (TRAVEL_OPS / name).is_dir() and not (TRAVEL_OPS / name / "__init__.py").is_file())
    assert not missing, f"팀 폴더에 __init__.py 가 없다: {missing}"


@pytest.mark.parametrize("team_id,ref", _teams(), ids=[team_id for team_id, _ in _teams()])
def test_the_registered_class_is_reachable_the_same_way(team_id: str, ref: str):
    """등록 문자열 그대로 클래스가 불리고, 그 manifest 의 team_id 가 등록과 같다."""
    module_name, _, class_name = ref.partition(":")
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name, None)
    assert cls is not None, (
        f"{ref} — `{module_name}` 에 `{class_name}` 이 없다. 폴더로 옮겼다면 "
        f"`__init__.py` 에서 `from .team import {class_name}` 로 다시 내보낸다.")
    assert cls.manifest.team_id == team_id
    source = Path(inspect.getsourcefile(cls)).resolve()
    assert (Path.cwd() / "app" / "domains").resolve() in source.parents, (
        f"{ref} 의 클래스가 app/domains 밖에 정의돼 있다: {source}")
