"""대상 프로젝트를 찾는다.

★이 프로그램은 **여러 프로젝트를 가리키는 하나의 콘솔**이다.
  프로젝트마다 콘솔 사본을 심으면 사본이 각자 드리프트한다 —
  수십·수백 개가 되면 보수할 때마다 어느 버전을 붙일지 맞춰야 한다.

★대상의 파이썬을 **import 하지 않는다.** 남의 프로세스에서 코드를 실행할 수 없기 때문이다.
  읽는 것은 파일뿐이다.

★"아닌 폴더를 프로젝트라고 하지 않는다." 판별 근거를 함께 낸다 —
  왜 프로젝트로 봤는지/안 봤는지 말하지 않으면 사용자가 목록을 믿을 수 없다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 이것이 있어야 프로젝트다. 조립 선언이 없으면 볼 것이 없다.
MARKER = Path("config") / "project.yaml"

#: 있으면 더 볼 수 있는 것들. 없다고 프로젝트가 아닌 것은 아니다.
OPTIONAL_SOURCES = {
    "evidence": Path("wiki") / "records" / "evidence",   # 2026-09-08: docs/ 가 wiki/records/ 로 합쳐졌다
    "eval_reports": Path("eval") / "reports",
    "introspection": Path("app") / "introspection",
}

#: 훑지 않는 폴더 — 남의 가상환경·캐시까지 뒤지면 느리고 오탐이 난다
SKIP_NAMES = {".git", ".venv", "venv", "node_modules", "__pycache__",
              ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tmp", "dist", "build"}


@dataclass
class Project:
    """탐지된 프로젝트 하나.

    ★`reasons` 를 반드시 채운다. 목록에 이름만 뜨면 사용자가 판단할 수 없다.
    """

    path: Path
    name: str
    is_project: bool
    reasons: list[str] = field(default_factory=list)
    sources: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "name": self.name, "is_project": self.is_project,
                "reasons": list(self.reasons), "sources": dict(self.sources)}


def inspect_path(path: str | Path) -> Project:
    """경로 하나가 대상 프로젝트인지 판별한다.

    ★판별은 **파일 존재**로만 한다. 내용을 파싱해 판단하지 않는다 —
      파싱 실패와 "프로젝트가 아님" 은 다른 사건이고, 여기서 섞으면
      깨진 선언을 가진 프로젝트가 목록에서 통째로 사라진다.
    """
    path = Path(path)
    name = path.name or str(path)

    if not path.exists():
        return Project(path, name, False, ["경로가 없다"])
    if not path.is_dir():
        return Project(path, name, False, ["폴더가 아니다"])

    marker = path / MARKER
    if not marker.is_file():
        return Project(path, name, False, [f"{MARKER.as_posix()} 가 없다"])

    sources = {key: (path / rel).exists() for key, rel in OPTIONAL_SOURCES.items()}
    reasons = [f"{MARKER.as_posix()} 있음"]
    missing = [key for key, present in sources.items() if not present]
    if missing:
        # ★없는 것도 적는다. 화면에서 "왜 이 칸이 비었나" 에 답해야 한다.
        reasons.append("없는 자료: " + ", ".join(sorted(missing)))
    return Project(path, name, True, reasons, sources)


def discover(root: str | Path, *, depth: int = 1) -> list[Project]:
    """루트 아래에서 형제 프로젝트를 찾는다.

    ★`depth=1` 이 기본이다. 깊게 훑으면 남의 하위 폴더까지 프로젝트로 잡고 느려진다.
      더 깊이 봐야 하면 호출자가 **명시적으로** 올린다.

    ★프로젝트가 아닌 폴더도 **목록에 남긴다**(`is_project=False`).
      조용히 빼면 "왜 내 폴더가 안 보이나" 에 답할 수 없다.
    """
    root = Path(root)
    if not root.is_dir():
        return []

    found: list[Project] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name in SKIP_NAMES or child.name.startswith("."):
            continue
        result = inspect_path(child)
        found.append(result)
        if not result.is_project and depth > 1:
            found.extend(discover(child, depth=depth - 1))
    return found


def projects_only(items: list[Project]) -> list[Project]:
    return [item for item in items if item.is_project]
