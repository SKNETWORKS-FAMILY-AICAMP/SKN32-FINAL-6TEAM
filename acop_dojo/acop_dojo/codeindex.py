"""대상 저장소의 코드 색인. 문제 생성기(quiz)가 정답을 뽑는 유일한 출처다.

정답은 구문 트리에서 기계로 뽑는다 — 누가 누구를 부르나, 어떤 조건에서 어떤 예외를 던지나.
언어 모델은 여기 끼지 않는다. 모델이 쓴 문장은 틀릴 수 있지만 구문 트리는 틀리지 않는다.

호출 관계는 이름으로 잇는다(정적 분석). 같은 이름의 함수가 둘 이상이면 어느 쪽을
부르는지 알 수 없으므로 그 이름은 호출 문제에서 뺀다 — 모르는 것을 정답으로 내지 않는다.
"""
from __future__ import annotations

import ast
import builtins
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import WORKSPACE_ROOT, target_root

INDEX_VERSION = "acop-codeindex/3"
#: 너무 짧은 함수는 문제로 쓸 거리가 없다(본문 문장 수 기준)
MIN_STATEMENTS = 2
#: 호출 관계로 믿지 않는 이름 — 내장 함수와 흔한 컨테이너·문자열 메서드.
#: `list(...)` 가 저장소의 `list` 메서드로 잘못 이어진 것이 실제로 있었다(2026-09-24).
GENERIC_NAMES = (set(dir(builtins)) | set(dir(dict)) | set(dir(list)) | set(dir(str)) | set(dir(set))
                 | {"get", "add", "run", "list", "update", "execute", "call", "send", "load", "save",
                    "read", "write", "close", "open", "items", "keys", "values", "create", "delete"})


@dataclass
class Guard:
    """`if 조건: raise 예외` 한 곳."""

    cond: str
    exc: str
    line: int


@dataclass
class Unit:
    uid: str                 # "app/core/transition.py::transition_case"
    path: str
    qualname: str
    name: str
    line: int
    signature: str
    doc: str
    source: str
    calls: list[str] = field(default_factory=list)
    guards: list[Guard] = field(default_factory=list)

    @property
    def layer(self) -> str:
        parts = self.path.split("/")
        return "/".join(parts[:2]) if len(parts) > 2 else self.path

    def text_for_embedding(self) -> str:
        return f"{self.path}\n{self.signature}\n{self.doc}\n{self.source[:1500]}"


def cache_dir() -> Path:
    return WORKSPACE_ROOT / ".acop_dojo" / "quiz"


def _exc_name(node: ast.Raise) -> str | None:
    exc = node.exc
    if exc is None:
        return None
    if isinstance(exc, ast.Call):
        exc = exc.func
    if isinstance(exc, ast.Name):
        return exc.id
    if isinstance(exc, ast.Attribute):
        return exc.attr
    return None


def _called_names(func: ast.AST, aliases: dict[str, str] | None = None) -> list[str]:
    """부르는 이름. `from x import a as b` 로 b(...) 를 부르면 a 도 부른 것으로 센다.

    별칭을 안 풀면 실제로 부르는 함수가 「안 부른다」로 잡혀 오답 보기에 들어간다
    (2026-09-24 코덱스 점검 — `open_case` 가 `idempotency_key` 를 별칭으로 부른다).
    """
    aliases = aliases or {}
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                names.add(target.id)
                if target.id in aliases:
                    names.add(aliases[target.id])
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return sorted(names)


def _guards(func: ast.AST) -> list[Guard]:
    out: list[Guard] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.If):
            continue
        # 몸통이 곧장 raise 인 검사만 쓴다 — 조건과 예외가 1:1 로 이어진다
        if len(node.body) == 1 and isinstance(node.body[0], ast.Raise) and not node.orelse:
            exc = _exc_name(node.body[0])
            if exc:
                out.append(Guard(cond=ast.unparse(node.test), exc=exc, line=node.lineno))
    return out


def _signature(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(func, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {func.name}({ast.unparse(func.args)})"


def _units_in(path: Path, rel: str) -> list[Unit]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    out: list[Unit] = []
    aliases = {a.asname: a.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               for a in node.names if a.asname}

    def visit(node: ast.AST, scope: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, scope + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = [s for s in child.body
                        if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
                if len(body) >= MIN_STATEMENTS or _guards(child):
                    qual = ".".join(scope + [child.name])
                    out.append(Unit(
                        uid=f"{rel}::{qual}", path=rel, qualname=qual, name=child.name,
                        line=child.lineno, signature=_signature(child),
                        doc=(ast.get_docstring(child) or "").strip().split("\n\n")[0],
                        source=ast.get_source_segment(text, child) or "",
                        calls=_called_names(child, aliases), guards=_guards(child)))
                # 안쪽 함수는 따로 세지 않는다(바깥 함수의 일부로 본다)

    visit(tree, [])
    return out


def _fingerprint(files: list[Path], root: Path) -> str:
    h = hashlib.sha1(INDEX_VERSION.encode())
    for p in files:
        st = p.stat()
        h.update(f"{p.relative_to(root).as_posix()}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


@dataclass
class Index:
    units: list[Unit]
    fingerprint: str
    root: str
    #: 파일마다 정의된 함수 이름 전부(짧은 함수 포함). 실행 기록이 낡았는지 볼 때 쓴다.
    defs: dict[str, list[str]] = field(default_factory=dict)

    def by_uid(self) -> dict[str, Unit]:
        return {u.uid: u for u in self.units}

    def unique_names(self) -> dict[str, Unit]:
        """이름이 저장소 전체(짧은 함수 포함)에서 하나뿐이고 흔한 이름이 아닌 함수. 호출 관계는 이것만 믿는다."""
        cached = getattr(self, "_unique", None)
        if cached is not None:
            return cached
        counts: dict[str, int] = {}
        for names in self.defs.values():
            for name in names:
                counts[name] = counts.get(name, 0) + 1
        seen: dict[str, list[Unit]] = {}
        for u in self.units:
            seen.setdefault(u.name, []).append(u)
        self._unique = {name: us[0] for name, us in seen.items()
                        if len(us) == 1 and counts.get(name, 1) == 1
                        and not name.startswith("__") and name not in GENERIC_NAMES}
        return self._unique

    def callers_of(self, unit: Unit) -> list[Unit]:
        if unit.name not in self.unique_names():
            return []
        return [u for u in self.units if u.uid != unit.uid and unit.name in u.calls]

    def callees_of(self, unit: Unit) -> list[Unit]:
        names = self.unique_names()
        return [names[n] for n in unit.calls if n in names and names[n].uid != unit.uid]


def build(root: Path | None = None, *, use_cache: bool = True) -> Index:
    root = (root or target_root()).resolve()
    app = root / "app"
    files = sorted(p for p in app.rglob("*.py") if "__pycache__" not in p.parts)
    fp = _fingerprint(files, root)
    cache = cache_dir() / "index.json"
    if use_cache and cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("fingerprint") == fp and data.get("root") == str(root):
                return Index(units=[_unit_from(d) for d in data["units"]], fingerprint=fp,
                             root=str(root), defs=data.get("defs", {}))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    units: list[Unit] = []
    defs: dict[str, list[str]] = {}
    for p in files:
        rel = p.relative_to(root).as_posix()
        try:
            units += _units_in(p, rel)
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # 겹치는 이름도 그대로 센다 — 한 파일에 같은 이름 메서드가 둘이면 둘이다
        defs[rel] = sorted(n.name for n in ast.walk(tree)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    index = Index(units=units, fingerprint=fp, root=str(root), defs=defs)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fingerprint": fp, "root": str(root), "defs": defs,
                                 "units": [asdict(u) for u in units]}, ensure_ascii=False),
                     encoding="utf-8")
    return index


def _unit_from(d: dict[str, Any]) -> Unit:
    guards = [Guard(**g) for g in d.pop("guards", [])]
    return Unit(**d, guards=guards)
