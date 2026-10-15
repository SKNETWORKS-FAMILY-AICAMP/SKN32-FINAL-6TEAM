# -*- coding: utf-8 -*-
"""요식 판정 에이전트 — LLM이 **무엇을 확인할지 고르고 도구를 불러** 식사 항목을 판정한다. 서버는 근거를 검증한다. `[2026-10-13 · 설계 §3 · §4 · §6]`

★에이전트다 — 다음에 무엇을 할지(어느 도구를 몇 번, 언제 끝낼지)를 **모델이** 정한다. 코드가 정하는 것은 울타리뿐이다:
    도구는 읽기 전용(`agent_tools.DiningTools`) · 도구 호출 상한 · 모델 턴 상한 · 시간 상한 · 최종 답의 근거 검증.
★LLM은 지휘, 규칙은 도구 — 영업 · 휴무 · 라스트오더 · 속성은 규칙 도구의 판정을 **인용**한다(다시 계산하지 않는다).
  규칙 도구가 unknown 이면 원문(`place_detail`)을 읽고 스스로 판정할 수 있다 — 그때도 읽은 원문을 근거로 단다.
★근거 검증(§6) — 인용한 `call_id` 가 이번 실행의 실제 호출인가 · `path` 의 값이 그 결과에 **그대로** 있는가 · 규칙 도구의 판정과
  모순되지 않는가 · 가게 번호가 도구 결과에서 온 것인가. 어기면 그 체크는 「unknown(검증 실패)」 — 조용히 고치지 않고 센다.
★모델 · 도구는 부르는 쪽이 넣는다(`chat.step(messages, tools)` — `infrastructure/llm/tool_chat`). 이 파일은 팀 경계라 바깥 코드를 import 하지 않는다.
★아직 **그림자 단계**다 — 이 결과로 일정을 바꾸지 않는다(설계 §9-5). 지금 규칙 판정과 나란히 기록 · 평가만 한다.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.domains.travel_ops.instances.dining.agent_tools import SPECS, DiningTools, openai_tools

#: 체크리스트(설계 §7) — 에이전트가 고를 수 있는 체크
#: ☆`[2026-10-13 실측]` 처음 이름(open_at_slot · closed_business)과 도구 이름이 달라 gpt-4o-mini 가 「business」 「attributes」 같은 이름을 지어 썼다
#:   (검증기가 4건을 거절) — 체크 이름을 도구 이름에 맞추고, 속성은 무엇을 보는지로 나눴다
CHECKS = {
    "found": "가게를 하나로 특정했나 — find_place",
    "open_at": "그 시각에 영업하나(브레이크 · 라스트오더 포함) — check_open_at",
    "closed_day": "그날 휴무인가 — check_closed_day",
    "business": "폐업 · 이전 상태 — check_business",
    "dietary": "할랄 · 채식 — check_attributes(halal · vegetarian). 고객이 요청했을 때만",
    "kids": "아이 동반 — check_attributes(kids). 아이와 함께일 때만",
    "payment": "카드 결제 — check_attributes(card). 결제 조건이 있을 때만",
}
VERDICTS = ("ok", "bad", "unknown")
#: 규칙 도구의 판정 값 → 체크 판정(구글은 open/closed)
_RULE_VERDICT = {"ok": "ok", "bad": "bad", "open": "ok", "closed": "bad", "unknown": "unknown"}
DEFAULT_MAX_TURNS = 10
DEFAULT_DEADLINE_S = 120.0

SYSTEM = """너는 여행 일정의 식사 항목을 점검하는 요식 담당이다.
그날 일정 전체를 보고, 식사 항목마다 고객이 그 시각 그 식당에서 문제없이 먹을 수 있는지 확인할 항목을 직접 골라 도구로 확인한다.

규칙
1. 식사 항목(kind=dining)마다 먼저 find_place 로 가게를 특정한다(place_uid 가 주어졌으면 생략해도 된다). 못 찾거나 애매하면 다른 말로 한 번 더 찾을 수 있다(최대 2번).
2. 시각이 있는 식사 항목마다 found 와 open_at 은 반드시 판정해 checks 에 넣는다(가게를 이미 알아도 found 를 넣는다).
   그 밖의 체크는 체크리스트에서 이 항목에 필요한 것만 고른다. 필요 없는 체크는 하지 않는다 — 고객이 요청하지 않은 식이 조건 · 아이 · 결제는 보지 않는다.
   check 값은 반드시 아래 이름 중 하나다(다른 이름을 만들지 않는다). 체크 하나에 판정 하나.
{checks}
3. 영업 · 휴무 · 폐업 · 속성은 규칙 도구(check_*)를 불러 그 판정을 그대로 쓴다. 다시 계산하지 않는다.
4. 규칙 도구가 unknown 이면 place_detail 의 원문을 읽고 판정할 수 있다. 그래도 모르면 unknown 이다. 지어내지 않는다.
5. 값은 반드시 도구 결과에서만 가져온다. evidence 에는 도구 결과의 call_id 와 그 결과 안의 경로(path, 점으로 잇는다 예: verdict · attributes.halal.state)와 그 값(value)을 그대로 적는다.
6. 확인이 끝나면 도구를 더 부르지 말고 아래 JSON 하나로만 답한다.

{{"items": [{{"item_id": "...", "place": {{"place_uid": "... 또는 null", "call_id": "find_place 의 call_id 또는 null"}},
  "checks": [{{"check": "체크 이름", "why_chosen": "고른 이유 한 줄", "verdict": "ok|bad|unknown", "reason": "한 문장",
              "evidence": [{{"call_id": "c2", "path": "verdict", "value": "ok"}}]}}]}}],
 "skipped": [{{"item_id": "식사 항목 id", "check": "체크리스트의 이름", "why": "안 본 이유"}}]}}
식사가 아닌 항목(활동 · 이동)은 items 에도 skipped 에도 넣지 않는다.
""".format(checks="\n".join(f"   - {k}: {v}" for k, v in CHECKS.items()))


#: 비교 실험 A — 규칙 도구 없이 원문 · 구간을 읽고 LLM이 직접 판정한다(학습 목적의 비교 · 운영 기본 아님, 설계 §7)
DIRECT_TOOLS = frozenset({"find_place", "place_detail", "check_attributes"})
DIRECT_RULES = """
[이번 판정의 방식 — 직접 계산]
규칙 도구(check_open_at · check_closed_day · check_business)는 쓸 수 없다. 영업 · 휴무는 place_detail(date 를 넣는다)의
intervals(그날 영업 구간 · 라스트오더)와 hours_text · closure_text 원문을 읽고 직접 판정한다.
- open_at: 식사 시작~끝이 그날 영업 구간 하나 안에 들어가면 ok, 아니면 bad(휴무 · 브레이크 · 영업시간 밖). 라스트오더가 있으면 시작 + 20분이 라스트오더를 넘으면 bad.
  intervals 가 비어 있고 휴무 원문에 그 요일이 있으면 bad, 둘 다 없으면 unknown.
- evidence 는 place_detail 결과의 경로(예: intervals.0.close · closure_text.0)와 값을 그대로 적는다.
"""


@dataclass
class AgentResult:
    items: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    stats: dict[str, Any]
    failure: str | None = None             # 판정 전체가 안 됐을 때(턴 · 시간 상한, 최종 답을 못 읽음)
    raw_final: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _get(result: Any, path: str) -> tuple[bool, Any]:
    """점 경로로 값을 꺼낸다(목록은 숫자). (있나, 값)."""
    node = result
    for part in [p for p in str(path).split(".") if p != ""]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return False, None
    return True, node


def _same(a: Any, b: Any) -> bool:
    if isinstance(b, bool) or isinstance(a, bool):
        return str(a).strip().lower() in {str(b).lower(), {True: "true", False: "false"}.get(b, "")}
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    norm = lambda x: re.sub(r"\s+", "", json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x))  # noqa: E731
    return norm(a) == norm(b)


def validate_check(check: dict[str, Any], tools: DiningTools) -> str | None:
    """체크 하나의 근거를 검증한다. 문제없으면 None, 있으면 이유 이름(§6)."""
    if check.get("check") not in CHECKS:
        return "unknown_check"
    if check.get("verdict") not in VERDICTS:
        return "bad_verdict"
    evidence = check.get("evidence")
    if not isinstance(evidence, list):
        return "evidence_not_list"
    if check["verdict"] != "unknown" and not evidence:
        return "no_evidence"
    rule_verdicts = []
    for ev in evidence:
        if not isinstance(ev, dict):
            return "evidence_bad_shape"
        call = next((c for c in tools.calls if c["id"] == ev.get("call_id")), None)
        if call is None:
            return "evidence_unknown_call"
        found, value = _get(call["result"], ev.get("path", ""))
        if not found:
            return "evidence_path_missing"
        if not _same(ev.get("value"), value):
            return "evidence_value_mismatch"
        if SPECS[call["tool"]].kind == "rule" and ev.get("path") == "verdict":
            rule_verdicts.append(_RULE_VERDICT.get(str(value), "unknown"))
    known = [v for v in rule_verdicts if v != "unknown"]
    if known and check["verdict"] != "unknown" and check["verdict"] not in known:
        return "contradicts_rule_tool"           # 규칙 도구가 bad 라고 했는데 ok 라고 판정
    return None


def validate_place(place: dict[str, Any] | None, tools: DiningTools) -> str | None:
    """고른 가게 번호가 도구 결과에서 온 것인가(원장 · 지도 결과에 없는 가게를 고르지 못한다)."""
    uid = (place or {}).get("place_uid")
    if not uid:
        return None
    blob = json.dumps([c["result"] for c in tools.calls], ensure_ascii=False)
    return None if f'"{uid}"' in blob else "place_not_from_tools"


def _plan_text(plan: dict[str, Any]) -> str:
    return json.dumps(plan, ensure_ascii=False)


def _parse_final(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except ValueError:
        return None
    return value if isinstance(value, dict) and isinstance(value.get("items"), list) else None


def judge_day(plan: dict[str, Any], *, tools: DiningTools, chat: Any, max_turns: int = DEFAULT_MAX_TURNS,
              deadline_s: float = DEFAULT_DEADLINE_S, clock: Callable[[], float] = time.perf_counter,
              mode: str = "rule_tools") -> AgentResult:
    """그날 일정(`plan`)의 식사 항목을 판정한다.

    plan = {"date": "YYYY-MM-DD", "customer_notes": "고객 문장(없으면 빈 글)",
            "items": [{"item_id", "seq", "kind", "title", "start", "end", "place": {"name", "place_uid"?, "lat"?, "lng"?}}]}
    """
    started = clock()
    if mode not in ("rule_tools", "llm_direct"):
        raise ValueError(f"모르는 방식: {mode}")
    system = SYSTEM if mode == "rule_tools" else SYSTEM + DIRECT_RULES
    if mode == "llm_direct":
        tools.allowed = DIRECT_TOOLS
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": _plan_text(plan)}]
    specs = openai_tools(sorted(tools.allowed) if tools.allowed is not None else None)
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    turns, final_text, failure = 0, None, None
    while True:
        if turns >= max_turns:
            failure = "turn_limit"
            break
        if clock() - started > deadline_s:
            failure = "deadline"
            break
        try:
            turn = chat.step(messages, specs)
        except Exception as exc:                          # noqa: BLE001 — 모델 실패는 판정 실패로 기록한다(그림자 단계)
            failure = f"model_error:{type(exc).__name__}"
            break
        turns += 1
        for key in usage:
            usage[key] += int(turn.usage.get(key, 0))
        if not turn.tool_calls:
            final_text = turn.content
            if _parse_final(final_text) is None and turns < max_turns:
                # ☆`[2026-10-13 실측]` gpt-4o-mini 가 식사 둘인 날(DG-013)에 JSON 대신 글로 끝냈다 — 한 번만 JSON 형식을 강제해 다시 묻는다
                messages += [turn.as_message(), {"role": "user", "content": "위 판정을 지정한 JSON 하나로만 다시 답하라."}]
                try:
                    again = chat.step(messages, [], final_json=True)
                    turns += 1
                    for key in usage:
                        usage[key] += int(again.usage.get(key, 0))
                    final_text = again.content
                except Exception as exc:                  # noqa: BLE001
                    failure = f"model_error:{type(exc).__name__}"
            break
        messages.append(turn.as_message())
        for call in turn.tool_calls:
            result = tools.call(call["name"], call["arguments"])
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})

    final = _parse_final(final_text) if failure is None else None
    if failure is None and final is None:
        failure = "final_not_json"
    items, skipped, failures = [], [], 0
    for item in (final or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        place = item.get("place") if isinstance(item.get("place"), dict) else None
        place_failure = validate_place(place, tools)
        checks = []
        for check in item.get("checks") or []:
            if not isinstance(check, dict):
                continue
            why = place_failure or validate_check(check, tools)
            if why:
                failures += 1
                check = {**check, "verdict": "unknown", "failure": why, "claimed_verdict": check.get("verdict")}
            checks.append(check)
        items.append({"item_id": item.get("item_id"), "place": place, "checks": checks})
    for skip in (final or {}).get("skipped") or []:
        if isinstance(skip, dict):
            skipped.append(skip)
    stats = {"turns": turns, "tool_calls": len(tools.calls), "refused": len(tools.refused),
             "validation_failures": failures, "seconds": round(clock() - started, 2), **usage}
    return AgentResult(items=items, skipped=skipped, stats=stats, failure=failure, raw_final=final_text,
                       tool_calls=[{"id": c["id"], "tool": c["tool"], "args": c["args"]} for c in tools.calls])


__all__ = ["AgentResult", "CHECKS", "DIRECT_TOOLS", "SYSTEM", "judge_day", "validate_check", "validate_place"]
