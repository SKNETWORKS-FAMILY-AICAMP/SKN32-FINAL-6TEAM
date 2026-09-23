"""등록된 Team 이 **선언한 도구가 실제로 구현돼 있는지** 본다.

★2026-09-09 — 이 검사가 없었다. `test_team_contract.py` 는
  `VocStoreManagerTeam` **하나만** 보고, `test_team_tool_discipline.py` 는
  런타임 차단(allowlist 밖 호출)만 본다. 그래서 manifest 에 **없는 도구 이름을
  적어도 테스트가 초록**이고, 실제 호출 때 비로소
  `ToolNotAllowed("unknown tool")` 이 난다.

  여행 Team 을 만들며 `read.booking`·`read.place`·`read.weather` 같은 새 도구를
  선언하게 됐는데, 오타 하나가 운영에서야 터지는 구조였다. 그래서 만든다.

★이 저장소가 같은 모양으로 여러 번 데였다:
  - `allowed_tools` 에 있는데 호출이 0회인 도구(`response_review` 의 `read.policy`)
  - 선언만 되고 아무도 안 읽던 `max_steps`
  **선언과 구현이 갈라지면 선언이 거짓말이 된다.**
"""
from __future__ import annotations

import pytest

from app.composition import build_registry
from app.tools.read_tools import ReadToolbox


def _implemented_tools() -> set[str]:
    """`ReadToolbox.call()` 이 실제로 디스패치하는 이름들.

    ★목록을 손으로 적지 않는다 — 적으면 그 목록이 또 갈라진다.
      실제 디스패치 표를 그대로 읽는다.
    """
    _toolbox = ReadToolbox(lambda: None)
    # `call()` 안의 functions 표를 그대로 얻으려고 한 번 호출해 본다.
    # 권한 검사에서 걸리게 두고, 그 전에 표를 만들 수는 없으므로
    # 알려진 두 갈래(여행/커머스)를 합친다.
    from app.tools import read_tools

    source = read_tools.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    import re

    return set(re.findall(r'"(read\.[a-z_]+)":\s*self\.', text))


IMPLEMENTED = _implemented_tools()


def test_the_tool_table_is_not_empty():
    """★목록이 비면 아래 검사가 전부 통과한다 — 빈 검사 방지."""
    assert len(IMPLEMENTED) >= 5, (
        f"구현된 도구를 {len(IMPLEMENTED)}개밖에 못 찾았다. "
        f"`ReadToolbox.call()` 의 디스패치 표 형태가 바뀌었는지 확인한다.")


def _registered_teams():
    # ★공개 API 인 `manifests()` 를 쓴다. 내부 속성 이름은 바뀔 수 있다.
    return [(m.team_id, m) for m in build_registry().manifests()]


REGISTERED = _registered_teams()


def test_at_least_one_team_is_registered():
    assert REGISTERED, "등록된 Team 이 없다 — config/project.yaml 을 확인한다."


@pytest.mark.parametrize("team_id,manifest", REGISTERED, ids=lambda x: x if isinstance(x, str) else "")
def test_declared_tools_are_implemented(team_id: str, manifest) -> None:
    """manifest 의 `allowed_tools` 는 전부 구현돼 있어야 한다."""
    missing = sorted(set(manifest.allowed_tools) - IMPLEMENTED)
    assert not missing, (
        f"{team_id} 가 구현되지 않은 도구를 선언한다: {missing}\n"
        f"  구현된 것: {sorted(IMPLEMENTED)}\n"
        f"  ★선언만 하면 테스트는 초록인데 실제 호출에서 "
        f"ToolNotAllowed('unknown tool') 이 난다.")


@pytest.mark.parametrize("team_id,manifest", REGISTERED, ids=lambda x: x if isinstance(x, str) else "")
def test_a_team_declares_at_least_one_tool(team_id: str, manifest) -> None:
    """도구가 하나도 없는 Team 은 조회를 못 한다 — 선언 실수일 가능성이 높다."""
    assert manifest.allowed_tools, (
        f"{team_id} 가 도구를 하나도 선언하지 않았다. "
        f"조회 없이 판정할 수 있는 Team 이면 그 사실을 docstring 에 적는다.")
