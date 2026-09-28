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


def _relative(path: str | Path) -> Path:
    """절대 경로를 `app/...` 상대 경로로 — 정적 검사가 모은 경로와 같은 모양으로 맞춘다.

    ★처음엔 경로 조각에서 첫 `app` 을 찾아 잘랐다. 상위 폴더 이름이 `app` 이면
      (`/home/app/repo/final_project_cs/app/...`) 엉뚱한 곳에서 잘린다(코덱스 검증 2026-09-28).
      시험은 `final_project_cs` 에서 돌므로 그 폴더 기준으로 자른다.
    """
    return Path(path).resolve().relative_to(Path.cwd().resolve())


def _declared_team_files() -> dict[str, Path]:
    """등록 문자열이 가리키는 클래스가 **실제로 정의된 파일**.

    ★2026-09-28 — 전에는 `app.modules.travel_ops.activity` 를 `activity.py` 로
      바꿔 찾았다. Team 을 폴더(`activity/team.py` 나 `activity/__init__.py`)로
      옮기면 그 파일이 없어 이 검사가 실패했다. 파일 하나든 폴더든 같은 등록
      문자열로 부르므로, 경로를 짐작하지 않고 클래스를 불러와 정의된 곳을 묻는다.
    """
    import importlib
    import inspect

    from app.core.project_config import load_project_config

    files = {}
    for team in load_project_config().teams:
        module_name, _, class_name = team.implementation_ref.partition(":")
        cls = getattr(importlib.import_module(module_name), class_name)
        files[team.implementation_ref] = _relative(inspect.getsourcefile(cls))
    return files


def _team_package_files() -> list[Path]:
    """팀이 가진 폴더 안 `.py` 전부 — 도우미 파일·엔진도 팀 코드다.

    파일 하나로 살 때는 그 파일만 Team 이었다. 폴더로 쪼개면 인프라 호출을
    옆 파일로 옮기기만 해도 규율 검사를 빠져나가므로, 폴더째 검사한다.

    팀의 폴더는 둘이다 — `<팀>/`(팀 본체 폴더)와 `<팀>_engine/`(Mobility 방식 엔진).
    ★처음엔 본체 폴더만 봐서 `mobility_engine/` 이 통째로 빠졌다. 본체가 파일 하나
      (`mobility.py`)면 부모가 `travel_ops/` 라 엔진까지 건너뛰었다(코덱스 검증 2026-09-28).
    `travel_ops/` 자체(여러 팀이 함께 쓰는 곳)는 팀 폴더로 치지 않는다.
    """
    out: set[Path] = set()
    for ref, path in _declared_team_files().items():
        team_name = ref.split(":")[0].rsplit(".", 1)[-1]           # app.modules.travel_ops.mobility → mobility
        base = path.parent.parent if path.parent.name == team_name else path.parent
        for folder in (base / team_name, base / f"{team_name}_engine"):
            if folder.is_dir() and folder != MODULES_ROOT:
                out.update(p for p in folder.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(out)


TEAM_MODULES = _team_modules()
TEAM_FILES = sorted(set(TEAM_MODULES) | set(_team_package_files()))


def test_team_modules_are_actually_found():
    """★대상이 0개면 아래 검사는 언제나 통과한다 — 빈 검사 방지.

    ★2026-09-10 — 전에는 `>= 6` 이라는 **숫자**를 박아 뒀다("등록된 Team 은
      여섯"). 그런데 세는 것은 Team 이 아니라 **파일**이라, 한 파일에 두 팀을
      담는 순간(`locked_bookings.py` 의 Lodging·Flight) 숫자가 어긋난다.
      숫자를 고치면 다음에 또 어긋나므로, **등록이 가리키는 파일**과 대조한다.
    """
    declared = set(_declared_team_files().values())
    found = set(TEAM_MODULES)
    missing = sorted(str(p) for p in declared - found)
    assert declared, "config/project.yaml 에 Team 선언이 없다."
    assert not missing, (
        f"등록된 Team 이 사는 파일을 정적 검사가 못 찾았다: {missing} / "
        f"찾은 파일: {sorted(str(p) for p in found)} — "
        f"manifest 선언 방식이나 경로가 바뀌었는지 확인한다. "
        f"못 찾으면 아래 규율 검사가 그 팀을 **건너뛴다.**")


@pytest.mark.parametrize("path", TEAM_FILES, ids=lambda p: "/".join(p.parts[-2:]))
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
