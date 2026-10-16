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
#: 체크마다 근거가 될 수 있는 도구 — ok · bad 판정은 이 중 하나의 결과를 근거로 들어야 한다
#: ☆`[2026-10-16]` 이 표가 없을 때 「가게를 찾았다」(find_place 의 ok)를 근거로 든 「영업 가능」이 통과했다(같은 날 휴무 도구는 bad)
#:   place_detail 은 규칙 도구가 unknown 일 때 원문을 읽는 길(SYSTEM 규칙 4) · 직접 계산 비교 실험(`DIRECT_RULES`)의 근거다
CHECK_TOOLS = {
    "found": frozenset({"find_place", "map_search"}),
    "open_at": frozenset({"check_open_at", "live_open_check", "place_detail"}),
    "closed_day": frozenset({"check_closed_day", "place_detail"}),
    "business": frozenset({"check_business", "place_detail"}),
    "dietary": frozenset({"check_attributes"}),
    "kids": frozenset({"check_attributes"}),
    "payment": frozenset({"check_attributes"}),
}
#: 「ok」를 막는 규칙 도구 — 같은 가게 · 같은 시각(날)에 이 중 하나라도 bad 면, 인용하지 않았어도 ok 는 모순이다
#:   (그날 휴무 · 폐업이면 그 시각에 영업할 수 없다)
_BLOCKERS = {
    "open_at": frozenset({"check_open_at", "live_open_check", "check_closed_day", "check_business"}),
    "closed_day": frozenset({"check_closed_day", "check_business"}),
    "business": frozenset({"check_business"}),
}
#: 속성 체크 → 근거가 될 속성(`check_attributes` 결과의 `attributes.<속성>.state`)
#: ☆`[2026-10-16]` 도구 종류만 보던 때 `halal.state = "no"` 를 인용한 식단 ok · 아이 동반만 인용한 식단 ok 가 통과했다
_CHECK_ATTRIBUTES = {"dietary": frozenset({"halal", "vegetarian"}), "kids": frozenset({"kids"}), "payment": frozenset({"card"})}
#: 속성 상태 → 판정. limited 는 「조건부 가능」이라 가능으로 본다(`dining.attribute_state` 205 와 같다)
_ATTRIBUTE_VERDICT = {"yes": "ok", "limited": "ok", "no": "bad", "unknown": "unknown"}
DEFAULT_MAX_TURNS = 10
#: ★`[2026-10-16 실제 접수 그림자]` 턴 상한 = max(DEFAULT_MAX_TURNS, TURNS_BASE + TURNS_PER_MEAL × 식사 수) — 식당 4곳인 날이 10턴에 걸려
#:  판정이 통째로 실패했다. 식사 하나에 「찾기 · 영업 · 휴무」를 한두 턴에 묶어 부른다(실측). ★우리가 고른 값 — 시간 상한(deadline)이 따로 막는다
TURNS_BASE = 4
TURNS_PER_MEAL = 2
#: 마지막 답 턴에 보내는 말 — 도구 없이 지금까지로 답하게 한다
FINAL_TURN = "도구를 더 부르지 말고, 지금까지 부른 도구 결과만으로 지정한 JSON 하나로 답하라. 확인하지 못한 체크는 넣지 않는다."
DEFAULT_DEADLINE_S = 120.0

SYSTEM = """너는 여행 일정의 식사 항목을 점검하는 요식 담당이다.
그날 일정 전체를 보고, 식사 항목마다 고객이 그 시각 그 식당에서 문제없이 먹을 수 있는지 확인할 항목을 직접 골라 도구로 확인한다.

규칙
1. 식사 항목(kind=dining)마다 먼저 find_place 로 가게를 특정한다(place_uid 가 주어졌으면 생략해도 된다).
   find_place 가 found=true 를 주면 그 가게로 정해진 것이다 — verdict 가 unknown(「다르면 고쳐 주세요」 · 확인 필요)이어도 다시 찾지 않는다.
   그 place_uid 로 확인을 이어 가고, found 체크는 그 verdict(unknown) 그대로 적는다. 다시 찾기는 found=false(못 찾음)일 때만 다른 말로 한 번.
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
    #: 계획의 식사 항목인데 답에 없거나(missing_item) 필수 체크(found · 시각이 있으면 open_at)가 빠진 것(missing_check)
    missing: list[dict[str, Any]] = field(default_factory=list)


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


def _minute(value: Any) -> str:
    """시각을 분까지 — 「2026-10-25 12:00」 · 「2026-10-25T12:00:00+09:00」 를 같게 본다."""
    return str(value).strip().replace(" ", "T")[:16]


def _same_time(call: dict[str, Any], start: str | None, end: str | None = None) -> bool:
    """그 호출이 이 항목의 시각(날)을 물은 것인가. 시각 인자가 없는 도구(폐업 · 속성)는 늘 같다."""
    args = call.get("args") or {}
    if "start" in args and (start is None or _minute(args["start"]) != _minute(start)):
        return False
    if args.get("end") and end and _minute(args["end"]) != _minute(end):
        return False
    # ★`[2026-10-16 구조 리뷰 P2]` 끝 시각이 있는 식사는 끝까지 물은 호출만 그 구간의 근거다 — 시작 시각만 물은 영업 조회(ok)가
    #   12:00~13:00 식사 전체의 「영업」으로 통과했다(11:00~12:30 가게 · 실제 SQL 재현)
    if end and "start" in args and not args.get("end"):
        return False
    if args.get("date") and (start is None or str(args["date"])[:10] != _minute(start)[:10]):
        return False
    return True


def _same_slot(call: dict[str, Any], place_uid: str, start: str | None) -> bool:
    """그 호출이 이 항목의 가게 · 시각(날)을 물은 것인가."""
    return (call.get("args") or {}).get("place_uid") == place_uid and _same_time(call, start)


def validate_check(check: dict[str, Any], tools: DiningTools, *, place_uid: str | None = None,
                   start: str | None = None, end: str | None = None) -> str | None:
    """체크 하나의 근거를 검증한다. 문제없으면 None, 있으면 이유 이름(§6).

    `place_uid` · `start` · `end` 는 그 식사 항목의 가게 · 시작 · 끝 시각 — 주면 남의 가게나 다른 시각(날)을 물은 근거를 거절하고,
    인용하지 않은 같은 가게 · 같은 시각(날)의 규칙 도구 bad 와 어긋나는 ok 도 거절한다."""
    if check.get("check") not in CHECKS:
        return "unknown_check"
    if check.get("verdict") not in VERDICTS:
        return "bad_verdict"
    evidence = check.get("evidence")
    if not isinstance(evidence, list):
        return "evidence_not_list"
    if check["verdict"] != "unknown" and not evidence:
        return "no_evidence"
    rule_verdicts, cited_tools, attribute_verdicts = [], set(), []
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
        if place_uid and (call.get("args") or {}).get("place_uid") not in (None, place_uid):
            return "evidence_other_place"
        if start and not _same_time(call, start, end):
            return "evidence_other_time"
        cited_tools.add(call["tool"])
        parts = str(ev.get("path", "")).split(".")
        if (call["tool"] == "check_attributes" and len(parts) >= 2 and parts[0] == "attributes"
                and parts[1] in _CHECK_ATTRIBUTES.get(check["check"], ())):
            state = ((call["result"].get("attributes") or {}).get(parts[1]) or {}).get("state")
            attribute_verdicts.append(_ATTRIBUTE_VERDICT.get(str(state), "unknown"))
        if SPECS[call["tool"]].kind == "rule" and ev.get("path") == "verdict":
            rule_verdicts.append(_RULE_VERDICT.get(str(value), "unknown"))
    if check["verdict"] != "unknown" and not cited_tools & CHECK_TOOLS[check["check"]]:
        return "evidence_wrong_tool"             # 이 체크를 판정하는 도구의 결과가 근거에 없다
    if check["check"] in _CHECK_ATTRIBUTES and check["verdict"] != "unknown":
        if not attribute_verdicts:
            return "evidence_wrong_attribute"    # 이 체크의 속성(식단이면 할랄 · 채식)을 인용하지 않았다
        if (check["verdict"] == "ok" and any(v != "ok" for v in attribute_verdicts)) or                 (check["verdict"] == "bad" and "bad" not in attribute_verdicts):
            return "contradicts_attribute"       # 인용한 속성 값과 판정이 어긋난다(no 인데 ok · yes 인데 bad)
    known = [v for v in rule_verdicts if v != "unknown"]
    if known and check["verdict"] != "unknown" and check["verdict"] not in known:
        return "contradicts_rule_tool"           # 규칙 도구가 bad 라고 했는데 ok 라고 판정
    if check["verdict"] == "ok" and place_uid:
        for call in tools.calls:                 # 인용하지 않은 같은 가게 · 같은 시각의 bad 도 본다
            if (call["tool"] in _BLOCKERS.get(check["check"], ()) and _same_slot(call, place_uid, start)
                    and _RULE_VERDICT.get(str((call.get("result") or {}).get("verdict"))) == "bad"):
                return "contradicts_rule_tool"
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


def turn_limit_for(plan: dict[str, Any]) -> int:
    """그날 턴 상한 — 식사가 많을수록 늘린다(최소 `DEFAULT_MAX_TURNS`)."""
    meals = sum(1 for i in plan.get("items") or [] if isinstance(i, dict) and i.get("kind") == "dining")
    return max(DEFAULT_MAX_TURNS, TURNS_BASE + TURNS_PER_MEAL * meals)


def _spot(args: dict[str, Any]) -> tuple[float, float] | None:
    """찾기 인자의 자리(좌표) — 같은 일정 항목의 다시 찾기를 알아보는 열쇠. 좌표가 없으면 None(가리지 않는다)."""
    try:
        return (round(float(args["lat"]), 5), round(float(args["lng"]), 5))
    except (KeyError, TypeError, ValueError):
        return None


def _bare(name: str) -> str:
    import re

    return re.sub(r"\[[^\]]*\]|\([^)]*\)|\s+", "", name or "")


def _earlier_find(found: list[tuple[str, dict[str, Any]]], query: str) -> dict[str, Any] | None:
    """같은 자리에서 이미 찾은 결과 중 **이 이름과 이어지는** 것 — 물은 이름이나 찾은 가게 이름이 새 이름을 통째로 품거나 그 안에 든다
    (「하동관 명동 본점 명동9길」 ⊃ 「하동관」). 이어지지 않으면 None(다른 가게일 수 있으니 찾는다)."""
    new = _bare(query)
    if len(new) < 2:
        return None
    for asked, result in found:
        for known in (_bare(asked), _bare(str(result.get("name") or ""))):
            if len(known) >= 2 and (known in new or new in known):
                return result
    return None


def judge_day(plan: dict[str, Any], *, tools: DiningTools, chat: Any, max_turns: int | None = None,
              deadline_s: float = DEFAULT_DEADLINE_S, clock: Callable[[], float] = time.perf_counter,
              mode: str = "rule_tools") -> AgentResult:
    """그날 일정(`plan`)의 식사 항목을 판정한다.

    plan = {"date": "YYYY-MM-DD", "customer_notes": "고객 문장(없으면 빈 글)",
            "items": [{"item_id", "seq", "kind", "title", "start", "end", "place": {"name", "place_uid"?, "lat"?, "lng"?}}]}
    """
    started = clock()
    if max_turns is None:
        max_turns = turn_limit_for(plan)
    if mode not in ("rule_tools", "llm_direct"):
        raise ValueError(f"모르는 방식: {mode}")
    system = SYSTEM if mode == "rule_tools" else SYSTEM + DIRECT_RULES
    if mode == "llm_direct":
        tools.allowed = DIRECT_TOOLS
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": _plan_text(plan)}]
    specs = openai_tools(sorted(tools.allowed) if tools.allowed is not None else None)
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    turns, final_text, failure = 0, None, None
    found_at: dict[tuple[float, float], list[tuple[str, dict[str, Any]]]] = {}   # 자리 → [(찾은 이름, 결과)]
    while True:
        if turns >= max_turns:
            failure = "turn_limit"
            break
        if clock() - started > deadline_s:
            failure = "deadline"
            break
        # ★`[2026-10-16 실제 접수 그림자 2차]` 마지막 한 턴은 **답 턴** — 도구 없이 지금까지 부른 결과로 JSON 을 내게 한다.
        #   ☆묻지 않은 확인(폐업 · 카드 · 할랄)을 한두 개씩 부르다 상한에 걸려 그날 판정이 통째로 사라졌다(기록 0건).
        #   빠진 필수 확인은 따로 센다(`missing`). 답 턴에도 도구를 부르면 그대로 `turn_limit` 이다
        last = turns == max_turns - 1
        try:
            if last:
                messages.append({"role": "user", "content": FINAL_TURN})
                turn = chat.step(messages, [], final_json=True)
            else:
                turn = chat.step(messages, specs)
        except Exception as exc:                          # noqa: BLE001 — 모델 실패는 판정 실패로 기록한다(그림자 단계)
            failure = f"model_error:{type(exc).__name__}"
            break
        turns += 1
        if last and turn.tool_calls:
            failure = "turn_limit"
            for key in usage:
                usage[key] += int(turn.usage.get(key, 0))
            break
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
            spot = _spot(call["arguments"] or {}) if call["name"] == "find_place" else None
            earlier = _earlier_find(found_at.get(spot) or [], str((call["arguments"] or {}).get("name") or ""))
            if earlier is not None:
                # ★`[2026-10-16]` 이미 찾은 가게를 이름만 바꿔 다시 찾지 않는다 — 도구를 부르지 않고 앞 결과를 돌려준다(코드가 막는다).
                #   ★구조 리뷰 P2: 같은 자리라도 **이름이 이어지는** 다시 찾기만 막는다 — 시장처럼 한 좌표의 다른 식당(시장김밥 · 시장칼국수)은 따로 찾는다
                result = {**earlier, "repeat": "이미 찾았다 — 다시 찾지 않는다. 이 place_uid 로 확인을 이어 간다"}
            else:
                result = tools.call(call["name"], call["arguments"])
                if spot is not None and result.get("found") is True:
                    found_at.setdefault(spot, []).append((str((call["arguments"] or {}).get("name") or ""), result))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})

    final = _parse_final(final_text) if failure is None else None
    if failure is None and final is None:
        failure = "final_not_json"
    plan_items = {str(i.get("item_id")): i for i in plan.get("items") or [] if isinstance(i, dict)}
    items, skipped, failures, unknown_items = [], [], 0, 0
    for item in (final or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        planned = plan_items.get(str(item.get("item_id")))
        if planned is None:
            unknown_items += 1                       # 계획에 없는 항목 id — 판정으로 받지 않고 센다
            continue
        place = item.get("place") if isinstance(item.get("place"), dict) else None
        place_failure = validate_place(place, tools)
        place_uid = (place or {}).get("place_uid") or (planned.get("place") or {}).get("place_uid")
        checks = []
        for check in item.get("checks") or []:
            if not isinstance(check, dict):
                continue
            why = place_failure or validate_check(check, tools, place_uid=place_uid, start=planned.get("start"),
                                                  end=planned.get("end"))
            if why:
                failures += 1
                check = {**check, "verdict": "unknown", "failure": why, "claimed_verdict": check.get("verdict")}
            checks.append(check)
        same = next((i for i in items if str(i["item_id"]) == str(item.get("item_id"))), None)
        if same is not None:                         # ☆`[2026-10-16]` 같은 항목을 나눠 내면 뒤의 것이 앞의 체크를 덮었다 — 합친다
            same["checks"] += checks
            same["place"] = same["place"] or place
            continue
        items.append({"item_id": item.get("item_id"), "place": place, "checks": checks})
    for skip in (final or {}).get("skipped") or []:
        if isinstance(skip, dict):
            skipped.append(skip)
    # ★필수 체크(SYSTEM 규칙 2) — 식사마다 found, 시각이 있으면 open_at. 빠지면 조용히 넘기지 않고 센다
    #  ☆`[2026-10-16]` 식사가 있는 날 빈 답(`items: []`)이 실패 없이 「검사 0건」으로 끝났다
    missing: list[dict[str, Any]] = []
    if failure is None:
        answered = {str(i["item_id"]): {c.get("check") for c in i["checks"]} for i in items}
        for item_id, planned in plan_items.items():
            if planned.get("kind") != "dining":
                continue
            need = ["found"] + (["open_at"] if planned.get("start") else [])
            why = "missing_item" if item_id not in answered else "missing_check"
            missing += [{"item_id": item_id, "check": c, "failure": why} for c in need if c not in answered.get(item_id, ())]
        dining_ids = [k for k, p in plan_items.items() if p.get("kind") == "dining"]
        if dining_ids and not any(answered.get(k) for k in dining_ids):
            failure = "empty_result"                 # 식사가 있는데 어느 식사에도 체크가 없다(빈 답 · 항목만 있고 checks 가 빈 것)
    stats = {"turns": turns, "tool_calls": len(tools.calls), "refused": len(tools.refused),
             "validation_failures": failures, "missing_checks": len(missing), "unknown_items": unknown_items,
             "seconds": round(clock() - started, 2), **usage}
    return AgentResult(items=items, skipped=skipped, stats=stats, failure=failure, raw_final=final_text,
                       tool_calls=[{"id": c["id"], "tool": c["tool"], "args": c["args"]} for c in tools.calls],
                       missing=missing)


__all__ = ["AgentResult", "CHECKS", "CHECK_TOOLS", "DIRECT_TOOLS", "SYSTEM", "judge_day", "turn_limit_for", "validate_check", "validate_place"]
