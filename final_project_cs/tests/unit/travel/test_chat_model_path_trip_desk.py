# -*- coding: utf-8 -*-
"""x600 74b2b232 결함(6) — trip_desk Case 도 model_path 를 같은 자리(state_json.decision.model_path)에. `[2026-10-26]`

증거: 보고서 `wiki/records/reports/2026-10-26_x600_74b2b232_실서버확인.md`, case 8f6055e0(다른 데로) → 2b9fa1d1(choice 누름 → 한일옥),
1cff6b55(실내를 야외로 → 식당 no_alternate, 원출력 target_item=i2 · target_change=c6 · place_setting outdoor), 1caa81bc · bcb1050d(trip_desk, model_path 없음).
모든 바깥 서비스는 메모리 대역이다(모델 호출 없음).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domains.travel_ops.components.conversation import trip_messages



@pytest.fixture
def cases(monkeypatch):
    store: dict[str, dict] = {}
    from app.infrastructure.db import repository
    monkeypatch.setattr(repository, "get_case", lambda conn, *, tenant_id, case_id: store.get(str(case_id)))
    return store


# ── (6) trip_desk Case 도 model_path 를 같은 자리(state_json.decision.model_path)에 ─────────────

def test_routed_decision_keeps_the_model_path_recorded_when_the_case_was_opened(cases):
    case_id = uuid4()
    path = {"path": "api", "backend": "openai", "reasons": [["ollama", "timeout"]]}
    cases[str(case_id)] = {"state_json": {"decision": {"action": "change_time", "model_path": path}}}
    record = {"action": "change_time", "raw": {}}
    assert trip_messages._with_stored_model_path(None, "t", case_id, record) == {**record, "model_path": path}
    cases[str(case_id)] = {"state_json": {"decision": {"action": "change_time"}}}               # 넘김 장치 꺼짐 — 더하지 않는다
    assert trip_messages._with_stored_model_path(None, "t", case_id, record) == record


def test_run_decision_routed_patch_uses_the_preserving_record():
    """ROUTED 의 `decision` · `state_patch.decision` 이 보존 기록을 쓴다(전에는 `decision.record()` 로 덮어 model_path 를 지웠다)."""
    import inspect
    source = inspect.getsource(trip_messages._run_decision)
    assert "_with_stored_model_path(conn, tenant, case_id, decision.record())" in source
    assert '"state_patch": {**read_patch, "decision": decision.record()}' not in source
