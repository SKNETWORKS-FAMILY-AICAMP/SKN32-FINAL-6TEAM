"""대상 저장소의 코드 색인. 문제 생성기(quiz)가 정답을 뽑는 유일한 출처다.

정답은 구문 트리에서 기계로 뽑는다 — 누가 누구를 부르나, 어떤 조건에서 어떤 예외를 던지나.
언어 모델은 여기 끼지 않는다. 모델이 쓴 문장은 틀릴 수 있지만 구문 트리는 틀리지 않는다.

호출 관계는 이름이 아니라 **어느 함수인지 풀 수 있는 것만** 믿는다(2026-09-24 코덱스 재점검 뒤).
  · `f(...)`            같은 모듈에 정의됐거나 `from app... import f [as g]` 로 가져온 f
  · `self.m(...)`       같은 클래스의 메서드 m
  · `mod.f(...)`        `import app.x as mod` · `from app import x` 로 가져온 모듈의 f
이름만 같은 외부 호출(`response.json()` 이 저장소의 `json` 메서드로 이어지던 것)은 믿지 않는다.
안쪽 함수 본문의 호출은 바깥 함수의 직접 호출이 아니다 — 정의만 하고 나중에 부른다.

오답을 고를 때는 반대로 넓게 본다. 이름이 한 번이라도 불린 함수(`mentions`)는 오답에서 뺀다 —
못 푼 호출이 사실은 그 함수일 수 있으므로, 정답이 둘이 되는 것보다 오답 후보가 주는 편이 낫다.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import WORKSPACE_ROOT, target_root

INDEX_VERSION = "acop-codeindex/4"
#: 너무 짧은 함수는 문제로 쓸 거리가 없다(본문 문장 수 기준)
MIN_STATEMENTS = 2


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
    #: 풀 수 있는 직접 호출(안쪽 함수 제외) — ["L", 이름] · ["S", 메서드] · ["M", 모듈별칭, 이름]
    refs: list[list[str]] = field(default_factory=list)
    #: 이 함수(안쪽 함수 포함) 안에서 불린 이름 전부. 오답에서 빼는 데 쓴다
    mentions: list[str] = field(default_factory=list)
    guards: list[Guard] = field(default_factory=list)

    @property
    def cls(self) -> str | None:
        return self.qualname.rsplit(".", 1)[0] if "." in self.qualname else None

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


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _direct_nodes(func: ast.AST):
    """func 본문의 노드. 안쪽 함수·람다·클래스 본문으로는 들어가지 않는다."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, _SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _refs(func: ast.AST) -> list[list[str]]:
    out: set[tuple[str, ...]] = set()
    for node in _direct_nodes(func):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name):
            out.add(("L", f.id))
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if f.value.id in ("self", "cls"):
                out.add(("S", f.attr))
            else:
                out.add(("M", f.value.id, f.attr))
    return [list(r) for r in sorted(out)]


def _mentions(func: ast.AST) -> list[str]:
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return sorted(names)


def _guards(func: ast.AST) -> list[Guard]:
    out: list[Guard] = []
    for node in _direct_nodes(func):
        if not isinstance(node, ast.If):
            continue
        # 몸통이 곧장 raise 인 검사만 쓴다 — 조건과 예외가 1:1 로 이어진다
        if len(node.body) == 1 and isinstance(node.body[0], ast.Raise) and not node.orelse:
            exc = _exc_name(node.body[0])
            if exc:
                out.append(Guard(cond=ast.unparse(node.test), exc=exc, line=node.lineno))
    return sorted(out, key=lambda g: g.line)


def _signature(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(func, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {func.name}({ast.unparse(func.args)})"


def _module_path(module: str, rel: str, level: int, root: Path) -> str | None:
    """import 문의 모듈 이름을 저장소 안 파일 경로로. 저장소 밖이면 None."""
    if level:
        base = Path(rel).parent
        for _ in range(level - 1):
            base = base.parent
        parts = list(base.parts) + (module.split(".") if module else [])
    else:
        parts = module.split(".") if module else []
    if not parts or parts[0] != "app":
        return None
    as_file = "/".join(parts) + ".py"
    as_pkg = "/".join(parts) + "/__init__.py"
    if (root / as_file).exists():
        return as_file
    if (root / as_pkg).exists():
        return as_pkg
    return None


@dataclass
class FileTable:
    """파일 하나의 이름표 — 이 파일에서 이름이 무엇을 가리키나."""

    top: list[str] = field(default_factory=list)                       # 최상위 함수·클래스 이름
    methods: dict[str, list[str]] = field(default_factory=dict)       # 클래스 → 메서드
    imported: dict[str, list[str]] = field(default_factory=dict)      # 로컬 이름 → [모듈 경로, 원래 이름]
    modules: dict[str, str] = field(default_factory=dict)             # 로컬 이름 → 모듈 경로
    all_defs: list[str] = field(default_factory=list)                 # 짧은 것·안쪽 것 포함 모든 def 이름


def _table(tree: ast.Module, rel: str, root: Path) -> FileTable:
    t = FileTable()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            t.top.append(node.name)
        if isinstance(node, ast.ClassDef):
            t.methods[node.name] = [n.name for n in node.body
                                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            mod = _module_path(base, rel, node.level, root)
            for a in node.names:
                local = a.asname or a.name
                sub = _module_path(f"{base}.{a.name}" if base else a.name, rel, node.level, root)
                if sub:
                    t.modules[local] = sub
                elif mod:
                    t.imported[local] = [mod, a.name]
        elif isinstance(node, ast.Import):
            for a in node.names:
                mod = _module_path(a.name, rel, 0, root)
                if mod and a.asname:
                    t.modules[a.asname] = mod
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            t.all_defs.append(node.name)
    return t


def _units_in(text: str, tree: ast.Module, rel: str) -> list[Unit]:
    out: list[Unit] = []

    def visit(node: ast.AST, scope: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef) and not scope:
                visit(child, [child.name])
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
                        refs=_refs(child), mentions=_mentions(child), guards=_guards(child)))
                # 안쪽 함수는 따로 세지 않는다(바깥 함수의 일부로 본다)

    visit(tree, [])
    return out


def _fingerprint(files: list[Path], root: Path) -> str:
    """내용 해시. 크기·수정 시각만 보면 같은 길이로 바뀐 파일을 놓친다."""
    h = hashlib.sha1(INDEX_VERSION.encode())
    for p in files:
        h.update(p.relative_to(root).as_posix().encode())
        h.update(hashlib.sha1(p.read_bytes()).digest())
    return h.hexdigest()


@dataclass
class Index:
    units: list[Unit]
    fingerprint: str
    root: str
    tables: dict[str, FileTable] = field(default_factory=dict)

    def by_uid(self) -> dict[str, Unit]:
        cached = getattr(self, "_by_uid", None)
        if cached is None:
            cached = self._by_uid = {u.uid: u for u in self.units}
        return cached

    def defs(self, path: str) -> list[str]:
        table = self.tables.get(path)
        return table.all_defs if table else []

    # ── 호출 풀기 ────────────────────────────────────────────────────────
    def _resolve_name(self, path: str, name: str, depth: int = 0) -> str | None:
        """path 파일에서 name 이 가리키는 함수 uid. 다시 내보낸 이름은 세 번까지 따라간다."""
        table = self.tables.get(path)
        if table is None or depth > 3:
            return None
        if name in table.top:
            uid = f"{path}::{name}"
            return uid if uid in self.by_uid() else None
        if name in table.imported:
            mod, original = table.imported[name]
            return self._resolve_name(mod, original, depth + 1)
        return None

    def resolve(self, unit: Unit, ref: list[str]) -> str | None:
        kind = ref[0]
        if kind == "L":
            return self._resolve_name(unit.path, ref[1])
        if kind == "S":
            cls = unit.cls
            table = self.tables.get(unit.path)
            if cls and table and ref[1] in table.methods.get(cls, []):
                uid = f"{unit.path}::{cls}.{ref[1]}"
                return uid if uid in self.by_uid() else None
            return None
        if kind == "M":
            table = self.tables.get(unit.path)
            if table and ref[1] in table.modules:
                return self._resolve_name(table.modules[ref[1]], ref[2])
        return None

    def callees_of(self, unit: Unit) -> list[Unit]:
        seen: dict[str, Unit] = {}
        for ref in unit.refs:
            uid = self.resolve(unit, ref)
            if uid and uid != unit.uid:
                seen[uid] = self.by_uid()[uid]
        return list(seen.values())

    def callers_of(self, unit: Unit) -> list[Unit]:
        cached = getattr(self, "_callers", None)
        if cached is None:
            cached = {}
            for u in self.units:
                for callee in self.callees_of(u):
                    cached.setdefault(callee.uid, []).append(u)
            self._callers = cached
        return list(cached.get(unit.uid, []))


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
                return Index(units=[_unit_from(d) for d in data["units"]], fingerprint=fp, root=str(root),
                             tables={k: FileTable(**v) for k, v in data["tables"].items()})
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    units: list[Unit] = []
    tables: dict[str, FileTable] = {}
    for p in files:
        rel = p.relative_to(root).as_posix()
        try:
            text = p.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError):
            continue
        tables[rel] = _table(tree, rel, root)
        units += _units_in(text, tree, rel)
    index = Index(units=units, fingerprint=fp, root=str(root), tables=tables)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"fingerprint": fp, "root": str(root),
                                 "tables": {k: asdict(v) for k, v in tables.items()},
                                 "units": [asdict(u) for u in units]}, ensure_ascii=False),
                     encoding="utf-8")
    return index


def _unit_from(d: dict[str, Any]) -> Unit:
    guards = [Guard(**g) for g in d.pop("guards", [])]
    return Unit(**d, guards=guards)
