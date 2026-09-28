"""처음부터 쌓아 보는 모드 — 빈 폴더에서 베이스먼트를 한 층씩 만든다.

0~4단계(완주·복원·대조·결함·보스)는 **이미 있는 코드를 읽고 고치는** 쪽이다. 여기는 반대다.
`acop_basement/` 를 통째로 비운 작업 폴더에서 시작해, 한 단계에 모듈 몇 개씩 직접 만든다.
판정은 그 저장소의 **실제 테스트**가 한다 — 단계마다, 그때까지 만든 것만으로 돌 수 있는
테스트가 정해져 있다(`data/build_steps.json`, 빈 폴더에 실제로 만들어 돌려서 센 목록이다).

★대상이 `final_project_sample` 인 이유 — 코어가 `acop_basement/` 한 패키지에 모여 있고
  도메인(`app/`)이 그 바깥에 있다. cs 는 둘이 같은 `app/` 안에 섞여 있어 "빈 폴더에서
  코어만 쌓는다" 가 성립하지 않는다.

★참고 구현을 언제든 꺼내 볼 수 있다(`--reveal`). 다만 꺼내 본 파일은 기록에 남는다 —
  무엇을 직접 썼고 무엇을 베꼈는지 섞이면 자기 상태를 못 읽는다.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import BUILD_PACKAGE, build_target_root, build_workspace, data_dir
from .sandbox import RunResult

SEPARATOR = "─" * 62
STEPS_PATH = data_dir() / "build_steps.json"
#: 사본에 넣지 않는 것. `.pytest*` 는 권한이 막혀 복사 자체가 실패한다.
SKIP_NAMES = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules",
              "build", "dist", "var", "final_project_sample.egg-info"}


@dataclass(frozen=True)
class Step:
    index: int
    title: str
    why: str
    modules: tuple[str, ...]
    tests: tuple[str, ...]
    #: 이 단계가 지나면 학습자가 말로 설명할 수 있어야 하는 것
    claim: str
    #: 이 단계에서 비워 두었다가 채우는 패키지 __init__ (있으면)
    inits: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)

    def paths(self) -> list[str]:
        return [module_path(m) for m in self.modules] + [init_path(m) for m in self.inits]


def module_path(module: str) -> str:
    return f"{BUILD_PACKAGE}/" + module.replace(".", "/") + ".py"


def init_path(package: str) -> str:
    return f"{BUILD_PACKAGE}/" + package.replace(".", "/") + "/__init__.py"


def steps() -> list[Step]:
    raw = json.loads(STEPS_PATH.read_text(encoding="utf-8"))
    return [Step(index=i, title=s["title"], why=s["why"], claim=s["claim"],
                 modules=tuple(s["modules"]), tests=tuple(s["tests"]),
                 inits=tuple(s.get("inits", ())), notes=tuple(s.get("notes", ())))
            for i, s in enumerate(raw["steps"], start=1)]


def get(index: int) -> Step:
    all_steps = steps()
    if not 1 <= index <= len(all_steps):
        raise SystemExit(f"단계 번호는 1~{len(all_steps)} 중에서 고른다. 입력한 값: {index}")
    return all_steps[index - 1]


# ── 작업 폴더 ────────────────────────────────────────────────────────────────
def state_path() -> Path:
    return build_workspace().parent / "state.json"


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"prepared_at": None, "steps": {}, "revealed": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"prepared_at": None, "steps": {}, "revealed": []}


def save_state(state: dict[str, Any]) -> Path:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                    encoding="utf-8", newline="\n")
    return path


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {n for n in names
            if n in SKIP_NAMES or n.endswith(".pyc") or n.startswith(".pytest")}


def prepare(*, force: bool = False) -> tuple[Path, list[str]]:
    """대상 저장소를 통째로 복사한 뒤, 단계에 나오는 모듈을 **전부 지운다.**

    지우는 것은 `acop_basement/` 안뿐이다. `app/`(도메인 모듈)·`tests/`·`config/` 는 그대로 둔다 —
    베이스먼트는 그것들을 모시는 층이라, 모실 대상이 없으면 무엇을 만드는지 알 수 없다.
    """
    workspace = build_workspace()
    if workspace.exists() and not force:
        raise SystemExit(f"작업 폴더가 이미 있다: {workspace}\n처음부터 다시 시작하려면 --force를 사용한다. "
                         f"직접 작성한 코드는 지워진다.")
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(build_target_root(), workspace, ignore=_ignore, symlinks=False)

    emptied: list[str] = []
    for step in steps():
        for rel in step.paths():
            target = workspace / rel
            if not target.exists():
                continue
            if target.name == "__init__.py":
                target.write_text("", encoding="utf-8")  # 패키지 자리는 남긴다
            else:
                target.unlink()
            emptied.append(rel)
    return workspace, emptied


def written(step: Step) -> list[str]:
    """이 단계 파일 중 작업 폴더에 실제로 내용이 들어 있는 것."""
    workspace = build_workspace()
    done = []
    for rel in step.paths():
        path = workspace / rel
        if path.exists() and path.read_text(encoding="utf-8", errors="replace").strip():
            done.append(rel)
    return done


# ── 명세 뽑기 ────────────────────────────────────────────────────────────────
def spec(rel_path: str) -> dict[str, Any]:
    """참고 구현에서 **이름과 서명만** 뽑는다. 본문은 주지 않는다.

    테스트가 import 하는 이름을 모르면 시작할 수 없다. 그렇다고 본문을 보여 주면
    베끼는 연습이 된다 — 그 사이가 이 함수다.
    """
    source = build_target_root() / rel_path
    if not source.exists():
        return {"path": rel_path, "missing": True}
    tree = ast.parse(source.read_text(encoding="utf-8"))
    doc = (ast.get_docstring(tree) or "").strip().splitlines()
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(f"def {node.name}({ast.unparse(node.args)})")
        elif isinstance(node, ast.ClassDef):
            members = [f"{m.name}()" for m in node.body
                       if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and not m.name.startswith("_")]
            fields = [t.target.id for t in node.body if isinstance(t, ast.AnnAssign)
                      and isinstance(t.target, ast.Name)]
            # ★Enum 은 값이 곧 계약이다. 이름만 주면 상태를 몇 개 만들어야 하는지도 모른다.
            values = [f"{t.targets[0].id}={ast.unparse(t.value)}" for t in node.body
                      if isinstance(t, ast.Assign) and len(t.targets) == 1
                      and isinstance(t.targets[0], ast.Name) and isinstance(t.value, ast.Constant)]
            bases = [ast.unparse(b) for b in node.bases]
            names.append(f"class {node.name}" + (f"({', '.join(bases)})" if bases else "")
                         + (f"  값: {', '.join(values)}" if values else "")
                         + (f"  필드: {', '.join(fields)}" if fields else "")
                         + (f"  메서드: {', '.join(members)}" if members else ""))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    names.append(f"{target.id} = …")
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                names.append(f"{node.target.id}: {ast.unparse(node.annotation)} = …")
    imports = sorted({n.split(".")[0] + "." + ".".join(n.split(".")[1:3])
                      for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                      for n in [node.module or ""] if n.startswith(BUILD_PACKAGE)})
    return {"path": rel_path, "summary": doc[0] if doc else "", "names": names,
            "imports": imports, "lines": len(source.read_text(encoding="utf-8").splitlines())}


# ── 판정 ─────────────────────────────────────────────────────────────────────
def run_tests(selection: list[str], *, timeout: int = 600) -> RunResult:
    workspace = build_workspace()
    args = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
            "--tb=short", "-rfE", *selection]
    try:
        proc = subprocess.run(args, cwd=workspace, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        # ★끝나지 않는 테스트가 실제로 있다(2026-09-16 sample 실측). 예외로 죽지 말고 결과로 말한다.
        return RunResult(124, sorted(selection),
                         f"{timeout}초 안에 테스트가 끝나지 않아 판정하지 못했다.", "")
    failed = []
    for line in proc.stdout.splitlines():
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            failed.append(line.split(" ", 1)[1].split(" - ")[0].strip())
    summary = ""
    for line in reversed(proc.stdout.splitlines()):
        if " passed" in line or " failed" in line or " error" in line:
            summary = line.strip()
            break
    return RunResult(proc.returncode, sorted(set(failed)), summary, proc.stdout)


def database_endpoint() -> tuple[str, int] | None:
    """작업 폴더 `.env` 의 ACOP_DATABASE_URL 에서 **호스트와 포트만** 읽는다. 비밀값은 안 꺼낸다."""
    import os
    import re

    text = os.environ.get("ACOP_DATABASE_URL", "")
    env = build_workspace() / ".env"
    if not text and env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("ACOP_DATABASE_URL="):
                text = line.split("=", 1)[1].strip()
                break
    matched = re.search(r"@([^:/@]+):(\d+)", text)
    return (matched.group(1), int(matched.group(2))) if matched else None


def database_reachable(timeout: float = 3.0) -> bool | None:
    """DB 포트에 붙어 본다. 주소를 못 찾으면 None(모름)이다.

    ★2026-09-17 — PostgreSQL 이 꺼져 있으니 DB 테스트가 하나에 130초씩 기다리다 실패했고,
      그걸 "테스트가 끝나지 않는다" 로 오진했다. 판정 전에 3초로 먼저 묻는다.
    """
    import socket

    endpoint = database_endpoint()
    if endpoint is None:
        return None
    try:
        with socket.create_connection(endpoint, timeout=timeout):
            return True
    except OSError:
        return False


def check(step: Step) -> tuple[bool, RunResult]:
    result = run_tests(list(step.tests))
    return (not result.failed and result.returncode == 0), result


def record(step: Step, *, passed: bool, result: RunResult) -> dict[str, Any]:
    state = load_state()
    entry = state["steps"].setdefault(str(step.index), {"attempts": 0})
    entry["attempts"] += 1
    entry["status"] = "passed" if passed else "in_progress"
    entry["summary"] = result.summary
    entry["failed"] = result.failed[:8]
    entry["wrote"] = written(step)
    save_state(state)
    return state


def reveal(step: Step, rel_path: str) -> Path:
    """참고 구현을 작업 폴더로 꺼낸다. 꺼낸 사실을 기록에 남긴다."""
    if rel_path not in step.paths():
        raise SystemExit(f"{step.index}단계에서 만들 파일이 아니다: {rel_path}\n"
                         f"이 단계에서 만들 파일: {', '.join(step.paths())}")
    source = build_target_root() / rel_path
    target = build_workspace() / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    state = load_state()
    if rel_path not in state["revealed"]:
        state["revealed"].append(rel_path)
        save_state(state)
    return target


# ── 힌트 세 단계 ──────────────────────────────────────────────────────────────
# 쌓기는 코드를 쓰는 문제라 보기(4지선다)가 맞지 않는다. 대신 한 단계씩 더 알려 준다.
#   1  판정 테스트가 무엇을 불러오는가 — 그 이름을 만들면 불러오기는 된다
#   2  참고 구현의 함수·클래스가 각각 무슨 일을 하는가(설명 첫 줄)
#   3  뼈대 — 서명과 설명만 있고 본문은 NotImplementedError 인 파일
# 쓴 힌트는 기록한다. 뼈대는 학습자가 이미 쓴 파일을 덮지 않는다.
HINT_TIERS = 3


def _imports_from_tests(step: "Step") -> dict[str, list[str]]:
    """판정 테스트가 이 단계 모듈에서 불러오는 이름. 테스트 파일을 AST 로 읽는다."""
    wanted = {f"{BUILD_PACKAGE}." + m for m in step.modules}
    found: dict[str, set[str]] = {}
    for test in step.tests:
        path = build_target_root() / test
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in wanted:
                found.setdefault(node.module, set()).update(a.name for a in node.names)
    return {k: sorted(v) for k, v in sorted(found.items())}


def _first_line(node: ast.AST) -> str:
    doc = ast.get_docstring(node) or ""
    return doc.strip().splitlines()[0] if doc.strip() else "(설명 없음)"


def _explain(rel_path: str) -> list[str]:
    source = build_target_root() / rel_path
    if not source.exists():
        return []
    tree = ast.parse(source.read_text(encoding="utf-8"))
    lines = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_") and not isinstance(node, ast.ClassDef):
                continue
            lines.append(f"{node.name} — {_first_line(node)}")
    return lines


def skeleton(rel_path: str) -> str:
    """참고 구현에서 본문을 걷어낸 뼈대. 서명·설명·Enum 값·import 는 남긴다."""
    source = (build_target_root() / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)

    class Hollow(ast.NodeTransformer):
        def _hollow(self, node):
            doc = ast.get_docstring(node)
            body = [ast.Expr(ast.Constant(doc))] if doc else []
            body.append(ast.Raise(exc=ast.Call(ast.Name("NotImplementedError", ast.Load()),
                                               [ast.Constant("여기를 채운다")], [])))
            node.body = body
            return node

        def visit_FunctionDef(self, node):
            return self._hollow(node)

        def visit_AsyncFunctionDef(self, node):
            return self._hollow(node)

    hollow = Hollow().visit(tree)
    # 모듈 수준의 큰 표(전이표처럼 문제의 알맹이인 것)는 비운다. 이름과 타입만 남긴다.
    for node in hollow.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(
                getattr(node, "value", None), (ast.Dict, ast.List, ast.Set, ast.Tuple)):
            value = node.value
            node.value = type(value)(**{f: [] for f in value._fields
                                        if f in ("keys", "values", "elts")},
                                     **({"ctx": ast.Load()} if "ctx" in value._fields else {}))
    ast.fix_missing_locations(hollow)
    return ("# 뼈대 — 서명과 설명만 남겼다. `raise NotImplementedError` 자리를 채운다.\n"
            "# 비워 둔 표({} · [])는 테스트가 무엇을 기대하는지 보고 채운다.\n\n"
            + ast.unparse(hollow) + "\n")


def next_hint(step: "Step") -> tuple[int, list[str]]:
    """다음 힌트를 연다. (몇 번째 힌트인가, 보여 줄 줄들)"""
    state = load_state()
    entry = state["steps"].setdefault(str(step.index), {"attempts": 0})
    tier = entry.get("hints_used", 0) + 1
    if tier > HINT_TIERS:
        return HINT_TIERS + 1, ["힌트 세 단계를 모두 확인했다. 더 막히면 `build reveal`로 참고 구현을 확인한다."]
    out: list[str] = []
    if tier == 1:
        imports = _imports_from_tests(step)
        if not imports:
            out.append("판정 테스트는 이 단계 모듈을 직접 호출하지 않고 앞 단계 모듈과 함께 호출한다.")
        for module, names in imports.items():
            out.append(f"{module.replace('.', '/')}.py에서 테스트가 불러오는 이름: {', '.join(names)}")
        out.append("먼저 위 이름을 정의한다. 그다음 테스트에서 각 이름에 기대하는 동작을 확인한다.")
    elif tier == 2:
        for rel in step.paths():
            explained = _explain(rel)
            if explained:
                out.append(rel)
                out.extend(f"    {line}" for line in explained)
    else:
        for rel in step.paths():
            source = build_target_root() / rel
            if not source.exists() or rel.endswith("__init__.py"):
                continue
            target = build_workspace() / rel
            text = skeleton(rel)
            if target.exists() and target.read_text(encoding="utf-8", errors="replace").strip():
                hint_path = target.with_suffix(".skeleton.py")
                hint_path.write_text(text, encoding="utf-8")
                out.append(f"{rel}은 이미 작성한 내용이 있어 덮어쓰지 않았다. 뼈대는 {hint_path.name}에 따로 저장했다.")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                out.append(f"{rel}에 뼈대를 넣었다. 비어 있는 본문을 채운다.")
    entry["hints_used"] = tier
    save_state(state)
    return tier, out
