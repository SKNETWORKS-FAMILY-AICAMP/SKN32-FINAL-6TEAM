"""`acop_composer` 경계 — 선택 패키지가 **어느 제품도 끌어오지 않는다.**

★왜 코드 리뷰에 맡기지 않는가. 이 패키지는 sample 저장소 **안에서** 개발되므로
  `from acop_basement...` 한 줄이 아무 때나 문법적으로 통한다. 그리고 그 한 줄은
  sample 에서는 **아무 증상도 안 낸다** — 전부 설치돼 있으니까. 증상은 `pip install
  acop_composer` 를 한 `final_project_cs` 에서 처음 나타난다:

    1. 등록표가 남의 것이라 cs 의 Team 여섯이 전부 "미등록" 422
    2. 스키마가 남의 것이라(`extra="forbid"`) cs 선언이 바로 검증 실패
    3. 설정·DB 세션·저장소·인증이 sample 코어 것이라 런타임이 두 벌

  여기서 걸려야 그때 안 걸린다.

★거꾸로도 본다. 제품의 **코어**(`acop_basement`)가 이 선택 패키지를 import 하면
  Composer 를 안 깐 배포에서 코어가 깨진다. 결합 방향이 뒤집히는 것이라
  코어 → 패키지 방향도 금지한다. 잇는 곳은 제품 조립부(`app/composer_host.py`)
  단 하나다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "acop_composer"
CORE_ROOT = REPO_ROOT / "acop_basement"

#: 패키지 안에 들어오면 안 되는 것 — 어느 제품의 것이든.
FORBIDDEN_IN_PACKAGE = ("acop_basement", "app")

#: 코어가 선택 패키지를 부르면 안 된다.
FORBIDDEN_IN_CORE = ("acop_composer",)


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    """이 파일이 import 하는 최상위 모듈 이름들. ★함수 안 import 도 본다 —
    지연 import 로 숨기면 경계는 그대로 무너진다."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            # `from . import x` (level>0) 은 패키지 내부다.
            if node.level == 0 and node.module:
                found.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
    return found


def _violations(root: Path, forbidden: tuple[str, ...]) -> list[str]:
    bad: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for lineno, module in _imported_modules(path):
            top = module.split(".")[0]
            if top in forbidden:
                bad.append(f"{path.relative_to(REPO_ROOT)}:{lineno} → {module}")
    return bad


def test_package_source_exists():
    """★파일이 없어서 통과하는 검사를 만들지 않는다."""
    assert PACKAGE_ROOT.is_dir()
    assert len(list(PACKAGE_ROOT.glob("*.py"))) >= 5


def test_package_does_not_import_any_product():
    """패키지는 호스트가 준 것만 쓴다 — 제품 코드를 직접 부르지 않는다."""
    bad = _violations(PACKAGE_ROOT, FORBIDDEN_IN_PACKAGE)
    assert not bad, (
        "`acop_composer` 가 제품 코드를 import 한다. 필요한 것은 "
        "`ComposerHost` 에 필드로 추가하고 호스트가 넘기게 한다:\n  "
        + "\n  ".join(bad))


def test_core_does_not_import_the_optional_package():
    """코어는 Composer 없이도 떠야 한다 — 잇는 곳은 `app/composer_host.py` 하나다."""
    bad = _violations(CORE_ROOT, FORBIDDEN_IN_CORE)
    assert not bad, (
        "`acop_basement`(코어)가 선택 패키지 `acop_composer` 를 import 한다. "
        "Composer 를 안 깐 배포에서 코어가 깨진다:\n  " + "\n  ".join(bad))


def test_the_adapter_is_the_single_seam():
    """제품 쪽에서 패키지를 아는 파일은 **조립부에만** 있어야 한다.

    ★도메인 모듈이나 프레젠테이션이 패키지를 직접 부르기 시작하면, 그 순간
      Composer 를 빼는 릴리즈 빌드가 안 된다(v9 §8-D: "cs 소스 안에 Composer
      구현 금지" 가 지키려는 성질이 이것이다).
    """
    allowed = {"app/composer_host.py", "app/entrypoint.py", "app/config_service.py"}
    seams = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in sorted((REPO_ROOT / "app").rglob("*.py"))
        if "__pycache__" not in path.parts
        and any(m.split(".")[0] == "acop_composer" for _, m in _imported_modules(path))
    }
    assert seams <= allowed, (
        "조립부 밖에서 `acop_composer` 를 부른다: " + ", ".join(sorted(seams - allowed)))


@pytest.mark.parametrize("module", ["api", "auth", "catalog", "service", "stores", "host"])
def test_every_package_module_imports_alone(module: str):
    """★제품을 안 깐 상태를 흉내 내지는 못하지만, 적어도 **패키지만** import 해서
    모듈이 열리는지는 본다. 제품 모듈이 import 시점에 필요하면 여기서 터진다."""
    __import__(f"acop_composer.{module}")
