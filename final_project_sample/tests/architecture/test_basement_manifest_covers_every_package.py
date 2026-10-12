"""basement export 경계가 실제 디렉터리를 빠짐없이 덮는지.

★2026-08-30 — `acop_basement/teams`(선언형 Team 실행기)를 새로 만들었는데
  `BASEMENT_COMPONENTS` 에 넣는 것을 잊었다. 그러면 export 를 받은 소비자가
  `DECLARATIVE_TEAM_REF` 를 선언에 쓸 수 없다 — 로드 시점에 import 가 실패한다.

  경계를 **명시 선언**으로 두는 것은 의도한 설계다(디렉터리 크롤링은 경계를
  실수로 넓힌다). 그 대가가 "새 디렉터리를 잊으면 조용히 빠진다" 인데, 그
  대가를 사람 기억에 맡기지 않고 이 테스트가 갚는다.
"""
from __future__ import annotations

from pathlib import Path

from scripts.basement_manifest import BASEMENT_COMPONENTS

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "acop_basement"


def _package_dirs() -> set[str]:
    return {f"acop_basement/{child.name}" for child in PACKAGE_ROOT.iterdir()
            if child.is_dir() and child.name != "__pycache__"}


def test_every_package_directory_is_declared():
    missing = sorted(_package_dirs() - set(BASEMENT_COMPONENTS))
    assert not missing, (
        "acop_basement 에 있는데 BASEMENT_COMPONENTS 에 없다 — export 에서 "
        f"조용히 빠진다: {', '.join(missing)}")


def test_no_declared_component_is_missing_from_disk():
    """반대 방향 — 지운 디렉터리가 선언에 남아 있으면 export 가 거짓말을 한다."""
    stale = sorted(name for name in BASEMENT_COMPONENTS
                   if not (PACKAGE_ROOT.parent / name).is_dir())
    assert not stale, f"선언에 있는데 디스크에 없다: {', '.join(stale)}"
