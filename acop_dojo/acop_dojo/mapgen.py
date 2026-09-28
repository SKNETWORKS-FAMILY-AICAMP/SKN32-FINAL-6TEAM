"""웹 지도를 만든다.

지도는 엔진이 아니라 거울이다. CLI 가 남긴 진행 파일과 실측 트레이스만 읽고,
스스로 판정하지 않는다. 그래야 코드와 어긋나 거짓말할 여지가 없다.

간선을 두 종류로 나눠 그린다. 정적 import 는 실제로 무엇을 부르는지 말해 주지 않는다 —
이 저장소는 composition.py 가 importlib 로 Team 을 동적으로 읽어 조립하기 때문에
import 만 보면 그 결합이 지도에서 사라진다.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

LAYERS = [
    ("presentation", "app/presentation"),
    ("application", "app/application"),
    ("core", "app/core"),
    ("domain", "app/domain"),
    ("infrastructure", "app/infrastructure"),
    ("modules", "app/modules"),
]
OTHER = "기타"


def module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.endswith("/__init__.py"):
        rel = rel[: -len("/__init__.py")]
    elif rel.endswith(".py"):
        rel = rel[:-3]
    return rel.replace("/", ".")


def static_imports(target: Path) -> dict[str, set[str]]:
    """AST 로 import 간선을 센다."""
    edges: dict[str, set[str]] = defaultdict(set)
    for path in (target / "app").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        source = module_name(path, target)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                edges[source].add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("app"):
                        edges[source].add(alias.name)
    return edges


def trace_module(path: str) -> str:
    """패키지 초기화 파일도 AST 지도와 같은 모듈 이름으로 읽는다."""
    suffix = "/__init__.py"
    return (path[:-len(suffix)] if path.endswith(suffix) else path[:-3]).replace("/", ".")


def runtime_calls(trace: dict[str, Any]) -> Counter:
    """실측 호출 간선. 연속 순서가 아니라 실제 호출자를 쓴다."""
    symbol_module = {}
    for step in trace.get("steps", []):
        symbol_module[step["symbol"]] = trace_module(step["path"])
    counts: Counter = Counter()
    for step in trace.get("steps", []):
        caller = step.get("caller")
        callee_module = trace_module(step["path"])
        caller_module = symbol_module.get(caller) if caller else None
        if caller_module and caller_module != callee_module:
            counts[(caller_module, callee_module)] += 1
    return counts


def layer_of(module: str) -> str:
    path = module.replace(".", "/")
    for name, prefix in LAYERS:
        if path.startswith(prefix):
            return name
    return OTHER


def layout(modules: set[str]) -> tuple[dict[str, tuple[float, float]], list[str], dict[str, list[str]], float]:
    columns: dict[str, list[str]] = defaultdict(list)
    for module in sorted(modules):
        columns[layer_of(module)].append(module)
    order = [name for name, _ in LAYERS if columns[name]] + ([OTHER] if columns[OTHER] else [])
    positions: dict[str, tuple[float, float]] = {}
    step_x = (WIDTH - NODE_W - 40) / max(len(order) - 1, 1)
    for index, layer in enumerate(order):
        x = 20 + index * step_x
        for row, module in enumerate(columns[layer]):
            positions[module] = (x, TOP + row * GAP_Y)
    height = TOP + max(len(columns[layer]) for layer in order) * GAP_Y + 40
    return positions, order, columns, height


WIDTH, NODE_W, NODE_H, GAP_Y, TOP = 1180, 168, 26, 32, 64


def _edge(positions, a: str, b: str, klass: str, weight: int = 1) -> str:
    if a not in positions or b not in positions:
        return ""
    x1, y1 = positions[a]
    x2, y2 = positions[b]
    x1 += NODE_W
    y1 += NODE_H / 2
    y2 += NODE_H / 2
    mid = (x1 + x2) / 2
    stroke = min(1 + weight * 0.35, 4)
    return (f'<path class="{klass}" d="M{x1:.0f} {y1:.0f} C{mid:.0f} {y1:.0f} '
            f'{mid:.0f} {y2:.0f} {x2:.0f} {y2:.0f}" stroke-width="{stroke:.1f}"/>')


def measured_order(trace: dict[str, Any] | None) -> list[str]:
    """실측 모듈 순서. 연속 중복만 묶고 재방문은 남긴다."""
    order: list[str] = []
    for step in (trace or {}).get('steps', []):
        module = trace_module(step['path'])
        if not order or order[-1] != module:
            order.append(module)
    return order


def snapshot(track_id: str, scenario_id: str) -> dict[str, Any]:
    from .map_ui import snapshot as collect
    return collect(track_id, scenario_id)


def build(target: Path, trace: dict[str, Any] | None, progress: dict[str, Any],
          track: Any = None, *, context: dict[str, Any] | None = None) -> str:
    from .map_ui import render
    return render(target, trace, progress, track, context=context)
