# -*- coding: utf-8 -*-
"""요식 판정 에이전트 그림자(`instances/dining/shadow.py`) — 접수 검사와 나란히 판정해 `dining.dn_agent_shadow`(232)에만 쓴다. 모델은 가짜. `[2026-10-13]`"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager

from app.domains.travel_ops.instances.dining.shadow import plans_from_review, rule_verdicts, run
from app.infrastructure.llm.tool_chat import ToolTurn
from tests.integration.dining.test_dining_agent_tools import _real
from tests.integration.dining.test_dining_judgment import add_closure, add_hours, at

DAY = at(0, "12:00").date().isoformat()                      # 월요일


class Script:
    def __init__(self, *turns):
        self.turns = list(turns)

    def step(self, messages, tools, final_json=False):
        return self.turns.pop(0)


def _review(name: str) -> dict:
    ok = [{"row": "place", "result": "ok"}, {"row": "hours", "result": "ok"}, {"row": "closed", "result": "unknown"}]
    return {"items": [{"id": "0-0", "kind": "activity", "title": "경복궁", "date": DAY, "starts_at": "10:00", "ends_at": "11:30",
                       "place": {"name": "경복궁", "latitude": 37.58, "longitude": 126.98}, "rows": ok},
                      {"id": "0-1", "kind": "dining", "title": f"{name} 점심", "date": DAY, "starts_at": "12:00", "ends_at": "13:00",
                       "place": {"name": name, "latitude": 37.57, "longitude": 126.99}, "rows": ok}]}


def test_rule_rows_map_to_checks_and_days_without_meals_are_skipped():
    review = _review("가게")
    assert rule_verdicts(review["items"][1]) == {"found": "ok", "open_at": "ok", "closed_day": "unknown"}
    plans = plans_from_review(review, "할랄만 " * 1000)
    assert len(plans) == 1 and plans[0]["date"] == DAY and len(plans[0]["customer_notes"]) == 2000
    assert [i["item_id"] for i in plans[0]["items"]] == ["0-0", "0-1"]
    review["items"] = review["items"][:1]
    assert plans_from_review(review, "") == []                                      # 식사가 없는 날은 돌리지 않는다


def test_shadow_records_agreement_and_disagreement_only_in_the_dining_table(conn, place):
    uid = place("그림자국밥", lat=37.57, lng=126.99)
    _real(conn, uid)
    add_hours(conn, uid, 1, [(660, 1320, None)])
    add_closure(conn, uid, pattern_kind="weekly", weekday=1)                        # 월요일 휴무 — 규칙 검사(가짜)는 ok 라고 했다
    name = conn.execute("SELECT name_ko FROM dining.dn_place WHERE place_uid = %s", (uid,)).fetchone()[0]
    final = {"items": [{"item_id": "0-1", "place": {"place_uid": uid, "call_id": "c1"}, "checks": [
        {"check": "found", "verdict": "ok", "reason": "찾음", "evidence": [{"call_id": "c1", "path": "verdict", "value": "ok"}]},
        {"check": "open_at", "verdict": "bad", "reason": "월요일 휴무",
         "evidence": [{"call_id": "c2", "path": "verdict", "value": "bad"}]}]}], "skipped": []}
    chat = Script(ToolTurn(content=None, tool_calls=[
                      {"id": "t1", "name": "find_place", "arguments": {"name": name}},
                      {"id": "t2", "name": "check_open_at", "arguments": {"place_uid": uid, "start": f"{DAY}T12:00", "end": f"{DAY}T13:00"}}]),
                  ToolTurn(content=json.dumps(final, ensure_ascii=False)))

    @contextmanager
    def connect():
        yield conn

    intake_id = uuid.uuid4()
    try:
        got = run(connect, tenant_id="test", intake_id=intake_id, revision=1, review=_review(name), notes="", chat=chat,
                  model="fake")
        assert got["days"] == 1 and got["compared"] == 2 and got["disagree"] == 1 and got["failures"] == 0
        rows = conn.execute("SELECT check_code, agent_verdict, rule_verdict, agree FROM dining.dn_agent_shadow "
                            "WHERE intake_id = %s ORDER BY shadow_id", (intake_id,)).fetchall()
        assert rows == [("_run", None, None, None), ("found", "ok", "ok", True), ("open_at", "bad", "ok", False)]
    finally:
        conn.execute("DELETE FROM dining.dn_agent_shadow WHERE intake_id = %s", (intake_id,))
