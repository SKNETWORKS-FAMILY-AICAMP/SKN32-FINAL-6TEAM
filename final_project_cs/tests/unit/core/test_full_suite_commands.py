"""전체 테스트를 돌린다고 말하는 스크립트가 실제로 전체를 도는지 검사한다.

★같은 결함이 두 번 나왔다(2026-09-02 둘 다 수정):

    scripts/check_release_gate.py   `pytest tests -q -m "not live"`
    scripts/verify_dod.py           `pytest tests -q`

  둘 다 `tests` 를 인자로 줘서 **`eval/tests/` 14건이 조용히 빠졌다**
  (실측: 542 수집 vs 556). 빠지던 것 중에
  `eval/tests/test_holdout_labeling.py` — DoD-15, 즉 RC 를 막고 있는 바로
  그 항목의 도구 테스트가 있었다. **게이트와 DoD 검증 스크립트가 "통과"라고
  말하면서 정작 차단 항목의 테스트는 한 번도 안 돌리고 있었다.**

  두 번 나온 결함은 세 번 나온다. 그래서 이 검사를 둔다.

★부분 실행 자체는 정상이다 — `docs/evidence/` 의 DoD 별 증거는 해당 영역만
  돌리는 것이 맞다. 여기서 보는 것은 **`scripts/` 의 실행 파일**뿐이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"

#: pytest 인자 중 "테스트를 고르는 경로"가 아닌 것들. 이들은 있어도 전체를 돈다.
NON_PATH_ARGS_PREFIXES = ("-", "not ", "python")


def _pytest_invocations(path: Path) -> list[tuple[int, list[str]]]:
    """소스에서 `[..., "-m", "pytest", ...]` 형태의 명령 리스트를 뽑는다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.List):
            continue
        parts: list[str] = []
        for element in node.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                parts.append(element.value)
            else:
                parts.append("<expr>")  # sys.executable 등
        if "pytest" in parts:
            found.append((node.lineno, parts))
    return found


SCRIPT_FILES = sorted(p for p in SCRIPTS_DIR.glob("*.py") if not p.name.startswith("_"))


# invariant 성격 — scripts/ 에 새 파일이 생겨도 자동으로 포함된다.
@pytest.mark.parametrize("path", SCRIPT_FILES, ids=lambda p: p.name)
def test_scripts_do_not_narrow_the_suite_with_a_path_argument(path: Path):
    offenders = []
    for lineno, parts in _pytest_invocations(path):
        after_pytest = parts[parts.index("pytest") + 1:]
        # 경로처럼 생긴 인자(옵션도 아니고 옵션 값도 아닌 것)를 찾는다.
        index = 0
        while index < len(after_pytest):
            argument = after_pytest[index]
            if argument.startswith("-"):
                # `-m "not live"` 처럼 값을 하나 먹는 옵션은 그 값까지 건너뛴다.
                if argument in {"-m", "-k", "-p", "--rootdir"}:
                    index += 2
                    continue
                index += 1
                continue
            if not argument.startswith(NON_PATH_ARGS_PREFIXES) and argument != "<expr>":
                offenders.append(f"{path.name}:{lineno}  경로 인자 {argument!r}")
            index += 1

    assert not offenders, (
        "전체 테스트를 돌려야 하는 스크립트가 경로를 줘서 범위를 좁히고 있다.\n"
        "  `pytest tests` 는 eval/tests/ 를 빠뜨린다 — 경로 없이 `pytest` 로 부른다.\n  "
        + "\n  ".join(offenders))


def test_the_check_actually_finds_pytest_invocations():
    """★아무것도 못 찾으면 위 테스트는 언제나 통과한다 — 빈 검사 방지."""
    total = sum(len(_pytest_invocations(path)) for path in SCRIPT_FILES)
    assert total >= 2, (
        f"scripts/ 에서 pytest 호출을 {total}개밖에 못 찾았다 — "
        "AST 추출이 깨졌거나 호출 형태가 바뀌었다")
