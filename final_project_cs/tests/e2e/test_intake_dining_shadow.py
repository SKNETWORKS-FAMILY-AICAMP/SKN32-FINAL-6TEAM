# -*- coding: utf-8 -*-
"""접수 → 확인 화면 → **요식 판정 에이전트 그림자** — 확인 화면은 그대로이고, 식사 항목의 판정이 `dining.dn_agent_shadow` 에만 남는다. `[2026-10-13]`

모델은 가짜(계획을 읽고 식사마다 found 를 unknown 으로 낸다 — 근거 없는 unknown 은 검증을 통과한다). 실제 모델 평가는 `eval/runners/dining_agent.py`.
"""
from __future__ import annotations

import json
from functools import partial

from app.domains.travel_ops.components.team_hooks import dining_ledger
from app.domains.travel_ops.instances.dining import shadow
from app.infrastructure.db.session import get_connection
from app.infrastructure.llm.tool_chat import ToolTurn

from .test_intake_review import _client, _key, _send, rv  # noqa: F401
from .test_trip_api import api  # noqa: F401


class ReadingChat:
    """계획(사용자 메시지)을 읽고 식사 항목마다 체크 하나를 낸다 — 도구는 부르지 않는다."""

    def __init__(self):
        self.plans = []

    def step(self, messages, tools, final_json=False):
        plan = json.loads(messages[1]["content"])
        self.plans.append(plan)
        items = [{"item_id": i["item_id"], "place": None,
                  "checks": [{"check": "found", "verdict": "unknown", "reason": "가짜 모델", "evidence": []}]}
                 for i in plan["items"] if i["kind"] == "dining"]
        return ToolTurn(content=json.dumps({"items": items, "skipped": []}, ensure_ascii=False))


def test_the_shadow_runs_after_review_and_writes_only_to_the_dining_table(rv, monkeypatch):
    chat = ReadingChat()
    monkeypatch.setattr(dining_ledger, "agent_shadow_runner", lambda: partial(shadow.run, chat=chat, model="fake"))
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    assert view["status"] == "review"                                         # 확인 화면은 그대로 나온다
    meal = next(i for i in view["review"]["items"] if i["kind"] == "dining")
    assert chat.plans and chat.plans[0]["date"] == meal["date"]
    assert "광장시장" in chat.plans[0]["customer_notes"]                       # 계획 원문을 조건 읽기용으로 넘긴다(저장하지 않는다)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT check_code, item_id, agent_verdict, rule_verdict, model FROM dining.dn_agent_shadow "
                    "WHERE intake_id = %s ORDER BY shadow_id", (view["intake_id"],))
        rows = cur.fetchall()
        cur.execute("DELETE FROM dining.dn_agent_shadow WHERE intake_id = %s", (view["intake_id"],))
        conn.commit()
    assert rows[0][0] == "_run"
    found = [r for r in rows if r[0] == "found"]
    assert found and found[0][1] == meal["id"] and found[0][2] == "unknown" and found[0][4] == "fake"
    assert found[0][3] in ("ok", "bad", "unknown")                           # 같은 항목의 규칙 검사 줄(place)과 나란히


def test_without_the_switch_nothing_is_written(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    assert view["status"] == "review"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dining.dn_agent_shadow WHERE intake_id = %s", (view["intake_id"],))
        assert cur.fetchone()[0] == 0
