# -*- coding: utf-8 -*-
"""병합 게이트 목록(`conftest.GATE`)이 실제 시험 이름을 가리키는지. 이름이 바뀌면 그 기능이 조용히 게이트 밖으로 빠진다. `[2026-10-12]`"""
from __future__ import annotations

import ast
from pathlib import Path

from .conftest import GATE, HERE


def _tests(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


def test_every_gate_name_is_a_test_in_its_file():
    missing = {name: sorted(set(names) - _tests(HERE / name)) for name, names in GATE.items()}
    assert not {name: left for name, left in missing.items() if left}, "게이트에 적힌 시험이 파일에 없다 — 이름을 고친다"


def test_every_test_file_here_has_a_gate_entry():
    files = {path.name for path in HERE.glob("test_*.py")}
    assert files == set(GATE), "게이트가 없는 시험 파일 — 그 파일의 핵심 시험을 GATE 에 적는다"
