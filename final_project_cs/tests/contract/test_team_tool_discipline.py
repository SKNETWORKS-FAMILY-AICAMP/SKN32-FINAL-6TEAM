"""DoD-22 — Team 은 인프라를 직접 부르지 않고, allowlist 밖 tool 은 런타임이 막는다.

★**이 파일은 2026-09-06 에 "근거가 없다" 는 것을 발견해 만들었다.**
  `wiki/records/evidence/DoD-22_Team_직접Tool호출_금지.md` 는 2026-08-16 에 「통과」로
  판정하며 근거로 둘을 인용했는데, 확인해 보니

      정적(AST)  `tests/unit/core/test_core_isolation.py`
                 → **그 경로에 파일이 없다.** `tests/contract/` 로 옮겨졌고,
                   옮겨진 그 파일은 `app/core` 만 훑는다. 즉 "Core → Team"
                   한 방향만 보고 **"Team → 인프라" 는 아무도 안 봤다.**
      런타임      `pytest.raises(ToolNotAllowed)`
                 → **그런 테스트가 저장소에 없다.** 문구만 있었다.

  판정 자체는 옳았다(오늘 실측: Team 6개 · 위반 0 · 차단 동작함). 틀린 것은
  **"테스트가 증명한다" 는 서술**이었다. 그래서 판정을 뒤집지 않고 근거를 만든다.

★**`feedback.py` 를 일부러 뺀다 — 여기서 한 번 오진했다.**
  처음엔 `app/modules/**` 를 통째로 훑어 위반 2건이 나왔다
  (`app.presentation.security` 의 `masked`, 지연 `openai` import). 그런데
  이 파일은 **manifest 가 없다 — Team 이 아니다.** 인라인 분류의 라벨 어휘·
  프롬프트 구현이고 소유가 코어 1 쪽이다(`CLAUDE.md` §5, v9 §3-A).
  DoD-22 가 말하는 것은 **Team** 의 tool 규율이므로 대상은 manifest 를 가진
  모듈이다. 범위를 파일 위치가 아니라 **manifest 유무**로 정하는 이유가 이것이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core.contracts import ToolNotAllowed
from app.tools.read_tools import ReadToolbox

MODULES_ROOT = Path("app/modules")

#: Team 이 직접 부르면 안 되는 것들. tool 은 Registry 가 넘겨준 것만 쓴다.
FORBIDDEN_ROOTS = ("app.infrastructure", "psycopg", "openai", "app.presentation", "app.application")


def _team_modules() -> list[Path]:
    """`manifest = TeamManifest(...)` 를 선언한 파일만 Team 으로 본다."""
    found = []
    for path in sorted(MODULES_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.Assign)
               and any(getattr(target, "id", "") == "manifest" for target in node.targets)
               for node in ast.walk(tree)):
            found.append(path)
    return found


TEAM_MODULES = _team_modules()


def test_team_modules_are_actually_found():
    """★대상이 0개면 아래 검사는 언제나 통과한다 — 빈 검사 방지.

    `config/project.yaml` 에 등록된 Team 은 여섯이다(`CLAUDE.md` 머리말).
    """
    assert len(TEAM_MODULES) >= 6, (
        f"Team 모듈을 {len(TEAM_MODULES)}개밖에 못 찾았다. 경로나 manifest 선언 방식이 "
        f"바뀌었는지 확인한다 — 못 찾으면 이 검사 전체가 무력해진다.")


@pytest.mark.parametrize("path", TEAM_MODULES, ids=lambda p: p.stem)
def test_team_does_not_import_infrastructure_directly(path: Path):
    """Team 은 인프라·프레임워크를 직접 import 하지 않는다(정적 검사)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            if any(name == root or name.startswith(root + ".") for root in FORBIDDEN_ROOTS):
                violations.append(f"{path}:{node.lineno} → {name}")

    assert not violations, (
        "Team 이 인프라를 직접 import 한다. tool 은 Registry 가 넘겨준 것만 쓴다:\n  "
        + "\n  ".join(violations))


def test_tool_outside_allowed_tools_is_refused_at_runtime():
    """allowlist 밖의 tool 이름은 실행 전에 거부된다."""
    toolbox = ReadToolbox(lambda: None)
    with pytest.raises(ToolNotAllowed) as caught:
        toolbox.call("read.order", None, {}, ["read.policy"], set())
    assert "read.order" in str(caught.value)


def test_unknown_tool_is_refused_even_when_allowlisted():
    """★allowlist 에 올라 있어도 **구현이 없으면** 거부한다.

    allowlist 는 사람이 손으로 쓰는 목록이라 오타가 난다. 그때 조용히
    `None` 을 돌려주면 Team 이 "근거를 봤다" 고 착각한다.
    """
    toolbox = ReadToolbox(lambda: None)
    with pytest.raises(ToolNotAllowed) as caught:
        toolbox.call("read.nonexistent", None, {}, ["read.nonexistent"], set())
    assert "unknown tool" in str(caught.value)


def test_the_gate_lets_an_allowed_tool_through():
    """★막는 것만 보면 **전부 망가져도 통과**한다 — 통과 경로도 함께 본다.

    allowlist 를 지난 호출은 `ToolNotAllowed` 가 아니라 그 다음 단계(여기서는
    커넥션이 `None` 이라 다른 예외)에서 실패해야 한다.
    """
    toolbox = ReadToolbox(lambda: None)
    with pytest.raises(Exception) as caught:
        toolbox.call("read.policy", None, {}, ["read.policy"], set())
    assert not isinstance(caught.value, ToolNotAllowed), (
        "allowlist 안의 tool 이 관문에서 막혔다 — 관문이 항상 막는 상태다")
