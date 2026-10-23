# -*- coding: utf-8 -*-
"""요식 판정 — 에이전트가 고른 확인 · 규칙 도구 결과를 **접수 확인 줄에 합친다**. `[2026-10-16 사용자 결정 — 그림자 모드를 뺀다]`

「LLM은 읽고 판단하고, 코드는 계산하고, 승인은 고객이」:
  에이전트(`agent.judge_day`)가 식사마다 무엇을 확인할지 고르고 규칙 도구 · 바깥 조회(카카오 · 구글)를 부른다. 판정 값은 도구 결과다.
★화면 문장은 지금처럼 **코드가 만든다** — 에이전트의 문장(reason)은 고객에게 내보내지 않고 근거로만 남긴다(사용자: 「화면 보여지는 건 지금처럼」).
★화면 반영
  ①규칙 검사가 **모름**(unknown)인 영업 · 휴무 줄에 에이전트가 도구 근거로 ok · bad 를 냈으면 그 줄을 그 판정으로 바꾼다
    (구글 실시간 영업이 근거면 「구글 정보로는 …」).
  ②규칙 검사에 없는 확인 — 고객 조건(식이 · 아이 · 결제)은 결과와 함께, 폐업은 bad 일 때만 새 줄로 더한다.
  ③최신 근거로 검증된 필수 bad는 기존 ok · 주의도 bad로 내린다. 기존 문장·결과는 rule_text · rule_result에 남긴다.
  기존 bad를 LLM으로 올리지 않는다. 선호 불일치는 주의이고, 에이전트 실패 · 근거 검증 실패인 체크는 쓰지 않는다.
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
from datetime import datetime, timezone
from typing import Any, Callable

from app.domains.travel_ops.instances.dining.agent import CHECKS, VERDICTS, judge_day, shows_verdict
from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

log = logging.getLogger(__name__)

RULE_ROWS = {"place": "found", "hours": "open_at", "closed": "closed_day"}
RULE_RESULT = {"ok": "ok", "filled": "ok", "warn": "ok", "bad": "bad", "unknown": "unknown"}
#: 등록을 막을 수 있는 이용 가능성 확인(검증된 bad 일 때) — 「못 찾음」(found)은 넣지 않는다(자료 부족 → 확인 못 함)
BLOCKING_CHECKS = frozenset({"open_at", "closed_day", "business"})
#: 이용 가능성 확인 — 실패하면 그날 판정을 실패로 센다(고객 조건은 필수일 때만)
AVAILABILITY_CHECKS = frozenset({"found", "open_at", "closed_day", "business"})


def is_required(check: dict[str, Any]) -> bool:
    """이용 가능성 확인(영업 · 휴무 · 폐업)은 늘 필수, 고객 조건(식이 · 아이 · 결제)은 모델이 **명시(true)할 때만** 필수다.
    `[2026-10-16 사용자 결정]` 빠뜨리면 선호(주의)다 — 전에는 생략도 필수로 봐 선호가 등록을 막을 수 있었다."""
    return check.get("check") in BLOCKING_CHECKS or check.get("required") is True


#: 규칙 검사 줄 ↔ 에이전트 체크
ROW_OF = {"found": "place", "open_at": "hours", "closed_day": "closed"}
#: 화면 문장(코드가 만든다) — 체크 × 판정. 지금 확인 화면 말투를 따른다
TEXT = {
    ("found", "ok"): "식당을 확인했어요", ("found", "bad"): "식당을 확인하지 못했어요(확인 못 함) — 이름이나 주소를 고쳐 다시 확인할 수 있어요",
    ("open_at", "ok"): "그 시각에 영업해요", ("open_at", "bad"): "그 시각에는 영업하지 않아요",
    ("closed_day", "ok"): "그날은 쉬는 날이 아니에요", ("closed_day", "bad"): "그날은 쉬는 날이에요",
    ("business", "bad"): "폐업했거나 옮긴 곳으로 나와요",
    # 식단 문장의 {조건} 은 `_text` 가 근거로 확인한 속성(할랄 · 채식)으로 채운다 — 없으면 빈칸
    ("dietary", "ok"): "요청하신 식사 조건{조건}에 맞는 곳이에요",
    ("dietary", "bad"): "요청하신 식사 조건{조건}에 맞지 않는 곳이에요",
    ("dietary", "unknown"): "요청하신 식사 조건{조건}은 확인하지 못했어요",
    ("kids", "ok"): "아이와 함께 갈 수 있는 곳이에요", ("kids", "bad"): "아이 동반이 어려운 곳이에요",
    ("kids", "unknown"): "아이 동반 가능 여부는 확인하지 못했어요",
    ("payment", "ok"): "카드 결제가 되는 곳이에요", ("payment", "bad"): "카드 결제가 안 되는 곳이에요",
    ("payment", "unknown"): "카드 결제 여부는 확인하지 못했어요",
}
#: 새 줄로 더하는 체크 — 폐업은 bad 일 때만(「폐업 기록 없음」은 고객에게 뜻이 없다)
ADDED = ("dietary", "kids", "payment", "business")
#: 식단 속성(`check_attributes` 의 말) → 화면 이름. 순서가 문장 순서다
#: ☆`[2026-10-18]` 전에는 문장에 「(할랄 · 채식)」이 고정이라 할랄만 요청해도 채식이 같이 나왔다
DIET_LABELS = {"halal": "할랄", "vegetarian": "채식"}


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
    context = [{"item_id": i["id"], **{key: i.get(key) for key in
               ("day", "date", "kind", "title", "starts_at", "ends_at")}}
               for i in review.get("items") or []]
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
        plans.append({"date": day, "customer_notes": notes or "", "items": rows, "itinerary_context": context})
    return plans


def outside_ledger(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """고객 일정에 나왔는데 원장에 없던 가게 — 원장 추가 후보(사람이 확인한 뒤 넣는다 · 자동 적재하지 않는다). `[2026-10-21]`

    ★인허가(공공 자료)는 이름 · 주소 · 좌표를 남기고, 카카오로 찾은 가게는 **고객이 쓴 이름만** 남긴다(카카오 결과는 저장하지 않는다 —
      `agent_tools` 머리말). 같은 이름은 한 번만."""
    out: list[dict[str, Any]] = []
    for call in calls:
        if not isinstance(call, dict) or call.get("tool") != "find_place":
            continue
        got, query = call.get("result") or {}, str((call.get("args") or {}).get("name") or "")
        if not got.get("found") or got.get("source") not in ("license", "map") or any(o["query"] == query for o in out):
            continue
        row: dict[str, Any] = {"query": query, "source": got["source"]}
        if got["source"] == "license":
            row.update({k: got.get(k) for k in ("name", "address", "lat", "lng", "category")})
        out.append(row)
    return out


def _tools_of(check: dict[str, Any], calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """체크가 인용한 도구 호출 — 화면 줄의 근거 칸(도구 이름 · 호출 id · 경로 · 값)."""
    by_id = {c["id"]: c for c in calls}
    return [{"tool": by_id.get(ev.get("call_id"), {}).get("tool"), "call_id": ev.get("call_id"),
             "path": ev.get("path"), "value": ev.get("value")} for ev in check.get("evidence") or []]


def _diet_words(evidence: list[dict[str, Any]]) -> str:
    """근거가 확인한 식단 속성 — `attributes.<속성>.state` 경로에서 읽는다. 「(할랄)」 · 「(할랄 · 채식)」 · 없으면 빈 글자."""
    seen = {str(e.get("path") or "").split(".")[1] for e in evidence
            if str(e.get("path") or "").startswith("attributes.") and len(str(e.get("path")).split(".")) >= 2}
    words = [label for attr, label in DIET_LABELS.items() if attr in seen]
    return f"({' · '.join(words)})" if words else ""


def _text(code: str, verdict: str, evidence: list[dict[str, Any]]) -> str:
    text = TEXT[(code, verdict)]
    if code == "dietary":
        text = text.replace("{조건}", _diet_words(evidence))
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
            if check.get("customer_request") is not None:
                agent["customer_request"] = check["customer_request"]
            validated = check.get("validated") is True
            required = is_required(check)
            # `[2026-10-16 사용자 결정]` 「못 찾음」은 자료 부족 — 「확인 못 함」(unknown)으로 두고 이용 불가로 내리지 않는다
            not_found = code == "found" and verdict == "bad"
            if validated:
                agent.update({"check": code, "validated": True, "required": required})
            # 선택한 선호를 만족하지 못해도 이용 불가로 승격하지 않는다.
            result = "unknown" if not_found else "warn" if verdict == "bad" and not required else verdict
            flags = {"requirement": "required" if required else "preference",
                     "blocks_registration": validated and required and verdict == "bad"} if validated else {}
            row_name = ROW_OF.get(code)
            row = next((r for r in rows if r.get("row") == row_name), None) if row_name else None
            # ★`[2026-10-16 설계 대조 P1]` 화면 줄은 **근거에 그 판정을 낸 규칙 도구(구글 포함)의 값이 보일 때만** 바꾼다.
            #   원문(place_detail)만 읽은 판정은 검증기가 문장의 뜻까지 못 보므로 줄에 에이전트 판정으로만 단다
            shown = shows_verdict(check)
            if row is not None:
                previous_agent = row.get("agent") or {}
                # 같은 확인의 뒤쪽 ok · unknown이 이미 검증한 필수 bad와 그 근거를 지우지 않는다.
                if (row.get("blocks_registration") is True and row.get("result") == "bad"
                        and previous_agent.get("validated") is True and previous_agent.get("verdict") == "bad"
                        and previous_agent.get("evidence")):
                    continue
                row["agent"] = agent
                downgrade = validated and required and verdict == "bad" and shown and rule.get(code) != "bad" and not not_found
                if (rule.get(code) == "unknown" and verdict in ("ok", "bad") and shown) or downgrade:
                    if downgrade:
                        row.setdefault("rule_result", row.get("result"))
                        row.setdefault("rule_text", row.get("text"))
                    row.update({"result": result, "text": _text(code, verdict, evidence), "by": "agent", **flags})
                    if code == "open_at":
                        row["open_at"] = verdict
                    changed += 1
            elif code in ADDED and (code, verdict) in TEXT and shown:
                added = {"row": code, "result": result, "text": _text(code, verdict, evidence), "by": "agent",
                         "agent": agent, **flags}
                # 할랄 · 채식이 모두 dietary여도 근거와 판정은 각각 보존한다.
                # 첫 ok · 선호 bad · unknown이 뒤의 검증된 필수 bad를 가리지 않는다.
                if added not in rows:
                    rows.append(added)
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
    """준비된 토큰을 맡고 잠금 밖에서 판정한다. 현재 토큰만 최신 검사에 합쳐 완료/실패를 저장한다.

    metadata 없는 독립 호출은 예전 기록·합치기 경로를 유지한다. 실제 접수 pipeline은 먼저 prepare한다.
    ★`[2026-10-20]` 판정 상태(`components/intake/dining_review` — 접수 담당 영역)는 metadata 가 있을 때만 불러온다.
      그 모듈이 아직 없는 판(지금 develop)에서도 요식 판정은 예전 합치기 경로로 돈다.
    """
    from app.domains.travel_ops.components.intake import review as review_module

    metadata = review.get("dining_judge")
    lifecycle = isinstance(metadata, dict)
    run_id = str(metadata.get("run_id") or uuid.uuid4()) if lifecycle else str(uuid.uuid4())
    records: list[tuple] = []
    decided: dict[str, list[dict[str, Any]]] = {}
    counts = {"days": 0, "checks": 0, "used": 0, "failures": 0, "missing": 0, "changed": 0, "stale": 0}
    error_code = None

    def record(conn, rows):
        with conn.cursor() as cur:
            for item_id, code, agent, rule, agree, failure, detail in rows:
                cur.execute("INSERT INTO dining.dn_agent_judge (run_id, tenant_id, intake_id, revision, item_id, check_code, "
                            "agent_verdict, rule_verdict, agree, failure, detail, model) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)",
                            (run_id, tenant_id, str(intake_id), revision, item_id, code, agent, rule, agree, failure,
                             json.dumps(detail, ensure_ascii=False, default=str), model))

    if lifecycle:
        from app.domains.travel_ops.components.intake import dining_review

        if metadata.get("status") == "disabled":
            return {"run_id": metadata.get("run_id"), **counts}
        with connect() as conn:
            claimed = dining_review.begin(conn, tenant_id, intake_id, revision, run_id,
                                          input_fingerprint=dining_review.fingerprint(review, notes))
        if claimed is None:
            counts["stale"] = 1
            with connect() as conn, conn.transaction():
                record(conn, [(None, "_stale", None, None, None, "intake_token_not_pending", {})])
            return {"run_id": run_id, **counts}
        review = claimed

    rule_of = {str(i["id"]): rule_verdicts(i) for i in review.get("items") or [] if i.get("kind") == "dining"}
    plans = plans_from_review(review, notes)
    planned_ids = {str(i["item_id"]) for plan in plans for i in plan["items"] if i.get("kind") == "dining"}
    if lifecycle and set(rule_of) - planned_ids:
        counts["failures"] += 1
        error_code = "dining_judge_input_incomplete"
        records.append((None, "_run", None, None, None, error_code, {"item_ids": sorted(set(rule_of) - planned_ids)}))
    for plan in plans:
        counts["days"] += 1
        try:
            budget = deadline_s
            if lifecycle:
                remaining = (datetime.fromisoformat(metadata["deadline_at"]) - datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    raise TimeoutError("dining judge deadline exceeded")
                budget = min(deadline_s, remaining)
            tools = tools_factory(connect)
            result = judge_day(plan, tools=tools, chat=chat, deadline_s=budget)
            if not isinstance(result.items, list) or not isinstance(result.tool_calls, list):
                raise ValueError("malformed agent result")
            records.append((None, "_run", None, None, None, result.failure,
                            {"date": plan["date"], **result.stats,
                             "customer_requests": result.requests,
                             "tools": [c["tool"] for c in result.tool_calls if isinstance(c, dict) and "tool" in c],
                             # ☆`result.tool_calls` 는 도구 결과를 싣지 않는다 — 결과가 있는 도구 기록에서 센다.
                             #   후보 기록은 부가 정보라 기록이 없는 도구 묶음이어도 판정을 실패로 만들지 않는다
                             "outside_ledger": outside_ledger(getattr(tools, "calls", None) or [])}))
            if result.failure:
                counts["failures"] += 1
                error_code = error_code or str(result.failure)
                continue
            answered: dict[str, set[str]] = defaultdict(set)
            for item in result.items:
                if not isinstance(item, dict) or not isinstance(item.get("checks"), list):
                    raise ValueError("malformed item checks")
                item_id = str(item.get("item_id"))
                if item_id not in rule_of:
                    continue
                for check in item["checks"]:
                    if not isinstance(check, dict):
                        raise ValueError("malformed check")
                    code, verdict = check.get("check"), check.get("verdict")
                    rule = rule_of[item_id].get(code)
                    counts["checks"] += 1
                    failure = check.get("failure")
                    evidence = check.get("evidence")
                    if (code not in CHECKS or verdict not in VERDICTS or not isinstance(evidence, list)
                            or any(not isinstance(ev, dict) for ev in (evidence or []))
                            or (verdict in ("ok", "bad") and not evidence)
                            or ("required" in check and not isinstance(check["required"], bool))):
                        failure = failure or "malformed_check"
                    records.append((item_id, str(code), verdict if verdict in VERDICTS else None, rule,
                                    (verdict == rule) if rule is not None else None, failure,
                                    {k: check.get(k) for k in ("why_chosen", "reason", "evidence", "claimed_verdict", "claimed_check",
                                                               "required", "request_id", "customer_request")
                                     if check.get(k) is not None}))
                    if failure is not None:
                        if code in AVAILABILITY_CHECKS or check.get("required") is True:
                            counts["failures"] += 1
                            error_code = error_code or str(failure)
                        continue
                    answered[item_id].add(code)
                    counts["used"] += 1
                    decided.setdefault(item_id, []).append(
                        {"check": code, "verdict": verdict, "evidence": _tools_of(check, result.tool_calls),
                         "validated": True,
                         "customer_request": check.get("customer_request"),
                         "required": is_required(check)})
            gaps = {(str(gap["item_id"]), gap["check"], gap.get("request_id"), gap.get("failure")): gap
                    for gap in result.missing}
            if lifecycle:
                # AgentResult 자체가 잘못 구성돼 missing을 누락하더라도 필수 확인을 성공으로 세지 않는다.
                for planned in plan["items"]:
                    if planned.get("kind") != "dining":
                        continue
                    item_id = str(planned["item_id"])
                    need = {"found"} | ({"open_at"} if planned.get("start") else set())
                    for code in need - answered[item_id]:
                        if not any(key[:2] == (item_id, code) for key in gaps):
                            gaps[(item_id, code, None, "missing_required_check")] = {"failure": "missing_required_check"}
            for (item_id, code, _, _), gap in gaps.items():
                failure = gap.get("failure") or "missing_required_check"
                counts["missing"] += 1
                error_code = error_code or str(failure)
                records.append((item_id, code, None, rule_of.get(item_id, {}).get(code), None, failure,
                                {k: gap[k] for k in ("attribute", "request_id", "quote", "required", "item_ids") if k in gap}))
        except Exception as exc:                         # noqa: BLE001 — 상태를 failed로 닫되 앞서 확인한 줄은 보존한다
            counts["failures"] += 1
            failure = "dining_judge_deadline_exceeded" if isinstance(exc, TimeoutError) else "dining_judge_execution_failed"
            error_code = error_code or failure
            records.append((None, "_run", None, None, None, failure, {"date": plan["date"], "error_type": type(exc).__name__}))
            log.warning("dining judge day failed intake=%s revision=%s date=%s", intake_id, revision, plan["date"], exc_info=True)

    def apply(current):
        merged, counts["changed"] = merge(current, decided)
        merged["agent_judged"] = {"run_id": run_id, "model": model, "changed_rows": counts["changed"]}
        return merged

    with connect() as conn, conn.transaction():
        record(conn, records)
        if lifecycle:
            from app.domains.travel_ops.components.intake import dining_review

            current = dining_review.finish(conn, tenant_id, intake_id, revision, run_id,
                                           error_code=error_code, update=apply)
            if current is None or current["dining_judge"].get("error_code") == "dining_judge_input_changed":
                counts["stale"] = 1
        elif decided:
            # 옛 독립 호출도 잠금 뒤에 읽는다. 신규 접수의 tokenless 작업은 현재 토큰을 덮을 수 없다.
            state = review_module.intake_state(conn, tenant_id, intake_id)
            current = review_module.load(conn, tenant_id, intake_id, revision)
            if current and state == ("review", revision) and not current.get("dining_judge"):
                review_module.store(conn, tenant_id, intake_id, revision, apply(current))
            else:
                counts["stale"] = 1
        if counts["stale"]:
            record(conn, [(None, "_stale", None, None, None, "intake_moved_on", {})])
    return {"run_id": run_id, **counts}


__all__ = ["ADDED", "RULE_ROWS", "ROW_OF", "TEXT", "merge", "outside_ledger", "plans_from_review", "rule_verdicts", "run"]
