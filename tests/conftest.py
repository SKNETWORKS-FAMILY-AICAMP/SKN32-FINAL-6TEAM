"""저장소 맨 위 `tests/<팀>/` 시험의 입구 (2026-09-28).

팀마다 시험을 두는 자리가 둘이다. 둘 다 CI 가 돌린다.

    final_project_cs/tests/unit/travel/<팀>/   ← cs 시험과 같은 방식(권장)
    tests/<팀>/                                ← 저장소 맨 위(Mobility 방식)

여기는 뒤쪽을 위한 설정이다.
- `final_project_cs/` 와 저장소 루트를 import 경로 **맨 앞**에 넣는다 —
  `from app.modules.travel_ops.mobility_engine... import ...` 가 cs 의 `app` 을 찾게.
  (CI 는 PYTHONPATH 에 final_project_sample 을 두는데, 거기에도 `app` 이 있다.)
- ★**직접 실행하는 스크립트 방식 파일은 pytest 가 모으지 않는다.**
  `def test_...` 가 하나도 없거나, 파일을 불러오기만 해도 `sys.exit()` 가 도는
  파일은 모으는 순간 pytest 가 멈춘다(실측 2026-09-28 — `test_car_fare.py` 가
  SystemExit 로 전체 수집을 멈췄다). 그런 파일은 건너뛰고 끝에 목록을 보여 준다.
  **CI 가 확인하게 하려면 `def test_...` 함수로 쓴다.**
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT, REPO_ROOT / "final_project_cs"):
    if str(_path) in sys.path:
        sys.path.remove(str(_path))
    sys.path.insert(0, str(_path))

_SCRIPT_STYLE: list[str] = []


def _is_sys_exit(node: ast.AST) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "exit"
            and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == "sys")


def _script_style(path: Path) -> bool:
    """pytest 로 모을 수 없는 파일 — 시험 함수가 없거나, 불러오는 순간 끝나 버린다."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return False            # 문법 오류는 숨기지 않는다 — pytest 가 오류로 보이게 둔다
    has_tests = any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and node.name.lower().startswith("test")
                    for node in tree.body)
    exits_on_import = any(_is_sys_exit(node) for node in tree.body)
    return not has_tests or exits_on_import


def pytest_ignore_collect(collection_path: Path, config):
    path = Path(collection_path)
    if path.suffix == ".py" and path.name.startswith("test_") and _script_style(path):
        _SCRIPT_STYLE.append(str(path.relative_to(REPO_ROOT)))
        return True
    return None


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if _SCRIPT_STYLE:
        terminalreporter.section("스크립트 방식이라 pytest 가 모으지 않은 파일")
        for name in sorted(set(_SCRIPT_STYLE)):
            terminalreporter.write_line(f"  {name}   (python {name} 로 직접 실행)")
        terminalreporter.write_line("  CI 가 확인하게 하려면 def test_... 함수로 바꾼다.")
