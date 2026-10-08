# -*- coding: utf-8 -*-
"""여행 묶음의 칸끼리 누가 누구를 부르는가 (D-CS-013, 2026-10-06).

칸: modules(끌 수 있는 기능) · instances(에이전트 팀) · components(필수 부품) · ports(바꿔 끼우는 자리) ·
entry(HTTP 입구) · scenarios.

    팀 → 다른 팀 속          0 이어야 한다 (팀끼리는 코어를 거쳐서만 만난다)
    필수 부품 → 팀 속         줄여 나간다 — 부품이 특정 팀 내부를 알면 그 팀을 빼는 순간 부품이 깨진다
    필수 부품 → 끌 수 있는 기능 · 입구   줄여 나간다 — 끌 수 있다는 말이 거짓이 된다
    바꿔 끼우는 자리 → 기능 · 부품 · 입구 · 팀 속   줄여 나간다

★폴더를 나눈 날(2026-10-06) 이미 어기는 곳이 있었다. 옮기는 작업과 고치는 작업을 섞지 않으려고
  **그날 수를 상한으로 박았다** — 늘면 실패하고, 줄이면 상한도 같이 내린다(내리지 않으면 실패한다).
  어기는 곳 목록은 실패 메시지에 나온다.
"""
from __future__ import annotations

import ast
from pathlib import Path

BASE = Path("app/domains/travel_ops")
PKG = "app.domains.travel_ops"

#: 2026-10-06 실측 상한 — (부르는 파일, 불리는 칸.하위) 짝의 수
CEILING = {
    "팀 → 다른 팀 속": 0,
    "필수 부품 → 팀 속": 0,                       # 2026-10-06 끼움 자리 넷으로 14 → 0
    "필수 부품 → 끌 수 있는 기능·입구": 0,       # 2026-10-06 (나) 전환으로 4 → 0
    "바꿔 끼우는 자리 → 기능·부품·입구·팀 속": 0,  # 동 — 연결 흐름을 웹 기능 칸으로 옮겼다
}


def _cell(module: str) -> tuple[str | None, str | None]:
    if not module.startswith(PKG + "."):
        return None, None
    rest = module[len(PKG) + 1:].split(".")
    return rest[0], (rest[1] if len(rest) > 1 else None)


def _edges() -> dict[str, set[tuple[str, str]]]:
    found: dict[str, set[tuple[str, str]]] = {key: set() for key in CEILING}
    for path in sorted(BASE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(BASE).parts
        if len(rel) < 2:
            continue                       # travel_ops/__init__.py — 팀 다시 내보내기
        src_cell = rel[0]
        src_team = rel[1] if src_cell == "instances" and len(rel) > 2 else None
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = [node.module]
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                cell, sub = _cell(module)
                if cell is None:
                    continue
                target = f"{cell}.{sub}" if sub else cell
                key = None
                if (src_cell == "instances" and cell == "instances" and src_team not in (None, "_shared")
                        and sub not in (src_team, "_shared")):
                    key = "팀 → 다른 팀 속"
                elif src_cell == "components" and cell == "instances" and sub != "_shared":
                    key = "필수 부품 → 팀 속"
                elif src_cell == "components" and cell in ("modules", "entry"):
                    key = "필수 부품 → 끌 수 있는 기능·입구"
                elif src_cell == "ports" and (cell in ("modules", "components", "entry")
                                              or (cell == "instances" and sub != "_shared")):
                    key = "바꿔 끼우는 자리 → 기능·부품·입구·팀 속"
                if key:
                    found[key].add(("/".join(rel), target))
    return found


def test_the_cells_exist():
    for cell in ("modules", "instances", "components", "ports", "entry", "scenarios"):
        assert (BASE / cell / "__init__.py").is_file(), f"칸 `{cell}/` 이 없다 — 검사가 헛돈다"


def test_cell_rules_do_not_get_worse():
    found = _edges()
    report = []
    for key, ceiling in CEILING.items():
        now = len(found[key])
        listing = "\n".join(f"      {src} → {target}" for src, target in sorted(found[key]))
        if now > ceiling:
            report.append(f"  {key}: {now} > 상한 {ceiling} — 늘었다\n{listing}")
        elif now < ceiling:
            report.append(f"  {key}: {now} < 상한 {ceiling} — 줄었다. CEILING 을 {now} 로 내린다\n{listing}")
    assert not report, "칸끼리 부르는 규칙:\n" + "\n".join(report)
