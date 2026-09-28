"""v9 §8-D 게이트 — **이 저장소 안에 Composer 구현을 두지 않는다.**

★2026-09-06 이전에는 `app/presentation/api/composer.py`(157줄) ·
  `app/application/composer_service.py`(167줄) · `app/presentation/composer_auth.py`
  (76줄)가 sample 것을 손으로 베낀 사본이었다. 결과가 어땠나:

    - sample 이 `/catalog`·`/changes`·`/revisions`·`/restore` 를 갖는 동안
      cs 는 네 개에 머물러, 콘솔의 카탈로그·변경 카드가 cs 에서는 안 떴다
    - 쓰기 채널이 **고객 릴리즈에 그대로 실려** 있었고 scope 하나가 유일한
      방어였다

  이 게이트가 그 상태로 되돌아가는 것을 막는다. 사람 눈으로는 막을 수 없다 —
  파일 하나 더 만드는 것이 문법적으로 아무 때나 가능하기 때문이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 이 저장소에서 `acop_composer` 를 알아도 되는 곳. **관리용 빌드의 조립부뿐**이다.
ALLOWED_SEAMS = {"app/composer_host.py", "app/entrypoint.py"}

#: 다시 생기면 안 되는 사본들.
REMOVED_COPIES = (
    "app/presentation/api/composer.py",
    "app/application/composer_service.py",
    "app/presentation/composer_auth.py",
)


def _imported_modules(path: Path) -> list[tuple[int, str]]:
    """이 파일이 import 하는 모듈. ★함수 안 지연 import 도 본다."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
    return found


def _app_files() -> list[Path]:
    return [p for p in sorted((REPO_ROOT / "app").rglob("*.py"))
            if "__pycache__" not in p.parts]


def test_app_source_exists():
    """★파일이 없어서 통과하는 검사를 만들지 않는다."""
    assert len(_app_files()) > 30


@pytest.mark.parametrize("relative", REMOVED_COPIES)
def test_the_hand_copied_implementation_does_not_come_back(relative: str):
    assert not (REPO_ROOT / relative).exists(), (
        f"{relative} 이 다시 생겼다. Composer 구현은 `acop_composer` 패키지 하나뿐이고 "
        "이 저장소는 `app/composer_host.py` 로 자기 것만 넘긴다(v9 §8-D).")


def test_only_the_management_seam_knows_the_package():
    seams = {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for path in _app_files()
        if any(m.split(".")[0] == "acop_composer" for _, m in _imported_modules(path))
    }
    assert seams <= ALLOWED_SEAMS, (
        "조립부 밖에서 `acop_composer` 를 부른다 — 그러면 Composer 를 뺀 릴리즈 "
        "빌드가 깨진다: " + ", ".join(sorted(seams - ALLOWED_SEAMS)))


def test_the_release_app_does_not_pull_the_package_in():
    """★릴리즈 진입점(`app/presentation/api/app.py`)이 패키지를 import 하면
    안 된다. 실제로 **막고 띄워 보는** 검사는 아래 e2e 가 한다."""
    module = REPO_ROOT / "app" / "presentation" / "api" / "app.py"
    offenders = [f"line {n}: {m}" for n, m in _imported_modules(module)
                 if m.split(".")[0] == "acop_composer"]
    assert not offenders, offenders


def test_the_registry_and_the_catalog_agree():
    """호스트가 UI 에 내는 목록과 로더가 허용하는 목록이 **같은 집합**이어야 한다.

    ★어긋나면 둘 중 하나다: UI 에 뜨는데 저장이 422 로 거부되거나(카탈로그가
      더 넓다), 저장은 되는데 UI 에서 고를 수 없다(등록표가 더 넓다).
      둘 다 운영자에게는 "되는데 안 된다" 로 보인다.
    """
    from app.composer_host import composer_host
    from app.core.project_config import KNOWN_IMPLEMENTATION_REFS

    host = composer_host()
    assert host.known_refs == KNOWN_IMPLEMENTATION_REFS, {
        "카탈로그에만": sorted(host.known_refs - KNOWN_IMPLEMENTATION_REFS),
        "등록표에만": sorted(KNOWN_IMPLEMENTATION_REFS - host.known_refs),
    }
