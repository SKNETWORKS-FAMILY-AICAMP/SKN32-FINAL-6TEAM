# -*- coding: utf-8 -*-
"""장소 실내외를 한 번 정해 저장하고 읽는다 — `activity.ac_indoor`(301). `[2026-10-12]` D-CS-015 개정 2 · 구현 계획 1.8.

    순서   저장값 → 관광공사 분류 → LLM 한 번(인용 검증) → 그래도 모르면 계획 검증에서만 고객에게(저장은 `record(..., "customer")`)
    우선   operator(사람 수정) > customer > llm > class — 높은 값을 낮은 값으로 덮지 않는다
    갱신   관광공사 분류가 바뀌면 class · llm 줄만 지우고 다시 정한다

★계산 · 저장만 한다 — 연결(`conn`)은 부르는 쪽(코어 끼움 자리 · 활동 스크립트)이 넘긴다. 팀(`team.py`)은 DB 를 직접 읽지 않는다.
★모름은 저장하지 않는다. LLM 은 `judge` 계층이 인용 검증을 통과시킨 값만 받는다.
"""
from __future__ import annotations

from typing import Any, Callable

PRIORITY = ("operator", "customer", "llm", "class")       # 앞이 높다
_COLS = ("decided_by", "outdoor", "model", "prompt_version", "quote", "decided_case_id", "decided_at")


def read(conn, content_id: str | None) -> dict[str, Any] | None:
    """가장 높은 줄 하나 — `{outdoor, decided_by, model, …}`. 없으면 `None`(모름)."""
    if not content_id:
        return None
    with conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_COLS)} FROM activity.ac_indoor WHERE content_id = %s "
                    "ORDER BY array_position(%s::text[], decided_by) LIMIT 1", (str(content_id), list(PRIORITY)))
        row = cur.fetchone()
    return dict(zip(_COLS, row)) if row else None


def record(conn, content_id: str, outdoor: bool, decided_by: str, *, model: str | None = None,
           prompt_version: str | None = None, quote: str | None = None, case_id: str | None = None) -> None:
    """정한 쪽의 줄을 쓴다(같은 쪽이면 새 값으로). 우선순위는 읽을 때 정한다 — 높은 줄이 있으면 이 값은 쓰이지 않는다."""
    if decided_by not in PRIORITY:
        raise ValueError(f"decided_by 는 {PRIORITY} 중 하나: {decided_by!r}")
    if not isinstance(outdoor, bool):
        raise ValueError("모름은 저장하지 않는다 — outdoor 는 True/False 여야 한다")
    with conn.cursor() as cur:
        cur.execute("INSERT INTO activity.ac_indoor (content_id, decided_by, outdoor, model, prompt_version, quote, "
                    "decided_case_id) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (content_id, decided_by) DO UPDATE SET "
                    "outdoor = EXCLUDED.outdoor, model = EXCLUDED.model, prompt_version = EXCLUDED.prompt_version, "
                    "quote = EXCLUDED.quote, decided_case_id = EXCLUDED.decided_case_id, decided_at = now()",
                    (str(content_id), decided_by, outdoor, model, prompt_version, quote, case_id))


def forget_derived(conn, content_id: str) -> int:
    """관광공사 분류가 바뀌었을 때 — class · llm 줄만 지운다(고객 · 운영자 줄은 남긴다). 지운 줄 수."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM activity.ac_indoor WHERE content_id = %s AND decided_by IN ('class', 'llm')",
                    (str(content_id),))
        return cur.rowcount


#: LLM 판정 — 장소 `(name, lcls2)` → `{"outdoor": bool, "model": str, "prompt_version": str, "quote": str}` | None(모름 · 못 부름)
IndoorJudge = Callable[[str | None, str | None], "dict[str, Any] | None"]


def decide(conn, content_id: str, *, name: str | None, lcls1: str | None, lcls2: str | None,
           judge: IndoorJudge | None = None) -> dict[str, Any] | None:
    """저장값 → 관광공사 분류 → (judge 가 있으면) LLM 한 번. 정해지면 저장하고 돌려준다. 끝까지 모르면 `None`.
    ★고객에게 묻는 것은 부르는 쪽(계획 검증)이 한다 — 여기서는 묻지 않는다(감시 루프에서도 불릴 수 있다)."""
    from app.domains.travel_ops.components.itinerary.itinerary import weather_from_class

    stored = read(conn, content_id)
    if stored is not None:
        return stored
    by_class = weather_from_class(lcls1 or (lcls2[:2] if lcls2 else None), lcls2)
    if by_class is not None:
        record(conn, content_id, bool(by_class), "class")
        return read(conn, content_id)
    if judge is None:
        return None
    verdict = judge(name, lcls2)
    if not verdict or not isinstance(verdict.get("outdoor"), bool) or not verdict.get("quote") or not verdict.get("model"):
        return None                                   # 인용 · 모델이 없으면 저장하지 않는다(모름)
    record(conn, content_id, verdict["outdoor"], "llm", model=verdict["model"],
           prompt_version=verdict.get("prompt_version"), quote=verdict["quote"])
    return read(conn, content_id)
