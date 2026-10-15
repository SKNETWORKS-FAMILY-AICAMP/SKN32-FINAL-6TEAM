# -*- coding: utf-8 -*-
"""요식 판정 에이전트 **그림자 운행** — 접수 확인의 규칙 검사와 나란히 판정하고 어긋남을 기록한다. `[2026-10-13 · 설계 §10 단계 5]`

★고객 결과를 바꾸지 않는다 — 접수 확인 화면 · 등록 · 일정은 지금 규칙 검사(`intake/review.py`) 그대로다. 이 실행은
  읽기가 끝나 확인 화면으로 넘어간 **뒤에** 뒤 일꾼에서 돌고, 결과는 `dining.dn_agent_shadow`(232)에만 쓴다.
★설계 §1 적용 위치대로 **접수 확인에만** 붙인다 — 등록된 여행의 새벽 확인에는 쓰지 않는다.
★실패해도 접수에 영향이 없다 — 부르는 쪽(`pipeline.process`)이 예외를 삼키고 경고만 남긴다. 실행 실패도 요약 줄(`_run`)에 남긴다(조용히 넘기지 않는다).
★고객 문장(계획 원문)은 에이전트에게 조건을 읽히려고 넘기지만 **저장하지 않는다**.

비교하는 체크 — 규칙 검사 줄 → 체크
    place  → found       hours → open_at       closed → closed_day
  규칙 검사의 결과 ok · filled · warn 은 ok(warn 은 「주의」지 「안 된다」가 아니다), bad 는 bad, unknown 은 unknown.
  ★`[2026-10-15]` 단 운영시간 줄은 그 줄이 따로 싣는 **시작 시각에 열려 있나**(`open_at`)가 있으면 그것과 비교한다 — 운영시간 warn 에는
    「시작 때 이미 닫힘」이 섞여 있어 ok 로 세면 같은 판단(「영업 안 함」)이 어긋남으로 잡혔다(접수 8건 중 3줄).
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from typing import Any, Callable

from app.domains.travel_ops.instances.dining.agent import judge_day
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

log = logging.getLogger(__name__)

RULE_ROWS = {"place": "found", "hours": "open_at", "closed": "closed_day"}
RULE_RESULT = {"ok": "ok", "filled": "ok", "warn": "ok", "bad": "bad", "unknown": "unknown"}
#: 에이전트에게 넘기는 계획 원문 길이 상한(글자) — 조건 문장을 읽히는 데 충분하고 토큰을 아낀다
NOTES_MAX = 2000


def rule_verdicts(item: dict[str, Any]) -> dict[str, str]:
    """접수 검사 항목 하나의 규칙 판정 {체크: ok · bad · unknown}."""
    out: dict[str, str] = {}
    for row in item.get("rows") or []:
        check = RULE_ROWS.get(row.get("row"))
        if check == "open_at" and row.get("open_at") in ("ok", "bad"):
            out[check] = row["open_at"]
        elif check and row.get("result") in RULE_RESULT:
            out[check] = RULE_RESULT[row["result"]]
    return out


def plans_from_review(review: dict[str, Any], notes: str) -> list[dict[str, Any]]:
    """접수 검사 → 날마다 에이전트 계획 하나(식사가 있는 날만). 항목 id 는 접수 검사의 id 그대로."""
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in review.get("items") or []:
        if item.get("date"):
            by_day[item["date"]].append(item)
    plans = []
    for day, items in sorted(by_day.items()):
        if not any(i.get("kind") == "dining" and i.get("place") for i in items):
            continue
        rows = []
        for i in items:
            place = i.get("place") or {}
            rows.append({"item_id": i["id"], "kind": i.get("kind"), "title": i.get("title"),
                         "start": f"{day}T{i['starts_at']}" if i.get("starts_at") else None,
                         "end": f"{day}T{i['ends_at']}" if i.get("ends_at") else None,
                         "place": {k: v for k, v in {"name": place.get("name"), "lat": place.get("latitude"),
                                                     "lng": place.get("longitude")}.items() if v is not None} or None})
        plans.append({"date": day, "customer_notes": (notes or "")[:NOTES_MAX], "items": rows})
    return plans


def run(connect: Callable[[], Any], *, tenant_id: str, intake_id: Any, revision: int, review: dict[str, Any],
        notes: str, chat: Any, model: str, deadline_s: float = 120.0,
        tools_factory: Callable[[Callable[[], Any]], DiningTools] = DiningTools) -> dict[str, Any]:
    """그림자 한 판 — 날마다 에이전트를 돌리고 체크마다 한 줄씩 쓴다. 돌려주는 값은 셈(기록 · 시험용)."""
    run_id = uuid.uuid4()
    rows: list[tuple] = []
    counts = {"days": 0, "checks": 0, "compared": 0, "disagree": 0, "failures": 0}
    rule_of = {i["id"]: rule_verdicts(i) for i in review.get("items") or [] if i.get("kind") == "dining"}
    for plan in plans_from_review(review, notes):
        counts["days"] += 1
        tools = tools_factory(connect)
        result = judge_day(plan, tools=tools, chat=chat, deadline_s=deadline_s)
        rows.append((None, "_run", None, None, None, result.failure,
                     {"date": plan["date"], **result.stats, "tools": [c["tool"] for c in result.tool_calls]}))
        if result.failure:
            counts["failures"] += 1
        for item in result.items:
            item_id = str(item.get("item_id"))
            if item_id not in rule_of:
                continue                                      # 식사가 아닌 항목 · 모르는 id — 비교하지 않는다
            for check in item["checks"]:
                code = check.get("check")
                rule = rule_of[item_id].get(code)
                agent = check.get("verdict")
                agree = (agent == rule) if rule is not None else None
                counts["checks"] += 1
                counts["compared"] += agree is not None
                counts["disagree"] += agree is False
                rows.append((item_id, code, agent, rule, agree, check.get("failure"),
                             {k: check.get(k) for k in ("why_chosen", "reason", "evidence", "claimed_verdict") if check.get(k)}))
    with connect() as conn, conn.transaction(), conn.cursor() as cur:
        for item_id, code, agent, rule, agree, failure, detail in rows:
            cur.execute("INSERT INTO dining.dn_agent_shadow (run_id, tenant_id, intake_id, revision, item_id, check_code, "
                        "agent_verdict, rule_verdict, agree, failure, detail, model) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                        (str(run_id), tenant_id, str(intake_id), revision, item_id, code, agent, rule, agree, failure,
                         json.dumps(detail, ensure_ascii=False, default=str), model))
    return {"run_id": str(run_id), **counts}


__all__ = ["RULE_ROWS", "plans_from_review", "rule_verdicts", "run"]
