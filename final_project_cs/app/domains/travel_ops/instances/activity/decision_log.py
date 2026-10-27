# -*- coding: utf-8 -*-
"""LLM 운영 판정 한 건을 남긴다 — 코드 결과 · LLM 원래 답 · 고객에게 나간 결과. `[2026-10-24 사용자 지시]`

★왜. `kind_modes` 가 `llm` 이면 LLM 답이 고객 결과를 바꾸는데, 운영에서 무엇이 바뀌었는지 아무 데도 남지 않았다
  (「코드 결과 / LLM 재정의 결과 명확하게」). 조립이 꽂은 함수(`judge_decision_sink` → 표 `activity_llm_decisions`)로 쓴다.
  보고서는 `scripts/activity/llm_decision_report.py` 가 만든다.
★싣지 않는 것 — 고객 문장 · 설문 · 좌표 · 장소 이름. 장소는 번호(content id)만 싣고 이름은 보고서가 목록 표에서 찾는다.
★기록 쓰기가 실패해도 고객 답을 막지 않는다 — `WARNING` 로그로만 남긴다(섀도 기록과 같다).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.contracts import TeamTask

_log = logging.getLogger("acop.activity.llm_decision")

#: 고객에게 나간 결과가 어디서 왔나 — `308_activity_llm_decisions.sql` 의 `outcome` 과 같다
LLM_SERVED = "llm_served"
CODE_FALLBACK = "code_fallback"
SKIPPED = "skipped"
SHADOW = "shadow"


def record(sink: Any | None, task: TeamTask, *, kind: str, mode: str, outcome: str, code_result: dict[str, Any],
           served_result: dict[str, Any], llm_result: dict[str, Any] | None = None, reason: str | None = None,
           reason_guard: str | None = None, failure_code: str | None = None, error: str | None = None,
           latency_ms: int | None = None, model: str | None = None) -> None:
    """한 건을 남긴다. `changed` 는 고객에게 나간 결과가 코드 결과와 다른가다 — 직접 넘기지 않고 여기서 센다."""
    if sink is None:
        return
    row = {"tenant_id": task.context.tenant_id, "case_id": str(task.case_id) if task.case_id else None,
           "run_id": str(task.run_id) if task.run_id else None, "capability": task.capability,
           "kind": kind, "mode": mode, "outcome": outcome, "code_result": code_result, "llm_result": llm_result,
           "served_result": served_result, "changed": served_result != code_result, "reason": reason,
           "reason_guard": reason_guard, "failure_code": failure_code, "error": error,
           "latency_ms": latency_ms, "model": model}
    try:
        sink(row)
    except Exception as exc:  # noqa: BLE001 — 기록이 판정을 막지 않게, 보이게만 남긴다
        _log.warning(json.dumps({"event": "activity_llm_decision_sink_failed", "kind": kind,
                                 "case_id": row["case_id"], "error": type(exc).__name__}, ensure_ascii=False))
