"""웹 지도를 만든다.

지도는 엔진이 아니라 거울이다. CLI 가 남긴 진행 파일과 실측 트레이스만 읽고,
스스로 판정하지 않는다. 그래야 코드와 어긋나 거짓말할 여지가 없다.

간선을 두 종류로 나눠 그린다. 정적 import 는 실제로 무엇을 부르는지 말해 주지 않는다 —
이 저장소는 composition.py 가 importlib 로 Team 을 동적으로 읽어 조립하기 때문에
import 만 보면 그 결합이 지도에서 사라진다.
"""
from __future__ import annotations

import ast
import html
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


def runtime_calls(trace: dict[str, Any]) -> Counter:
    """실측 호출 간선. 연속 순서가 아니라 실제 호출자를 쓴다."""
    symbol_module = {}
    for step in trace.get("steps", []):
        symbol_module[step["symbol"]] = step["path"][:-3].replace("/", ".")
    counts: Counter = Counter()
    for step in trace.get("steps", []):
        caller = step.get("caller")
        callee_module = step["path"][:-3].replace("/", ".")
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


def build(target: Path, trace: dict[str, Any] | None, progress: dict[str, Any],
          track: Any = None) -> str:
    imports = static_imports(target)
    modules = set(imports) | {m for targets in imports.values() for m in targets}
    indegree: Counter = Counter()
    for sources in imports.values():
        for module in sources:
            indegree[module] += 1
    calls = runtime_calls(trace) if trace else Counter()
    visited = {entry.split("::")[0][:-3].replace("/", ".")
               for entry in progress.get("discovered", [])}
    positions, order, columns, height = layout(modules)

    parts = []
    for source, targets in imports.items():
        for destination in targets:
            parts.append(_edge(positions, source, destination, "imp"))
    for (source, destination), weight in calls.items():
        parts.append(_edge(positions, source, destination, "run", weight))
    for layer in order:
        x, _ = positions[columns[layer][0]]
        parts.append(f'<text class="lyr" x="{x:.0f}" y="{TOP - 18:.0f}">{html.escape(layer)}</text>')
    for module in sorted(modules):
        x, y = positions[module]
        klass = "seen" if module in visited else "unseen"
        # 트랙이 있으면 내 담당이 아닌 것은 흐리게 둔다. 남의 디렉터리는 배울 대상이 아니다.
        if track is not None and track.owns:
            from . import tracks as tracks_mod
            if not tracks_mod.owns(track, module.replace(".", "/") + ".py") and \
                    not tracks_mod.owns(track, module.replace(".", "/") + "/"):
                klass += " other"
        label = module.replace("app.", "")
        count = indegree[module]
        badge = (f'<text class="deg" x="{x + NODE_W - 8:.0f}" y="{y + 17:.0f}">{count}</text>'
                 if count else "")
        parts.append(
            f'<g class="n {klass}"><rect x="{x:.0f}" y="{y:.0f}" width="{NODE_W}" '
            f'height="{NODE_H}" rx="5"/>'
            f'<text x="{x + 8:.0f}" y="{y + 17:.0f}">{html.escape(label[:26])}</text>{badge}</g>')

    stages = progress.get("stages", {})
    done = ", ".join(f"{k}단계 {v.get('status')}" for k, v in sorted(stages.items())) or "아직 없음"
    rows = "".join(
        f"<li>{html.escape(name)} — {'확정' if info['state'] == 'confirmed' else '잠정'}"
        f" <span class='ev'>{html.escape(info['evidence'])}</span></li>"
        for name, info in sorted(progress.get("abilities", {}).items())) or "<li>아직 없음</li>"
    import_count = sum(len(v) for v in imports.values())
    return TEMPLATE.format(
        width=WIDTH, height=f"{height:.0f}", body="".join(parts), modules=len(modules),
        imports=import_count, calls=len(calls), visited=len(visited), done=html.escape(done),
        rows=rows, track_title=track.title if track is not None else "전체")


TEMPLATE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A-COP 지식 지도</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#8a8a8a;--line:#e2e2e2;--seen:#e8f0fe;--seenb:#4a7fd4;--run:#c96a12}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1c1c1c;--fg:#e8e8e8;--mut:#909090;--line:#3a3a3a;--seen:#1e3050;--seenb:#5a8fe4;--run:#e08a3a}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px;background:var(--bg);color:var(--fg);
font:15px/1.7 -apple-system,"Segoe UI",system-ui,sans-serif}}
h1{{font-size:20px;font-weight:500;margin:0 0 4px}}
p.sub{{color:var(--mut);margin:0 0 20px}}
.wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;padding:8px}}
svg{{display:block}}
.lyr{{fill:var(--mut);font-size:12px}}
.n rect{{fill:none;stroke:var(--line)}}
.n text{{fill:var(--mut);font-size:11px;font-family:ui-monospace,Consolas,monospace}}
.n.seen rect{{fill:var(--seen);stroke:var(--seenb)}}
.n.seen text{{fill:var(--fg)}}
.n.other{{opacity:.28}}
.deg{{text-anchor:end;font-size:10px}}
path{{fill:none}}
path.imp{{stroke:var(--line)}}
path.run{{stroke:var(--run);opacity:.85}}
.legend{{display:flex;gap:20px;flex-wrap:wrap;margin:14px 0 0;color:var(--mut);font-size:13px}}
.sw{{display:inline-block;width:26px;height:0;border-top:2px solid;vertical-align:middle;margin-right:6px}}
ul{{margin:6px 0 0;padding-left:20px}}
.ev{{color:var(--mut);font-family:ui-monospace,Consolas,monospace;font-size:12px}}
footer{{margin-top:24px;color:var(--mut);font-size:13px}}
code{{font-family:ui-monospace,Consolas,monospace}}
</style></head><body>
<h1>A-COP 지식 지도 — {track_title}</h1>
<p class="sub">모듈 {modules}개 · 정적 import 간선 {imports}개 · 실측 호출 간선 {calls}개 ·
지나간 모듈 {visited}개</p>
<div class="wrap"><svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">
{body}
</svg></div>
<div class="legend">
<span><span class="sw" style="border-color:var(--line)"></span>정적 import</span>
<span><span class="sw" style="border-color:var(--run)"></span>실측 호출</span>
<span>칠해진 칸 = 트레이스가 실제로 지나간 모듈</span>
<span>흐린 칸 = 이 트랙의 담당이 아닌 모듈</span>
<span>오른쪽 숫자 = 이 모듈을 import 하는 곳의 수</span>
</div>
<footer>
<div>진행: {done}</div>
<div>능력</div><ul>{rows}</ul>
<div style="margin-top:10px">이 문서는 CLI 가 남긴 진행 파일과 실측 트레이스만 읽어 그린다.
정적 import 는 <code>composition.py</code> 가 importlib 로 만드는 결합을 보여주지 못한다.</div>
</footer>
</body></html>
"""
