"""`acop_composer_ui` 경계 — UI 용 클라이언트가 대상 코드를 끌어오지 않는다.

★`docs/handoff/10` 이 basement 순수성을 검사하는 것과 같은 원리다. 다만
  여기서 지키는 것은 도메인 무지가 아니라 **"UI 프로세스에 대상의 검증
  모델이 들어오지 않는다"**(`final_project_ui/CLAUDE.md` §0.2·§0.3)이다.

  검사를 코드 리뷰에 맡기지 않는 이유: 이 패키지는 sample 저장소 안에서
  개발되므로 `acop_basement` 를 import 하는 것이 문법적으로 아무 때나
  가능하다. 한 줄만 들어가도 UI 는 대상 스키마에 묶인다.
"""
from __future__ import annotations

from pathlib import Path
import re
import tomllib

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "packages" / "acop_composer_ui"
SOURCE_ROOT = PACKAGE_ROOT / "acop_composer_ui"

#: UI 프로세스에 들어오면 안 되는 것들.
FORBIDDEN_IMPORTS = ("acop_basement", "acop_composer.", "app.", "fastapi", "pydantic", "yaml")


def _python_files() -> list[Path]:
    return sorted(SOURCE_ROOT.rglob("*.py"))


def test_package_source_exists():
    """검사 대상이 0개면 검사가 통과해도 아무 의미가 없다."""
    files = _python_files()
    assert files, f"검사할 소스가 없다: {SOURCE_ROOT}"


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_forbidden_imports(path: Path):
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("import ") or stripped.startswith("from ")):
            continue
        for forbidden in FORBIDDEN_IMPORTS:
            assert forbidden not in stripped, (
                f"{path.name}: UI 클라이언트가 '{forbidden}' 을 import 한다 — "
                "대상의 검증 모델이 UI 프로세스로 들어온다")


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_does_not_reimplement_target_validation(path: Path):
    """대상 Core 모델 이름이 코드에 등장하면 스키마 복제의 신호다."""
    text = path.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines()
                     if not line.strip().startswith("#"))
    # docstring 안의 설명(§0.2 인용 등)은 허용한다 — 실제 식별자 사용만 잡는다.
    code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
    for name in ("ProjectConfig", "TeamManifest", "ContextPack"):
        assert name not in code, f"{path.name}: 대상 Core 모델 '{name}' 을 다룬다"


def test_declares_no_dependencies():
    """의존성이 비어 있는 것이 이 패키지의 계약이다."""
    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["dependencies"] == [], (
        "UI 클라이언트는 표준 라이브러리만 쓴다 — 서버 프레임워크를 끌어오면 "
        "UI 배포에 대상의 런타임이 섞인다")


def test_is_excluded_from_the_product_distribution():
    """제품 배포판이 이 패키지를 삼키면 '따로 설치한다' 는 전제가 깨진다."""
    root = tomllib.loads(
        (PACKAGE_ROOT.parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    exclude = root["tool"]["setuptools"]["packages"]["find"]["exclude"]
    assert any(pattern.startswith("packages") for pattern in exclude), (
        "루트 pyproject 가 packages/ 를 제외하지 않는다")
