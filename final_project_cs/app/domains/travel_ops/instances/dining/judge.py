# -*- coding: utf-8 -*-
"""요식 판정 — 에이전트가 고른 확인 · 규칙 도구 결과를 **접수 확인 줄에 합친다**. `[2026-10-16 사용자 결정 — 그림자 모드를 뺀다]`

「LLM은 읽고 판단하고, 코드는 계산하고, 승인은 고객이」:
  에이전트(`agent.judge_day`)가 식사마다 무엇을 확인할지 고르고 규칙 도구 · 바깥 조회(카카오 · 구글)를 부른다. 판정 값은 도구 결과다.
★화면 문장은 지금처럼 **코드가 만든다** — 에이전트의 문장(reason)은 고객에게 내보내지 않고 근거로만 남긴다(사용자: 「화면 보여지는 건 지금처럼」).
★바꾸는 것은 둘뿐이다
  ①규칙 검사가 **모름**(unknown)인 영업 · 휴무 줄에 에이전트가 도구 근거로 ok · bad 를 냈으면 그 줄을 그 판정으로 바꾼다
    (구글 실시간 영업이 근거면 「구글 정보로는 …」).
  ②규칙 검사에 없는 확인 — 고객 조건(식이 · 아이 · 결제)은 결과와 함께, 폐업은 bad 일 때만 새 줄로 더한다.
  규칙이 이미 판정한 줄은 그대로다(줄에 에이전트 판정 · 같은지만 근거로 단다). 에이전트 실패 · 근거 검증 실패인 체크는 쓰지 않는다.
★접수 확인으로 넘긴 **뒤에** 돈다(에이전트는 하루 15~30초) — 같은 판의 저장된 검사(`intake_reviews`)를 고쳐 쓰고, 화면은 다음 조회에서 본다.
  고친 줄로 확인 필요 개수(`needs`) · 등록 가능(`ready`)을 다시 센다.
★근거 기록은 `dining.dn_agent_judge`(232)에 쓴다 — 체크마다 에이전트 판정 · 규칙 판정 · 근거 · 실패 이유.
★`[2026-10-16 사용자 지시]` 옛 「그림자」 이름(모듈 `shadow.py` · 가드레일 `agent_shadow` · 표 `dn_agent_shadow`)을 모두 「판정」으로 바꿨다.

규칙 검사 줄 → 체크
    place  → found       hours → open_at       closed → closed_day
  규칙 검사의 결과 ok · filled · warn 은 ok(warn 은 「주의」지 「안 된다」가 아니다), bad 는 bad, unknown 은 unknown.
  ★`[2026-10-15]` 단 운영시간 줄은 그 줄이 따로 싣는 **시작 시각에 열려 있나**(`open_at`)가 있으면 그것을 쓴다 — 운영시간 warn 에는
    「시작 때 이미 닫힘」이 섞여 있다.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from typing import Any, Callable

from app.domains.travel_ops.instances.dining.agent import judge_day, shows_verdict
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

log = logging.getLogger(__name__)

RULE_ROWS = {"place": "found", "hours": "open_at", "closed": "closed_day"}
RULE_RESULT = {"ok": "ok", "filled": "ok", "warn": "ok", "bad": "bad", "unknown": "unknown"}
#: 에이전트에게 넘기는 계획 원문 길이 상한(글자) — 조건 문장을 읽히는 데 충분하고 토큰을 아낀다
NOTES_MAX = 2000

#: 규칙 검사 줄 ↔ 에이전트 체크
ROW_OF = {"open_at": "hours", "closed_day": "closed"}
#: 화면 문장(코드가 만든다) — 체크 × 판정. 지금 확인 화면 말투를 따른다
TEXT = {
    ("open_at", "ok"): "그 시각에 영업해요", ("open_at", "bad"): "그 시각에는 영업하지 않아요",
    ("closed_day", "ok"): "그날은 쉬는 날이 아니에요", ("closed_day", "bad"): "그날은 쉬는 날이에요",
    ("business", "bad"): "폐업했거나 옮긴 곳으로 나와요",
    ("dietary", "ok"): "요청하신 식사 조건(할랄 · 채식)에 맞는 곳이에요",
    ("dietary", "bad"): "요청하신 식사 조건(할랄 · 채식)에 맞지 않는 곳이에요",
    ("dietary", "unknown"): "요청하신 식사 조건(할랄 · 채식)은 확인하지 못했어요",
    ("kids", "ok"): "아이와 함께 갈 수 있는 곳이에요", ("kids", "bad"): "아이 동반이 어려운 곳이에요",
    ("kids", "unknown"): "아이 동반 가능 여부는 확인하지 못했어요",
    ("payment", "ok"): "카드 결제가 되는 곳이에요", ("payment", "bad"): "카드 결제가 안 되는 곳이에요",
    ("payment", "unknown"): "카드 결제 여부는 확인하지 못했어요",
}
#: 새 줄로 더하는 체크 — 폐업은 bad 일 때만(「폐업 기록 없음」은 고객에게 뜻이 없다)
ADDED = ("dietary", "kids", "payment", "business")


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


def _tools_of(check: dict[str, Any], calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """체크가 인용한 도구 호출 — 화면 줄의 근거 칸(도구 이름 · 호출 id · 경로 · 값)."""
    by_id = {c["id"]: c for c in calls}
    return [{"tool": by_id.get(ev.get("call_id"), {}).get("tool"), "call_id": ev.get("call_id"),
             "path": ev.get("path"), "value": ev.get("value")} for ev in check.get("evidence") or []]


def _text(code: str, verdict: str, evidence: list[dict[str, Any]]) -> str:
    text = TEXT[(code, verdict)]
    if code == "open_at" and any(e.get("tool") == "live_open_check" for e in evidence):
        text = "구글 정보로는 " + text                     # 원장이 몰라 실시간 영업(구글)으로 정했다
    return text


def merge(review: dict[str, Any], decided: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], int]:
    """검사(`review`)에 에이전트 판정(`decided` — 항목 id → 체크들, 근거 검증을 통과한 것만)을 합친다. (새 검사, 고친 줄 수)."""
    changed = 0
    for item in review.get("items") or []:
        checks = decided.get(item.get("id")) or []
        if item.get("kind") != "dining" or not checks:
            continue
        rows = item.setdefault("rows", [])
        rule = rule_verdicts(item)
        for check in checks:
            code, verdict, evidence = check["check"], check["verdict"], check["evidence"]
            agent = {"verdict": verdict, "agree": (verdict == rule[code]) if code in rule else None, "evidence": evidence}
            row_name = ROW_OF.get(code)
            row = next((r for r in rows if r.get("row") == row_name), None) if row_name else None
            # ★`[2026-10-16 설계 대조 P1]` 화면 줄은 **근거에 그 판정을 낸 규칙 도구(구글 포함)의 값이 보일 때만** 바꾼다.
            #   원문(place_detail)만 읽은 판정은 검증기가 문장의 뜻까지 못 보므로 줄에 에이전트 판정으로만 단다
            shown = shows_verdict(check)
            if row is not None:
                row["agent"] = agent
                if rule.get(code) == "unknown" and verdict in ("ok", "bad") and shown:
                    row.update({"result": verdict, "text": _text(code, verdict, evidence), "by": "agent"})
                    if code == "open_at":
                        row["open_at"] = verdict
                    changed += 1
            elif code in ADDED and (code, verdict) in TEXT and shown and not any(r.get("row") == code for r in rows):
                rows.append({"row": code, "result": verdict, "text": _text(code, verdict, evidence), "by": "agent",
                             "agent": agent})
                changed += 1
        if any(r.get("result") == "bad" for r in rows) and item.get("status") != "review":
            item["status"], item["can_lock"] = "review", False
    items = review.get("items") or []
    moves = review.get("moves") or []
    needs_items = sum(1 for it in items if it.get("status") == "review")
    needs_moves = sum(1 for m in moves if m.get("status") == "review")
    was_ready = bool(review.get("ready"))
    review["needs"] = {"items": needs_items, "moves": needs_moves, "total": needs_items + needs_moves}
    review["ready"] = was_ready and needs_items + needs_moves == 0       # 더 나빠질 수만 있다 — 규칙 문제(problems)는 다시 보지 않는다
    return review, changed


def run(connect: Callable[[], Any], *, tenant_id: str, intake_id: Any, revision: int, review: dict[str, Any],
        notes: str, chat: Any, model: str, deadline_s: float = 120.0,
        tools_factory: Callable[[Callable[[], Any]], DiningTools] = DiningTools) -> dict[str, Any]:
    """날마다 에이전트를 돌리고, 근거를 기록하고, 검증을 통과한 판정을 그 판의 저장된 검사에 합친다. 돌려주는 값은 셈."""
    from app.domains.travel_ops.components.intake import review as review_module

    run_id = uuid.uuid4()
    records: list[tuple] = []
    decided: dict[str, list[dict[str, Any]]] = {}
    counts = {"days": 0, "checks": 0, "used": 0, "failures": 0, "missing": 0, "changed": 0, "stale": 0}
    rule_of = {i["id"]: rule_verdicts(i) for i in review.get("items") or [] if i.get("kind") == "dining"}
    for plan in plans_from_review(review, notes):
        counts["days"] += 1
        tools = tools_factory(connect)
        result = judge_day(plan, tools=tools, chat=chat, deadline_s=deadline_s)
        records.append((None, "_run", None, None, None, result.failure,
                        {"date": plan["date"], **result.stats, "tools": [c["tool"] for c in result.tool_calls]}))
        if result.failure:
            counts["failures"] += 1
            continue                                         # 그날은 규칙 검사 그대로
        for item in result.items:
            item_id = str(item.get("item_id"))
            if item_id not in rule_of:
                continue
            for check in item["checks"]:
                code, verdict = check.get("check"), check.get("verdict")
                rule = rule_of[item_id].get(code)
                counts["checks"] += 1
                records.append((item_id, code, verdict, rule, (verdict == rule) if rule is not None else None,
                                check.get("failure"),
                                {k: check.get(k) for k in ("why_chosen", "reason", "evidence", "claimed_verdict") if check.get(k)}))
                if check.get("failure") is None:
                    counts["used"] += 1
                    decided.setdefault(item_id, []).append(
                        {"check": code, "verdict": verdict, "evidence": _tools_of(check, result.tool_calls)})
        for gap in result.missing:
            counts["missing"] += 1
            records.append((str(gap["item_id"]), gap["check"], None, rule_of.get(str(gap["item_id"]), {}).get(gap["check"]),
                            None, gap["failure"], {}))
    with connect() as conn, conn.transaction():
        with conn.cursor() as cur:
            for item_id, code, agent, rule, agree, failure, detail in records:
                cur.execute("INSERT INTO dining.dn_agent_judge (run_id, tenant_id, intake_id, revision, item_id, check_code, "
                            "agent_verdict, rule_verdict, agree, failure, detail, model) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                            (str(run_id), tenant_id, str(intake_id), revision, item_id, code, agent, rule, agree, failure,
                             json.dumps(detail, ensure_ascii=False, default=str), model))
        if decided:
            # ★합치는 바탕은 **지금 저장된** 그 판의 검사다 — 넘겨받은 `review` 는 에이전트를 돌리는 사이 다시 계산됐을 수 있다
            current = review_module.load(conn, tenant_id, intake_id, revision)
            # ★`[2026-10-16 설계 대조 P2]` 그 사이 고객이 고쳐 새 판이 생겼거나 등록했으면 합치지 않는다 — 버린 것도 한 줄 남긴다.
            #   새 판은 고치기 뒤의 다시 판정(`pipeline.rejudge`)이 맡는다. 접수 줄을 잠그고 보므로 합치는 동안 고치기 · 등록이 기다린다
            state = review_module.intake_state(conn, tenant_id, intake_id) if current else None
            if current and state != ("review", revision):
                current, counts["stale"] = None, 1
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO dining.dn_agent_judge (run_id, tenant_id, intake_id, revision, item_id, check_code, "
                                "agent_verdict, rule_verdict, agree, failure, detail, model) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                                (str(run_id), tenant_id, str(intake_id), revision, None, "_stale", None, None, None,
                                 "intake_moved_on", json.dumps({"now": list(state) if state else None}), model))
            if current:
                merged, counts["changed"] = merge(current, decided)
                merged["agent_judged"] = {"run_id": str(run_id), "model": model, "changed_rows": counts["changed"]}
                review_module.store(conn, tenant_id, intake_id, revision, merged)
    return {"run_id": str(run_id), **counts}


__all__ = ["ADDED", "RULE_ROWS", "ROW_OF", "TEXT", "merge", "plans_from_review", "rule_verdicts", "run"]
