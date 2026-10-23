# -*- coding: utf-8 -*-
"""경로 후보 「더 보기」 · 경로 고르기는 `move_judge`(이동 판정) 칸으로 센다 — 2026-10-23 사용자 지적(「서버 제한 문서 갱신된 거 봐」).

카카오를 부르는 `place_search` 와 섞이면 서비스 모드(D-CS-020) 게스트 장소 검색 한도(시간당 20)를 경로 목록 스크롤이 먹는다.
DB 없이 소스(AST)만 본다 — 실제로 세는지는 e2e(`tests/e2e/test_web_guard_service_mode.py` 계열)와 같은 `_count` 를 쓴다.

    python -m pytest tests/unit/intake/test_route_endpoints_count_move_judge.py -v
"""
from __future__ import annotations

import ast
from pathlib import Path

API = Path(__file__).resolve().parents[3] / "app/domains/travel_ops/entry/trip_api.py"


def _counted(name: str) -> list[str]:
    tree = ast.parse(API.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return [c.args[0].value for c in ast.walk(fn)
            if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "_count" and c.args and isinstance(c.args[0], ast.Constant)]


def test_more_routes_and_route_pick_count_as_move_judge():
    assert _counted("web_intake_move_routes") == ["move_judge"]
    assert _counted("web_intake_move_route") == ["move_judge"]
