# -*- coding: utf-8 -*-
"""읽은 성향 · 조건 → 담당이 읽는 열쇠. `[2026-10-16 D-025 후속]`

★왜. 이해 에이전트(`agent_read.py`)가 「웬만하면 택시」 · 「천천히」 · 「맛집 위주」 · 「비 오면 실내」 · 「9시까지 숙소」를 읽어도
  그 값은 `reading.agent` 값 줄에만 있었다 — 이동 판정 · 일정 짜기 · 식당 고르기 · 활동 대안은 **설문 열쇠**만 읽는데 그 열쇠는 설문 답만 채웠다.
  그래서 담당이 이미 읽는 열쇠로 옮겨 싣는다. 새 판단 규칙을 만들지 않는다 — 담당은 지금 읽던 열쇠를 그대로 읽는다.

    읽은 것(코드)                                  → 담당이 읽는 열쇠                         누가 읽나
    prefer_taxi · prefer_transit · prefer_walking  → survey.priority_details.mobility        이동 판정 · 일정 짜기(`mobility/wiring.modes_from_survey`)
      + 여행 전체 이동(「다 지하철로」 — moves scope all, 원문 조각에 「다 · 늘 · 주로 · 웬만하면」류가 있을 때만 — `whole_trip_said`)
    slow_pace · late_start                         → survey.pace = relaxed                   일정 짜기 밀도(`planning/survey.apply_survey`)
    food_focus · nice_restaurants (+ 원문 조각)    → constraints.meal_preference             식당 고르기(`planning/meal_pick.preference_of`)
    if_rain_indoor                                 → survey.indoor_outdoor.activity = indoor 활동 대안 순서(`activity/alternative_order`)
                                                     + survey.custom_answers.indoor_outdoor(원문)
    avoid_walking · elderly_friendly · avoid_stairs → constraints.mobility_ease = needs_rest  밀도 · 이동 판정(`density` · `mobility/engine/plan.party_of`)
    finish_by:HH:MM · start_after:HH:MM            → constraints.day_hours.end · .start      하루 마감 · 일정 짜기 하루 창(새 열쇠 — D-025 「담당 연결」)

★**고객이 직접 답한 값이 먼저다.** 설문(로딩 중 질문 · 등록 요청의 설문)에 이미 있는 자리와 등록 몸통에 이미 있는 열쇠는 덮지 않는다.
  읽은 값으로 채운 것은 `constraints.filled_by_reading` 에 원문 조각과 함께 남긴다 — 화면이 「우리가 채움」으로 보이고,
  설문의 「직접 답한 문항」(`survey_answered`)에는 넣지 않는다(`planning/survey.apply_survey`).
★읽는 쪽은 둘이다 — 접수 확인 화면(`proposals` → 「담당에 넘길 것」)과 등록(`apply` → 등록 몸통 · 일정 짜기 요청).
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Iterable, Mapping

#: 등록 몸통에 실어 두는 칸 — 등록 직전에 `apply` 가 풀어 담당 열쇠로 옮기고 지운다
CARRY_KEY = "reading_fill"
#: 등록된 여행에 남는 「우리가 채움」 기록
FILLED_KEY = "filled_by_reading"
#: 설문 판(`planning/survey.SURVEY_VERSION`) — 설문이 없을 때 새로 만들 때만 쓴다
SURVEY_VERSION = "2026-09-24.v1"

_MOBILITY_PREF = {"prefer_taxi": "taxi", "prefer_transit": "public", "prefer_walking": "walk"}
#: 여행 전체 이동 수단(moves scope all) → 설문 이동 코드(`mobility/wiring.SURVEY_MODES` 가 아는 것만 — 렌트카 · 자전거 · 케이블카는 계산기가 못 다룬다)
_MOVE_MODE = {"taxi": "taxi", "subway": "subway", "bus": "bus", "transit": "public", "walk": "walk"}
_PACE_PREF = ("slow_pace", "late_start")
_FOOD_WORDS = {"food_focus": "맛있는 곳(먹는 게 중요)", "nice_restaurants": "분위기 좋은 식당"}
_REST_PREF = ("avoid_walking", "elderly_friendly", "avoid_stairs")
_CLOCK = re.compile(r"^(finish_by|start_after):(([01]\d|2[0-3]):[0-5]\d)$")
#: 여행 전체를 말하는 낱말 — 띄어 쓴 한 낱말(「다 지하철로」의 「다」 · 「늘」)과 글 안 어디에 있어도 되는 말(「주로」 · 「웬만하면」)
_WHOLE_TRIP_WORDS = frozenset({"다", "늘", "모두", "전부", "항상", "내내", "줄곧", "언제나"})
_WHOLE_TRIP_PHRASES = ("주로", "웬만하면", "웬만해선", "웬만해서는", "대부분", "여행 내내", "모든 이동", "이동은 다")


_DAY_TRANSPORT = re.compile(r"오늘|내일|모레|첫날|둘째\s*날|셋째\s*날|\d+\s*일차|하루\s*종일")
_LOCAL_TRANSPORT = re.compile(r"지금|이번\s*(?:구간|이동)|이번만|[이그]\s*구간|[여거]기서|에서|부터|까지")
_MOBILITY_PREFERENCE = re.compile(r"위주|선호|좋아|다니|다닐|괜찮")


def transport_scope(scope: Any, quote: Any) -> str:
    """모델이 말한 적용 범위는 원문의 근거가 있을 때만 넓힌다."""
    if scope == "all" and whole_trip_said(quote):
        return "all"
    text = str(quote or "")
    if scope == "day" and _DAY_TRANSPORT.search(text) and not _LOCAL_TRANSPORT.search(text):
        if _whole_transport_words(text) or _MOBILITY_PREFERENCE.search(text):
            return "day"
    return "segment"


def mobility_preference_said(quote: Any) -> bool:
    """한 번의 이동을 지속적인 이동 성향으로 확대하지 않는다."""
    text = str(quote or "")
    return not (_LOCAL_TRANSPORT.search(text) or _DAY_TRANSPORT.search(text)) and (
        whole_trip_said(text) or bool(_MOBILITY_PREFERENCE.search(text)))


def whole_trip_said(quote: Any) -> bool:
    """원문 조각이 여행 전체의 이동을 말하나 — 「다 지하철로」 · 「웬만하면 택시」는 예, 「택시로 이동」 · 「다녀와요」는 아니다."""
    text = str(quote or "")
    return not (_LOCAL_TRANSPORT.search(text) or _DAY_TRANSPORT.search(text)) and _whole_transport_words(text)


def _whole_transport_words(text: str) -> bool:
    if any(phrase in text for phrase in _WHOLE_TRIP_PHRASES):
        return True
    return any(token in _WHOLE_TRIP_WORDS for token in re.split(r"[\s,.!?·~()\[\]「」'\"]+", text))


#: 원문 조각을 식당 취향 문장에 붙일 때의 상한 — 선택기 문장(`meal_pick.preference_of` 의 설문 원문 200자)과 같다
MEAL_PREFERENCE_MAX = 200

#: 화면에 보일 이름 — 「무엇을 · 누구에게」
LABELS = {
    "survey.priority_details.mobility": ("이동 수단", "이동 판정 · 일정 짜기"),
    "survey.pace": ("일정 여유", "일정 짜기"),
    "constraints.meal_preference": ("식당 취향", "식당 고르기"),
    "survey.indoor_outdoor.activity": ("실내 먼저", "활동 대안"),
    "constraints.mobility_ease": ("덜 걷게", "이동 판정 · 일정 밀도"),
    "constraints.day_hours.end": ("하루 끝 시각", "일정 짜기 · 하루 마감"),
    "constraints.day_hours.start": ("하루 시작 시각", "일정 짜기"),
}


def agent_values(claims: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """원본마다 `reading.agent` 값 줄(에이전트 결과를 실제로 쓴 것만 — 그림자 · 실패는 뺀다)."""
    return [dict(c["value"]) for c in claims
            if c.get("field") == "reading.agent" and isinstance(c.get("value"), dict) and c["value"].get("used")]


def proposals(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """읽은 성향 · 조건 → 열쇠마다 하나 `{key, value, codes, quotes}`. 같은 열쇠는 원본 여럿을 합친다(이동 수단은 모아서, 시각은 처음 것)."""
    by_key: dict[str, dict[str, Any]] = {}

    def put(key: str, value: Any, code: str, quote: Any, *, merge_list: bool = False) -> None:
        found = by_key.get(key)
        if found is None:
            by_key[key] = {"key": key, "value": value, "codes": [code], "quotes": [quote] if quote else []}
            return
        if merge_list:
            found["value"] = list(dict.fromkeys([*found["value"], *value]))
        if code not in found["codes"]:
            found["codes"].append(code)
        if quote and quote not in found["quotes"]:
            found["quotes"].append(quote)

    for value in values:
        for pref in value.get("preferences") or []:
            code, quote = pref.get("code"), pref.get("quote")
            if code in _MOBILITY_PREF:
                if mobility_preference_said(quote):
                    put("survey.priority_details.mobility", [_MOBILITY_PREF[code]], code, quote, merge_list=True)
            elif code in _PACE_PREF:
                put("survey.pace", "relaxed", code, quote)
            elif code in _FOOD_WORDS:
                put("constraints.meal_preference", None, code, quote)
            elif code in _REST_PREF:
                put("constraints.mobility_ease", "needs_rest", code, quote)
        for move in value.get("moves") or []:
            # ★`[2026-10-19 설계 §4]` 여행 전체 수단은 원문 조각에 「다 · 늘 · 주로 · 웬만하면」 같은 말이 있을 때만 받는다 — 한 구간 「택시로 이동」을
            #   여행 내내 택시로 읽은 사례(x600 서버 2건)가 이동 질문을 빼고 설문을 채우지 않게. 구간 수단은 이동 판정에만 쓴다
            if move.get("scope") == "all" and move.get("mode") in _MOVE_MODE and whole_trip_said(move.get("quote")):
                put("survey.priority_details.mobility", [_MOVE_MODE[move["mode"]]], f"move_all:{move['mode']}", move.get("quote"),
                    merge_list=True)
        for cond in value.get("conditions") or []:
            code, quote = str(cond.get("code") or ""), cond.get("quote")
            if code == "if_rain_indoor":
                put("survey.indoor_outdoor.activity", "indoor", code, quote)
            clock = _CLOCK.match(code)
            if clock:
                put(f"constraints.day_hours.{'end' if clock.group(1) == 'finish_by' else 'start'}", clock.group(2), code, quote)
    meal = by_key.get("constraints.meal_preference")
    if meal is not None:
        meal["value"] = _meal_sentence(meal["codes"], meal["quotes"])
    hours = (by_key.get("constraints.day_hours.start"), by_key.get("constraints.day_hours.end"))
    if all(hours) and hours[0]["value"] >= hours[1]["value"]:
        # 시작이 끝보다 늦다 — 둘 중 하나를 잘못 읽었다. 짐작으로 고르지 않고 둘 다 넘기지 않는다(확인 화면 「이렇게 이해했어요」에는 남는다)
        del by_key["constraints.day_hours.start"], by_key["constraints.day_hours.end"]
    return [by_key[key] for key in LABELS if key in by_key]


def _meal_sentence(codes: list[str], quotes: list[str]) -> str:
    """식당 고르기 모델이 읽는 취향 문장 — 정해진 말 + 고객 원문. 원문은 고객이 쓴 그대로다(지어내지 않는다)."""
    words = " · ".join(_FOOD_WORDS[c] for c in codes if c in _FOOD_WORDS)
    said = " / ".join(q for q in quotes if q)
    text = f"{words} — 고객 말: {said}" if said else words
    return text[:MEAL_PREFERENCE_MAX]


def carry(claims: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """등록 몸통에 실을 것(`constraints.reading_fill`) — 읽은 것이 없으면 빈 목록."""
    return proposals(agent_values(claims))


def _survey_has(survey: Mapping[str, Any] | None, key: str) -> bool:
    """설문의 그 자리에 고객이 준 값이 있나 — `survey.priority_details.mobility` 처럼 점으로 잇는다."""
    node: Any = survey or {}
    for part in key.split(".")[1:]:
        if not isinstance(node, Mapping) or node.get(part) in (None, "", [], {}):
            return False
        node = node[part]
    return True


def status(item: Mapping[str, Any], *, constraints: Mapping[str, Any] | None, survey: Mapping[str, Any] | None) -> str:
    """`filled`(우리가 채움) · `customer`(고객이 직접 답한 값이 있어 그대로 둠)."""
    key = item["key"]
    if key.startswith("survey."):
        return "customer" if _survey_has(survey, key) else "filled"
    name = key.split(".", 1)[1]
    head = name.split(".")[0]
    current = (constraints or {}).get(head)
    if name == "day_hours.end" or name == "day_hours.start":
        current = (current or {}).get(name.split(".")[1]) if isinstance(current, Mapping) else None
    return "customer" if current not in (None, "", [], {}) else "filled"


_MODE_WORDS = {"taxi": "택시", "public": "대중교통", "walk": "걷기", "subway": "지하철", "bus": "버스"}
_VALUE_WORDS = {"relaxed": "여유 있게", "indoor": "실내 먼저", "needs_rest": "덜 걷고 쉬어 가며"}


def value_text(key: str, value: Any) -> str:
    """화면에 보일 값 — 코드(`taxi` · `relaxed`)를 고객 말로. 시각 · 취향 문장은 그대로."""
    if key == "survey.priority_details.mobility":
        return " · ".join(_MODE_WORDS.get(v, str(v)) for v in value or [])
    if key == "constraints.day_hours.end":
        return f"{value}까지"
    if key == "constraints.day_hours.start":
        return f"{value}부터"
    return _VALUE_WORDS.get(value, str(value)) if isinstance(value, str) else str(value)


def view(items: Iterable[Mapping[str, Any]], *, survey: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """확인 화면 「담당에 넘길 것」 — 무엇을 · 누구에게 · 원문 조각 · 우리가 채움(filled)인가 고객 답 먼저(customer)인가."""
    out = []
    for item in items:
        label, owner = LABELS[item["key"]]
        out.append({"key": item["key"], "label": label, "owner": owner, "value": item["value"], "text": value_text(item["key"], item["value"]),
                    "codes": list(item["codes"]), "quotes": list(item["quotes"]), "status": status(item, constraints=None, survey=survey)})
    return out


def apply(constraints: Mapping[str, Any] | None) -> dict[str, Any]:
    """등록 직전 — 실어 둔 읽은 값(`reading_fill`)을 **비어 있는 자리에만** 옮기고, 채운 것을 `filled_by_reading` 에 남긴다. 새 dict 를 돌려준다.

    ★설문 자리는 설문(`constraints.survey`)에 고객 값이 없을 때만, 다른 열쇠는 등록 몸통에 그 열쇠가 없을 때만 채운다.
    ★설문이 없으면 판(`version`)을 붙여 새로 만든다 — 그래도 「직접 답한 문항」은 아니다(`survey_read_keys` → `apply_survey` 가 뺀다)."""
    out = deepcopy(dict(constraints or {}))
    items = out.pop(CARRY_KEY, None) or []
    if not items:
        return out
    survey_before = out.get("survey") if isinstance(out.get("survey"), Mapping) else None
    survey = dict(deepcopy(survey_before) or {})
    filled: list[dict[str, Any]] = list(out.get(FILLED_KEY) or [])
    read_keys: set[str] = set(out.get("survey_read_keys") or [])
    for item in items:
        key = item.get("key")
        if key not in LABELS or status(item, constraints=out, survey=survey) != "filled":
            continue
        value = item["value"]
        parts = key.split(".")
        if parts[0] == "survey":
            top = parts[1]
            if top not in survey or survey.get(top) in (None, "", [], {}):
                read_keys.add(top)
            if len(parts) == 2:
                survey[top] = value
            else:
                node = survey.setdefault(top, {})
                node[parts[2]] = value
            if key == "survey.indoor_outdoor.activity" and item.get("quotes"):
                answers = survey.setdefault("custom_answers", {})
                if "indoor_outdoor" not in answers:
                    answers["indoor_outdoor"] = " / ".join(item["quotes"])[:MEAL_PREFERENCE_MAX]
                    if "custom_answers" not in (survey_before or {}):
                        read_keys.add("custom_answers")
        elif parts[1] == "day_hours":
            out["day_hours"] = {**(out.get("day_hours") or {}), parts[2]: value}
        else:
            out[parts[1]] = value
        filled.append({"key": key, "value": value, "codes": list(item.get("codes") or []), "quotes": list(item.get("quotes") or []),
                       "by": "reading"})
    if survey and survey != (survey_before or {}):
        survey.setdefault("version", SURVEY_VERSION)
        out["survey"] = survey
    if filled:
        out[FILLED_KEY] = filled
    if read_keys:
        out["survey_read_keys"] = sorted(read_keys)
    return out


__all__ = ["CARRY_KEY", "FILLED_KEY", "LABELS", "agent_values", "apply", "carry", "proposals", "status", "value_text", "view",
           "mobility_preference_said", "transport_scope", "whole_trip_said"]
