# -*- coding: utf-8 -*-
"""`[2026-10-27 A 접수·읽기 전수검사]` 먼저 채우기(`prefill.run`)가 계획 에이전트의 새 일정을 판에 넣지 못해도(`_add_item` 실패)
기록에는 「우리가 채움」으로 남았다 — 화면은 넣지 않은 일정을 채웠다고 보였다. 넣지 못한 것은 `kept` 로 이유와 함께 남긴다.
"""
from __future__ import annotations

from app.domains.travel_ops.components.intake import pipeline, prefill

def test_a_planner_item_that_could_not_be_added_is_kept_not_reported_as_filled(monkeypatch):
    review = {"items": [{"id": "0-0", "index": 0, "source_id": "s", "title": "경복궁", "kind": "activity", "date": "2030-11-06",
                         "day": 1, "place_state": "found", "place": {"name": "경복궁"}, "starts_at": "10:00", "ends_at": "11:30"}],
              "moves": []}
    claims = [{"source_id": "s", "field": "items[0].title", "value": "경복궁", "method": "rule", "evidence": {"line": 1},
               "needs_review": False, "note": None},
              {"source_id": "s", "field": "reading.agent", "method": "llm_agent", "evidence": {}, "needs_review": False, "note": None,
               "value": {"used": True, "gaps": [{"kind": "free_slot", "quote": "오후는 알아서", "day": 1, "start": "14:00", "end": "18:00"}]}}]
    pick = {"title": "북촌한옥마을", "date": "2030-11-06", "starts_at": "14:00", "ends_at": "15:30", "kind": "activity",
            "place": {"name": "북촌한옥마을", "latitude": 37.58, "longitude": 126.98, "source": "places", "kind": "activity"},
            "reason": "계획서의 「오후는 알아서」 — 그날 빈 시간(14:00~15:30)에 맞춰 계획 에이전트가 골랐어요"}
    records, edits = [], []

    def refused(_conn, **kw):
        edits.append(kw["edits"])
        raise pipeline.IntakeConflict("item_locked", "고정한 일정")

    monkeypatch.setattr(pipeline, "current_review", lambda conn, **kw: (None, review))
    monkeypatch.setattr(pipeline, "_claims", lambda *args: claims)
    monkeypatch.setattr(pipeline, "_trip_fields", lambda claims: {})
    monkeypatch.setattr(pipeline, "edit", refused)
    monkeypatch.setattr(prefill, "_store", lambda conn, **kw: records.append(kw["record"]))
    result = prefill.run(None, tenant_id="test", customer_id=None, intake_id=None, revision=1,
                         plan_slot=lambda gap, draft: [pick])
    assert edits, "새 일정을 넣어 보기는 했다"
    assert result["revision"] == 1, "판은 그대로다"
    assert not any(f.get("new") or f.get("title") == "북촌한옥마을" for f in result["filled"]), result["filled"]
    kept = [k for k in result["kept"] if k["owner"] == "planner"]
    assert kept and kept[0]["reason"] == prefill.ADD_FAILED_REASON, result["kept"]
    assert records and records[-1]["filled"] == result["filled"]
