# -*- coding: utf-8 -*-
"""접수 → 확인 화면 → **요식 판정 에이전트** — 식사 항목의 판정이 `dining.dn_agent_judge` 에 남는다. `[2026-10-13 · 2026-10-16]`
가짜 모델은 found 를 unknown 으로만 내서 확인 줄은 바뀌지 않는다(규칙이 이미 판정한 줄은 그대로).

모델은 가짜(계획을 읽고 식사마다 found 를 unknown 으로 낸다 — 근거 없는 unknown 은 검증을 통과한다). 실제 모델 평가는 `eval/runners/dining_agent.py`.
"""
from __future__ import annotations

import json
from functools import partial

from app.domains.travel_ops.components.team_hooks import dining_ledger
from app.domains.travel_ops.instances.dining import judge
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


def test_the_judge_runs_after_review_and_records_in_the_dining_table(rv, monkeypatch):
    chat = ReadingChat()
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: partial(judge.run, chat=chat, model="fake"))
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    assert view["status"] == "review"                                         # 확인 화면은 그대로 나온다
    meal = next(i for i in view["review"]["items"] if i["kind"] == "dining")
    assert chat.plans and chat.plans[0]["date"] == meal["date"]
    assert "광장시장" in chat.plans[0]["customer_notes"]                       # 계획 원문을 조건 읽기용으로 넘긴다(저장하지 않는다)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT check_code, item_id, agent_verdict, rule_verdict, model FROM dining.dn_agent_judge "
                    "WHERE intake_id = %s ORDER BY judge_id", (view["intake_id"],))
        rows = cur.fetchall()
        cur.execute("DELETE FROM dining.dn_agent_judge WHERE intake_id = %s", (view["intake_id"],))
        conn.commit()
    assert rows[0][0] == "_run"
    found = [r for r in rows if r[0] == "found"]
    assert found and found[0][1] == meal["id"] and found[0][2] == "unknown" and found[0][4] == "fake"
    assert found[0][3] in ("ok", "bad", "unknown")                           # 같은 항목의 규칙 검사 줄(place)과 나란히


def test_an_edit_judges_the_new_revision_again(rv, monkeypatch):
    """`[2026-10-16 설계 대조 P2]` 고치면 새 판의 검사가 새로 계산된다 — 그 판의 식사를 뒤에서 다시 판정해 그 판에 남긴다."""
    from .test_intake_review import _edit, _field, _item

    chat = ReadingChat()
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: partial(judge.run, chat=chat, model="fake"))
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    edited = _edit(client, headers, view, _field(_item(view, "올리브영"), "removed", True))
    assert edited["revision"] == view["revision"] + 1
    assert len(chat.plans) == 2                                               # 접수 때 한 번 · 고친 뒤 새 판에 한 번
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT revision FROM dining.dn_agent_judge WHERE intake_id = %s ORDER BY revision",
                    (view["intake_id"],))
        revisions = [r[0] for r in cur.fetchall()]
        cur.execute("DELETE FROM dining.dn_agent_judge WHERE intake_id = %s", (view["intake_id"],))
        conn.commit()
    assert revisions == [view["revision"], edited["revision"]]


def test_with_the_mock_model_nothing_is_written(rv):
    """스위치는 기본 켜짐이지만 시험(모의 모델)에서는 실행기를 만들지 않는다 — 가짜 키로 실제 모델을 부르지 않는다."""
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers)
    assert view["status"] == "review"
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM dining.dn_agent_judge WHERE intake_id = %s", (view["intake_id"],))
        assert cur.fetchone()[0] == 0
