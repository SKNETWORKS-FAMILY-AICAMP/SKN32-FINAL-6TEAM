# -*- coding: utf-8 -*-
"""이동 엔진의 **정책 수치** 읽기 — 값의 정본은 팀 `final_project_cs/config/guardrails.yaml` 의 `mobility:` 절 하나다.

☆`[2026-09-29 문제목록 #49]` 앞 판은 여유(버퍼)·환승 상한·도보 상한·시간표 노후 기준을 엔진 규칙 JSON 에 따로 두었다 —
  팀 안전 수치 파일을 바꿔도 엔진은 그대로였다(가드레일 수치는 한 곳에만 둔다 — final_project_cs/CLAUDE.md §3).
  규칙 JSON 에는 그 자리에 `"value": null, "value_from": "guardrails:mobility.…"` 만 남기고, 값은 여기서 읽는다.

★ 앱 설정(app.core.settings.get_guardrails)을 부르지 않는다 — 그 함수는 DB 주소 등 서버 설정 전체를 요구해서
  데이터 기기의 명령줄 도구(판정 회귀·자기점검)에서 돌지 않는다. 같은 파일을 직접 읽는다.
  서버는 기동할 때 설정의 경로로 `use(path)` 를 불러 같은 파일을 가리키게 할 수 있다.
"""
from __future__ import annotations

import copy
import threading
from pathlib import Path

import yaml

# engine → mobility → travel_ops → modules → app → final_project_cs
DEFAULT_PATH = Path(__file__).resolve().parents[5] / "config" / "guardrails.yaml"
PREFIX = "guardrails:"

_lock = threading.Lock()
_state = {"path": DEFAULT_PATH, "data": None}


class GuardrailMissing(KeyError):
    """정책 수치가 guardrails.yaml 에 없다 — 조용히 기본값을 쓰지 않는다(결정 15 · RULE §3.2)."""


def use(path) -> None:
    """읽을 파일을 바꾼다(서버 기동 때 설정의 guardrails_path). 다음 조회에서 다시 읽는다."""
    with _lock:
        _state["path"], _state["data"] = Path(path), None


def _data() -> dict:
    if _state["data"] is None:
        with _lock:
            if _state["data"] is None:
                p = _state["path"]
                if not p.is_file():
                    raise GuardrailMissing(f"guardrails 파일이 없다: {p}")
                _state["data"] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return _state["data"]


def lookup(ref: str):
    """'guardrails:mobility.buffer.by_stage.planning' 또는 'mobility.buffer.…' → 값. 없으면 GuardrailMissing."""
    dotted = ref[len(PREFIX):] if ref.startswith(PREFIX) else ref
    node = _data()
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise GuardrailMissing(f"guardrails 키 없음: {dotted} (파일 {_state['path']})")
        node = node[part]
    return node


def resolve(rules: dict) -> dict:
    """규칙 dict 사본 — `value_from` 이 있는 칸의 value 를 guardrails 값으로 채운다(스크립트가 원시 JSON 을 읽을 때)."""
    out = copy.deepcopy(rules)

    def walk(n):
        if isinstance(n, dict):
            if n.get("value") is None and isinstance(n.get("value_from"), str):
                n["value"] = lookup(n["value_from"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(out)
    return out
