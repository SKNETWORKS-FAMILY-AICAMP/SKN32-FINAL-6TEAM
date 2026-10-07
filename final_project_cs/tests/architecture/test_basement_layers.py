# -*- coding: utf-8 -*-
"""basement 네 층(core · application · infrastructure · presentation)이 **서로 어느 방향으로 부르는가**. `[2026-10-07]`

기존 `test_basement_is_domain_free.py` 는 basement 에 **도메인 낱말**이 없는지만 본다. 층끼리 누가 누구를 부르는지(방향)는 검사하는 시험이 없어,
2026-10-07 점검에서 이런 것이 있었다: 응용(`classification.py`) · 인프라(`repository.py`) · 도메인(`feedback.py`)이 코어의 가림 함수(`masked`)를
**표현 층 파일(`presentation/security.py`)이 다시 내보낸 것**을 거쳐 가져다 쓰고 있었다(코어 함수인데 표현 층에 의존하는 모양).

방향(부르는 쪽 → 불리는 쪽). 안쪽일수록 아는 것이 적다:

    core            → (아무도 안 부른다)                       ★ 0 — 코어는 다른 폴더를 몰라야 한다
    application     → core                                      인프라 · 표현 · 도메인은 몰라야 한다(아래 예외)
    infrastructure  → core                                      응용 · 표현 · 도메인은 몰라야 한다
    presentation    → core · application · infrastructure       도메인은 몰라야 한다(조립은 `composition` 이 한다)
    domains         → core · application · infrastructure       표현은 몰라야 한다(아래 예외)
    루트 파일(`composition.py` …) → 전부                        조립 루트다

★상한이 0 이 아닌 곳은 **그날 수를 박았다** — 늘면 실패하고, 줄이면 상한도 같이 내린다(내리지 않으면 실패한다). 목록은 실패 메시지에 나온다.

재현:

    python -m pytest tests/architecture/test_basement_layers.py -v
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path("app")
BASEMENT = ("core", "application", "infrastructure", "presentation")
ROOT_FILES = {"composition", "entrypoint", "composer_host", "main"}

#: (이름, 부르는 층들, 불리는 층들, 상한, 이유)
RULES = [
    ("core → 다른 폴더", ("core",), ("application", "infrastructure", "presentation", "domains", "(루트)"), 0, "코어는 다른 폴더를 몰라야 한다"),
    ("basement → 도메인", BASEMENT, ("domains",), 0, "도메인은 도메인 자리에만 산다(낱말 시험의 import 판)"),
    ("infrastructure → 응용 · 표현", ("infrastructure",), ("application", "presentation"), 0,
     "인프라는 코어의 계약만 안다 — 2026-10-07 `repository.py` 가 표현 층을 거치던 것을 코어 직접 import 로 고쳤다"),
    ("application → 표현", ("application",), ("presentation",), 0,
     "응용이 표현을 알면 HTTP 를 몰라야 하는 흐름이 HTTP 에 묶인다 — 2026-10-07 `classification.py` 를 고쳤다"),
    ("presentation → 도메인", ("presentation",), ("domains",), 0, "표현은 도메인을 직접 모른다 — 조립 루트가 꽂는다"),
    # ── 알고 있는 예외(이유와 함께) ───────────────────────────────
    ("application → infrastructure", ("application",), ("infrastructure",), 3,
     "`controller.py` 의 늦은 기본값(연결 팩토리 · 검색기) — 조립 루트가 다 꽂아 주지만 좁은 시험이 빈손으로 만들 수 있게 남겨 뒀다. 없애려면 시험을 고쳐야 한다"),
    ("domains → presentation", ("domains",), ("presentation",), 3,
     "도메인의 HTTP 입구 셋(`delegation_api` · `trip_api` · `web_limits_api`)이 인증 의존(`Principal` · `require_scope`)을 `presentation/security.py` 에서 쓴다. 인증을 중립 자리로 옮겨야 0 이 된다"),
    ("presentation → 조립 루트", ("presentation",), ("(루트)",), 1,
     "`presentation/api/cases.py` 가 `app.composition` 으로 컨트롤러를 만든다"),
]


def _layer(parts: tuple[str, ...]) -> str:
    return parts[0] if len(parts) > 1 else "(루트)"


def _target(module: str) -> str | None:
    seg = module.split(".")
    if seg[0] != "app" or len(seg) < 2:
        return None
    return "(루트)" if seg[1] in ROOT_FILES else seg[1]


def _edges() -> dict[tuple[str, str], set[tuple[str, str]]]:
    found: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for path in sorted(APP.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(APP).parts
        source = _layer(rel)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                target = _target(module)
                if target is not None and target != source:
                    found.setdefault((source, target), set()).add(("/".join(rel), module))
    return found


def test_the_layers_exist():
    for layer in (*BASEMENT, "domains"):
        assert (APP / layer).is_dir(), f"`app/{layer}/` 가 없다 — 검사가 헛돈다"


def test_layer_directions_do_not_get_worse():
    edges = _edges()
    report = []
    for name, callers, callees, ceiling, why in RULES:
        pairs = sorted(pair for (src, dst), found in edges.items() if src in callers and dst in callees for pair in found)
        now = len(pairs)
        listing = "\n".join(f"      {src} → {module}" for src, module in pairs)
        if now > ceiling:
            report.append(f"  {name}: {now} > 상한 {ceiling} — 늘었다 ({why})\n{listing}")
        elif now < ceiling:
            report.append(f"  {name}: {now} < 상한 {ceiling} — 줄었다. 상한을 {now} 로 내린다\n{listing}")
    assert not report, "층끼리 부르는 방향:\n" + "\n".join(report)
