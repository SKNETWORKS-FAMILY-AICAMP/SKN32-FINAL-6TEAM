# -*- coding: utf-8 -*-
"""대체 식당 — 규칙이 거른 **상위 3곳 중 하나**를 모델(LLM)이 고른다. `[2026-10-13 사용자 제안 · 설계 §7-2]`

★규칙이 거르고, 모델이 고른다. 후보 찾기 · 탈락 · 순위는 지금 그대로(`replan.dining_candidates` · `choose`).
  셋 다 규칙을 통과했으니 무엇을 골라도 「닫힌 곳 · 늦는 곳」은 안 된다 — 모델이 틀려도 위험이 작다.
★부를 때만 부른다(`should_ask`) — **고객 취향 문장이 있을 때만.** 그때도 규칙 1등과 **같은 동선 등급**(허용 범위 안/밖)인 후보만
  보인다 — 취향 때문에 다음 일정에 더 늦는 곳으로 바꾸지 않는다. 취향 문장이 없으면 규칙 1등 그대로다.
  ☆`[2026-10-13 실측]` 처음에는 「앞 후보끼리 차이가 없고 그날 다른 식사가 있으면」도 불렀다. 취향 없이 늘 부르게 해 기존 동선 평가에 돌리니
  gpt-4o-mini 가 「취향 문장이 없으므로 규칙 1위인 B를 선택」이라 쓰고 **2위(B)를 골라 다음 일정에 늦는 곳**을 냈다(DA-003, 3판 모두) —
  후보 id(A · B · C)를 순위로 착각했다. 그래서 id 를 **규칙 순위 그 자체**(「1」 「2」 「3」)로 바꾸고, 정답지가 없는 「흐름」 조건은 뺐다.
★모델이 낸 답은 서버가 확인한다(`check`) — 고른 id 가 후보 안에 있나 · 인용한 값이 후보 사실과 같은가 ·
  규칙 1등이 아닌 곳을 고르면 그 곳의 사실을 하나 이상 인용했나 · 취향 문장 없이 1등을 바꾸지 않았나.
  하나라도 어기면 **규칙 1등**으로 돌아가고 그 이유를 센다.
★계산 부품이다 — 모델은 부르는 쪽이 넣는다(`make_picker(chat)`, `chat.structured` 를 가진 것: `OllamaChat` · `OpenAIChat`).
  넣지 않으면 지금과 똑같다(규칙 1등).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.planning.meal_likeness import kind_of, style_of

KST = ZoneInfo("Asia/Seoul")
#: 모델에게 보이는 후보 수 — 규칙 1등 + 재요청용 둘(`replan.choose`)
TOP = 3
IDS = ("1", "2", "3")          # ★id = 규칙 순위 — 「규칙 1위」와 id 가 어긋날 수 없게(위 ☆)
#: 고객 취향 문장을 읽는 칸 — 일정의 `constraints`. ★`[2026-10-13]` 새 칸이다. 설문 · 채팅에서 채우는 길은 아직 없다(평가가 넣는다)
PREFERENCE_KEY = "meal_preference"
#: 이유 문장 길이 상한(글자) — 알림 · 기록에 그대로 싣는다
REASON_MAX = 120

LIKENESS_WORDS = {0: "같은 브랜드", 1: "같은 메뉴", 2: "같은 음식 결", 3: "같은 큰 종류", 4: "종류 모름", 5: "다른 종류"}

SYSTEM = (
    "너는 여행 일정의 대체 식당을 고르는 도우미다. 원래 식당에 갈 수 없어 규칙이 후보를 거르고 순위를 매겼다. "
    "후보는 모두 그 시각에 영업하고 일정에 늦지 않는다고 확인됐다.\n"
    "할 일: 후보 중 하나를 고른다.\n"
    "- 고객 취향 문장(customer_preference)이 가장 중요하다. 취향에 맞는 후보가 있으면, 원래 식당과 덜 비슷하거나(likeness_to_original) "
    "조금 더 멀어도 그 후보를 고른다. 규칙 1위가 취향과 어긋나면 규칙 1위를 고르지 않는다.\n"
    "- 후보 id 는 규칙 순위다(\"1\" 이 규칙 1위).\n"
    "- 규칙 1위(id \"1\")를 고르는 때: 아무거나 괜찮다고 했거나 · 원래와 비슷한 곳을 원하거나 · 취향에 맞는 후보가 하나도 없을 때.\n"
    "- 후보 사실에 없는 것을 지어내지 않는다. 고른 이유가 된 사실을 cited 에 그대로 옮긴다(candidate=후보 id, field=칸 이름, value=그 칸의 값).\n"
    "- reason 은 한국어 한 문장, 60자 안쪽.\n"
    "JSON 으로만 답한다."
)


@dataclass(frozen=True)
class MealContext:
    """모델이 볼 그날 맥락 — 계산한 값만."""

    meal_title: str
    starts_at: datetime
    original: Mapping[str, Any]
    day: list[dict[str, Any]] = field(default_factory=list)      # 같은 날 다른 항목(시각 · 종류 · 이름 · 식사면 종류/결)
    preference: str = ""


@dataclass
class Pick:
    best: Any
    alternates: list[Any]
    by: str                         # rule(부르지 않음) · llm · rule_fallback(불렀지만 규칙으로 돌아감)
    reason: str = ""
    cited: list[dict[str, Any]] = field(default_factory=list)
    failure: str | None = None      # rule_fallback 일 때 이유
    seconds: float = 0.0
    asked_ids: list[str] = field(default_factory=list)

    def record(self) -> dict[str, Any]:
        """일정 항목 `detail.meal_pick` 에 싣는 값 — 누가 골랐나 · 왜."""
        return {"by": self.by, **({"reason": self.reason} if self.reason else {}),
                **({"cited": self.cited} if self.cited else {}), **({"failure": self.failure} if self.failure else {})}


MealPicker = Callable[[Any, list[Any], MealContext], Pick]


def preference_of(constraints: Mapping[str, Any] | None) -> str:
    value = (constraints or {}).get(PREFERENCE_KEY)
    return value.strip() if isinstance(value, str) else ""


def _hm(moment: datetime | None) -> str | None:
    return moment.astimezone(KST).strftime("%H:%M") if moment else None


def _route_band(candidate: Any) -> tuple:
    """규칙 순위의 앞 칸 — 시연 순위 · 바뀌는 항목 수 · 요금 모름 · **동선 허용 범위 밖 여부**(`replan.Candidate.rank` 의 [:4]).
    비슷함 등급(다음 칸)은 넣지 않는다 — 취향이 바꾸려는 것이 바로 그것이다."""
    return candidate.rank()[:4]


def should_ask(best: Any, alternates: Sequence[Any], context: MealContext) -> list[Any]:
    """모델에게 보일 후보(규칙 순서). 부를 이유가 없으면 빈 목록 — 취향 문장이 있고, 같은 동선 등급의 후보가 둘 이상일 때만.
    ★늘어난 이동(`added_move_min`)이 1등보다 큰 후보는 뺀다 — 취향은 「무엇을 먹나」를 바꾸지 동선을 나쁘게 하지 않는다.
    ☆`[2026-10-13 실측]` 같은 등급만 걸렀을 때, 모든 시나리오에 「다른 종류로」를 넣은 압박 시험에서 DA-003(다음 일정까지 1.8km — 규칙은 교통으로 보고
      도보로 탈락시키지 않는다)의 2위 남쪽 가게를 골라 다음 일정에 도보로 더 늦었다(3판 모두). 1등보다 이동이 늘지 않는 곳만 보이게 했다."""
    if not context.preference:
        return []
    pool = [c for c in [best, *alternates][:TOP]
            if _route_band(c) == _route_band(best) and c.added_move_min <= best.added_move_min]
    return pool if len(pool) >= 2 else []


def facts(candidate: Any, rule_rank: int) -> dict[str, Any]:
    """후보 하나의 사실 — 모델이 인용할 수 있는 값은 이것뿐이다."""
    place = candidate.place or {}
    attributes = place.get("attributes") or {}
    cuisine = attributes.get("cuisine")
    out: dict[str, Any] = {
        "rule_rank": rule_rank, "name": place.get("name") or candidate.name,
        "kind": kind_of(place), "style": style_of(place),
        "menu": str(cuisine[1]) if isinstance(cuisine, (list, tuple)) and len(cuisine) > 1 else None,
        "category": attributes.get("category") if isinstance(attributes.get("category"), str) else None,
        "walk_from_original_min": candidate.walk_min,
        "added_move_min": candidate.added_move_min,
        "likeness_to_original": LIKENESS_WORDS.get(candidate.likeness),
        "starts_at": _hm(candidate.starts_at),
    }
    if candidate.warnings:
        out["warnings"] = list(candidate.warnings)
    if candidate.card_payment is not None:
        out["card_payment"] = candidate.card_payment
    if attributes.get("price_krw") is not None:
        out["price_krw"] = attributes["price_krw"]
    return {k: v for k, v in out.items() if v is not None}


def _place_brief(place: Mapping[str, Any] | None) -> dict[str, Any]:
    place = place or {}
    attributes = place.get("attributes") or {}
    cuisine = attributes.get("cuisine")
    return {k: v for k, v in {"name": place.get("name"), "kind": kind_of(place), "style": style_of(place),
                              "menu": str(cuisine[1]) if isinstance(cuisine, (list, tuple)) and len(cuisine) > 1 else None
                              }.items() if v is not None}


def prompt(pool: Sequence[Any], context: MealContext) -> tuple[str, dict[str, dict[str, Any]]]:
    table = {IDS[i]: facts(c, i + 1) for i, c in enumerate(pool)}
    body = {"meal": {"title": context.meal_title, "starts_at": _hm(context.starts_at),
                     "original": _place_brief(context.original)},
            "day": context.day, "customer_preference": context.preference or None,
            "candidates": [{"id": key, **value} for key, value in table.items()]}
    return json.dumps(body, ensure_ascii=False), table


def schema(ids: Sequence[str]) -> dict[str, Any]:
    return {"type": "object", "required": ["pick", "reason", "cited"], "properties": {
        "pick": {"type": "string", "enum": list(ids)},
        "reason": {"type": "string"},
        "cited": {"type": "array", "items": {"type": "object", "required": ["candidate", "field", "value"], "properties": {
            "candidate": {"type": "string", "enum": list(ids)}, "field": {"type": "string"}, "value": {}}}}}}


def _same(value: Any, fact: Any) -> bool:
    def norm(x: Any) -> str:
        return str(x).strip().lower().replace(" ", "")
    if isinstance(fact, (list, tuple)):
        return norm(value) in {norm(x) for x in fact} or norm(value) == norm(", ".join(map(str, fact)))
    if isinstance(fact, bool):
        return norm(value) in ({"true", "참", "가능", "yes"} if fact else {"false", "거짓", "불가", "no"})
    return norm(value) == norm(fact)


def check(answer: Mapping[str, Any], table: Mapping[str, Mapping[str, Any]], *, preference: str = "") -> str | None:
    """모델 답을 확인한다. 문제가 없으면 None, 있으면 이유 이름. 취향 문장(`preference`)이 비면 1등을 바꾸는 답은 받지 않는다."""
    pick = answer.get("pick")
    if pick not in table:
        return "pick_not_in_candidates"
    cited = answer.get("cited")
    if not isinstance(cited, list):
        return "cited_not_list"
    for cite in cited:
        if not isinstance(cite, Mapping):
            return "cited_bad_shape"
        row = table.get(cite.get("candidate"))
        if row is None:
            return "cited_unknown_candidate"
        if cite.get("field") not in row:
            return "cited_unknown_field"
        if not _same(cite.get("value"), row[cite.get("field")]):
            return "cited_value_mismatch"
    if table[pick].get("rule_rank") != 1 and not preference.strip():
        return "override_without_preference"
    if table[pick].get("rule_rank") != 1 and not any(c.get("candidate") == pick for c in cited):
        return "uncited_override"
    reason = answer.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return "no_reason"
    return None


def make_picker(chat: Any, *, ask: Callable[[Any, Sequence[Any], MealContext], list[Any]] = should_ask,
                clock: Callable[[], float] = time.perf_counter, num_predict: int = 200) -> MealPicker:
    """`chat.structured(system, user, schema)` 로 고르는 선택기. 실패는 규칙 1등으로 돌아간다(예외를 올리지 않는다 — 대체 계산을 멈추지 않는다).
    `ask` — 부를 조건(기본 `should_ask`). 평가는 「늘 부르기」로 모델 자체의 실력을 잰다."""

    def pick(best: Any, alternates: list[Any], context: MealContext) -> Pick:
        pool = ask(best, alternates, context)
        if not pool:
            return Pick(best=best, alternates=list(alternates), by="rule")
        user, table = prompt(pool, context)
        started = clock()
        try:
            answer = chat.structured(SYSTEM, user, schema(list(table)), num_predict=num_predict)
            failure = check(answer, table, preference=context.preference)
        except Exception as exc:                       # noqa: BLE001 — 모델 실패는 규칙 1등으로. 이유는 남긴다
            answer, failure = {}, f"call_failed:{type(exc).__name__}"
        seconds = round(clock() - started, 3)
        if failure:
            return Pick(best=best, alternates=list(alternates), by="rule_fallback", failure=failure,
                        seconds=seconds, asked_ids=list(table))
        chosen = pool[IDS.index(answer["pick"])]
        ordered = [best, *alternates]
        rest = [c for c in ordered if c is not chosen]
        return Pick(best=chosen, alternates=rest[:TOP - 1], by="llm", reason=answer["reason"].strip()[:REASON_MAX],
                    cited=list(answer.get("cited") or []), seconds=seconds, asked_ids=list(table))

    return pick


def day_context(items: Sequence[Any], meal: Any, preference: str = "") -> MealContext:
    """같은 날 다른 항목을 맥락으로 — 시각 · 종류 · 이름, 식사면 종류 · 결도."""
    day = meal.starts_at.astimezone(KST).date()
    rows = []
    for item in items:
        if item is meal or item.kind == "mobility" or item.starts_at.astimezone(KST).date() != day:
            continue
        row: dict[str, Any] = {"time": _hm(item.starts_at), "kind": item.kind, "title": item.title}
        if item.kind == "dining" and item.place:
            row.update({k: v for k, v in _place_brief(item.place).items() if k != "name"})
        rows.append(row)
    return MealContext(meal_title=meal.title, starts_at=meal.starts_at, original=meal.place or {}, day=rows,
                       preference=preference)


__all__ = ["IDS", "PREFERENCE_KEY", "MealContext", "MealPicker", "Pick", "check", "day_context", "facts",
           "make_picker", "preference_of", "prompt", "schema", "should_ask"]
