"""Validated time boundaries and spatial search criteria, independent of wording."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import re
from typing import Any

TIME = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")
#: 생성 문법의 비어 있지 않은 HH:MM(`TIME` 과 같은 값 범위)
_CLOCK = "^([01][0-9]|2[0-3]):[0-5][0-9]$"


def schemas(aliases: list[str]) -> dict[str, Any]:
    def obj(fields):
        return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}

    def enum(values):
        return {"type": "string", "enum": values}

    return {
        "time_edit": obj({"boundary": enum(["none", "start", "end", "duration", "shift", "reflow"]),
                          "scope": enum(["item", "following", "range"]),
                          "time": {"type": "string", "pattern": "^(|([01][0-9]|2[0-3]):[0-5][0-9])$"},
                          "duration_minutes": {"type": "integer"}, "cascade": {"type": "boolean"},
                          "continue_previous": {"type": "boolean"}, "evidence": {"type": "string"}}),
        "place_search": obj({"relation": enum(["none", "near"]), "anchor_item": enum(aliases),
                             "place_text": {"type": "string"}, "evidence": {"type": "string"}}),
        # ★`[2026-10-25 QA]` 바꿀 새 장소의 실내·야외 조건 — 전에는 담을 칸이 없어 「실내를 야외로 바꿔줘」가 또 실내로 바뀌었다
        # ★`[2026-10-26 x600 c34bd376]` 대상을 몰라 clarify 를 고른 해석이 이 칸을 any 로 비웠다 — 엄격 스키마(유료 넘김)는 칸 설명을 그대로 보낸다
        "place_setting": {**obj({"want": enum(list(SETTINGS)), "evidence": {"type": "string"}}),
                          "description": "새 장소의 실내·야외 조건. action과 무관하게(바꿀 일정을 몰라 clarify여도) 고객이 말했으면 채운다"},
    }


#: 새 장소의 실내·야외 조건 — any(조건 없음) · indoor · outdoor
SETTINGS = ("any", "indoor", "outdoor")


def paid_time_edit(aliases: list[str]) -> dict[str, Any]:
    """유료 넘김 경로(`decision_unit._schema(plain=True)`)의 `time_edit` — 실행할 수 있는 경계 · 범위 조합만 갈래로 싣는다. `[2026-10-26 x600 40231a56]`

    ★로컬 생성 문법은 갈래(`generation_variants`)로 맞는 조합만 생성하게 한다. 유료 스키마는 두 칸을 따로 둬 `start` + `following` 같은
      실행할 수 없는 조합을 낼 수 있었고, 그 답은 `validate` 가 `inconsistent temporal scope` 로 거절했다(x600 Case 72e29b8c
      「오후 5시 30분으로 옮겨줘」 — `ollama=timeout, openai=content`). OpenAI 엄격 모드는 최상위가 아닌 칸 안의 anyOf 를 받는다.
    갈래 규칙은 `_inconsistent` 와 `validate` 의 range 조건 중 이 칸 안에서 정해지는 것과 같다(다른 칸과 묶인 조건은 `validate` 가 그대로 본다).
    문장 · 일정 이름은 싣지 않는다."""
    from copy import deepcopy

    base = schemas(aliases)["time_edit"]

    def variant(boundary: list[str], scope: list[str], **fixed: Any) -> dict[str, Any]:
        shape = deepcopy(base)
        shape["properties"]["boundary"] = {"type": "string", "enum": boundary}
        shape["properties"]["scope"] = {"type": "string", "enum": scope}
        for key, value in fixed.items():
            kind = "boolean" if type(value) is bool else "integer" if type(value) is int else "string"
            shape["properties"][key] = {"type": kind, "enum": [value]}
        return shape

    return {"anyOf": [
        variant(["none"], ["item"]),
        variant(["start", "end", "duration"], ["item"], continue_previous=False),
        variant(["shift"], ["item", "following"], continue_previous=False),
        variant(["shift"], ["range"], time="", duration_minutes=0, cascade=False, continue_previous=False),
        variant(["reflow"], ["following"]),
    ], "description": "시간 수정. boundary 와 scope 의 맞는 조합만 — start · end · duration 은 scope=item, reflow 는 scope=following, "
                      "range 는 shift 만(target_item=none, query 필수). 시간 변경이 없으면 boundary=none, scope=item"}


def requested_setting(raw: dict[str, Any] | None) -> str | None:
    """검증을 지난 해석의 실내·야외 조건 — indoor/outdoor 이거나 None(조건 없음 · 옛 해석)."""
    want = ((raw or {}).get("place_setting") or {}).get("want")
    return want if want in ("indoor", "outdoor") else None


SYSTEM = """
시간 변경의 뜻은 time_edit, 장소 검색의 기준은 place_search에 별도로 보존한다.
상대 이동과 절대 시각 수정은 다르다. 기존 시각에서 몇 분/시간 미룸·당김은 boundary=shift, minutes=부호 있는 이동 분수, time="",duration_minutes=0,cascade=false다. 일정표의 시각을 새 시각으로 복사하지 않는다. 체류 유지도 shift다.
방문 하나 상대 이동은 scope=item,target_item=그 방문,anchor_kind=none,anchor_item=none,anchor_time=""다.
특정 날짜 전체 또는 시각/방문 이전·이후 범위의 상대 이동은 scope=range,target_item=none,query={day,period,kind,position} 필수다. 날짜는 query.day로 고르며 at_day=none이다. 달력 날짜는 일정 목록의 월-일과 일차를 대조한다. 지금 날짜가 아니면 today가 아니다.
시각 전후 범위는 anchor_kind=time,anchor_time=고객이 말한 기준 시각,relation=before/after다. 기준 시각은 옮길 새 시작이나 종료가 아니므로 time_edit.time=""다. 방문 전후 범위는 anchor_kind=item,anchor_item=기준 방문,relation=before/after이며 기준 방문 자체와 다른 날은 제외한다. 날짜 전체는 anchor_kind=none,anchor_time="",relation=at다.
정확한 새 시작/종료 시각 자체를 요청할 때만 start/end다. 체류 분수를 바꿀 때만 duration이다. 이 세 경계의 minutes는 0이며 상대 이동과 함께 생성하지 않는다. 일반 읽기 질문의 앞뒤 한 항목 선택과 여러 일정 이동 범위를 혼동하지 않는다.
time_edit.boundary=start(시작),end(체류 종료),duration(머무는 분수),shift(상대 이동),reflow(뒤 일정 재배치),none(시간 변경 없음).
종료 시각까지 머물겠다는 요청은 end이며 그 시각에 시작하라는 뜻이 아니다. 정확한 시각이 없는 저녁·늦게 등의 표현으로 시각을 만들지 않고 time=""로 낸다.
새 시작 시각을 말하면 미루기·당기기 말이 함께 있어도 start이며 time=그 시각이다(「점심을 오후 2시 10분으로 미뤄줘」 start, time=14:10). shift는 옮길 크기(30분·1시간)만 말할 때다.
다른 날로 옮기면 at_day=그 날이다. 「다음 날로」「전날로」처럼 그 일정 날을 기준으로 말하면 일정 줄의 일차로 센 dN이며, 오늘 기준의 tomorrow가 아니다(1일차 일정을 다음 날로 = d2). 날과 새 시작 시각을 함께 말하면 start에 time과 at_day를 함께 내고, 날만 말하면 start, time=""이다.
scope=item은 target_item 자체, following은 anchor_item 다음의 같은 날 일정 전체이며 기준 항목 자체는 제외한다.
following 상대 이동에서 anchor_item은 고객이 가리킨 기준 방문이며 target_item도 같은 기준 방문이다. 옮겨질 첫 번째 뒤 방문을 anchor_item으로 고르면 그 방문이 제외되므로 그렇게 고르지 않는다. 기준 방문 뒤의 모든 방문이 대상이다.
장소 변경 자체는 근처 검색 조건이 아니다. 고객이 현재 문장에서 별도의 공간 관계·검색 기준을 요청하지 않았으면 place_search.relation=none이며 anchor_item=none,place_text="",evidence=""다. 기존 장소를 다른 곳으로 바꾸라는 요청만으로 near를 만들지 않는다.
체류 종료를 바꾸고 뒤 일정도 맞추는 요청은 end/scope=item/cascade=true이며 target_item은 머무는 일정이다.
새 종료를 말하지 않고 뒤 일정만 맞추는 요청은 reflow/scope=following이며 anchor_item은 기준 일정이다.
직전 실패·확인 질문의 변경 목표를 이어 실행하라는 요청에서만 continue_previous=true. 제공된 edit_goal만 이어받으며 새 시각·대상을 명시하면 false.
evidence는 현재 고객 문장의 해당 부분을 그대로 복사한다. time은 HH:MM이며 duration_minutes는 명시된 체류 분수다.
해당 없음은 boundary=none,scope=item,time="",duration_minutes=0,cascade=false,continue_previous=false,evidence="".
place_search는 변경 대상과 별도의 검색 기준이다. 기존 식사를 다른 일정 근처로 바꾸면 apply_change/target_item=식사,
place_search.relation=near/anchor_item=기준 일정이다. 주변·근처 같은 관계를 상호명으로 조회하지 않으며 destination_text를 비운다.
기준이 일정 안이면 그 ID, 일정 밖 지명이면 place_text에 고객이 말한 지명만 원문 그대로 적는다. 기준 불명이면 none/빈 문자열이다.
후보만 요청하면 propose_alternatives이며 실제 변경은 apply_change다. 주변 식당 읽기 질문으로 바꾸어 해석하지 않는다.
evidence는 현재 고객 문장의 장소 조건 원문. 검색 조건 없음은 relation=none,anchor_item=none,place_text="",evidence="".
place_setting은 장소 교체·후보 요청에서 고객이 새 장소를 실내 또는 야외로 지정한 조건이다. 실내로 가자면 want=indoor, 야외·바깥으로 가자면 want=outdoor,
evidence에 그 조건 원문을 그대로 복사한다. 지금 장소가 실내·야외라는 설명은 새 장소 조건이 아니다. 실내·야외는 장소 이름이나 조건부 요청이 아니므로 destination_text·condition_text에 넣지 않는다.
조건이 없으면 want=any, evidence="".
place_setting은 action과 무관하게 채운다. 바꿀 일정을 정하지 못해 clarify를 골라도 고객이 새 장소를 실내·야외로 지정했으면 want와 evidence를 낸다.
place_setting은 place_search와 별개다. 고객이 주변·근처의 기준 일정이나 지명을 말하지 않았으면 실내·야외 조건이 있든 없든
place_search는 relation=none,anchor_item=none,place_text="",evidence=""이며, 바꿀 대상 일정을 place_search 기준으로 옮겨 적지 않는다.
"""


def generation_variants(variants, aliases, query_schema, message, *, quoted_days, quoted_items):
    """Disjoint generation modes; no natural-language parsing or output repair."""
    from copy import deepcopy

    result = []
    template = None
    for original in variants:
        actions = original["properties"]["action"]["enum"]
        if "change_time" not in actions:
            result.append(original)
            continue
        if template is None:
            template = original
        other = [action for action in actions if action != "change_time"]
        if other:
            branch = deepcopy(original)
            branch["properties"]["action"]["enum"] = other
            result.append(branch)
        temporal = original["properties"]["time_edit"]
        # Existing following/reflow schema already binds the quoted anchor. Its
        # legacy duration/cascade metadata does not change the delta consumer;
        # preserve that contract rather than retroactively rejecting saved shapes.
        if temporal.get("properties", {}).get("scope", {}).get("enum") == ["following"]:
            result.append(original)
            continue
        for spec in temporal.get("anyOf", [temporal]):
            for boundary in spec["properties"]["boundary"]["enum"]:
                branch = deepcopy(original)
                fields = branch["properties"]
                fields["action"]["enum"] = ["change_time"]
                fields["time_edit"] = deepcopy(spec)
                edit = fields["time_edit"]["properties"]
                edit["boundary"]["enum"] = [boundary]
                if boundary in {"none", "start", "end", "duration"}:
                    fields["minutes"] = {"type": "integer", "enum": [0]}
                if boundary in {"shift", "reflow"}:
                    edit["time"] = {"type": "string", "enum": [""]}
                    edit["duration_minutes"] = {"type": "integer", "enum": [0]}
                    fields["anchor_time"] = {"type": "string", "enum": [""]}
                    if edit["scope"]["enum"] == ["item"]:
                        fields["anchor_kind"]["enum"] = ["none"]
                        fields["anchor_item"]["enum"] = ["none"]
                    if boundary == "shift":
                        fields["minutes"] = {"anyOf": [{"type": "integer", "minimum": 1},
                                                       {"type": "integer", "maximum": -1}]}
                        edit["cascade"] = {"type": "boolean", "enum": [False]}
                        edit["continue_previous"] = {"type": "boolean", "enum": [False]}
                result.append(branch)
                if boundary == "shift" and edit["scope"]["enum"] == ["item"]:
                    # ★`[2026-10-28 x600 4fee819c]` 한 일정 shift 는 인용된 절대 시각을 낼 수도 있다 — `time_ops` 가 그 시각을 새 시작으로
                    #   실행한다(c286b906). 위 갈래만 두면 time 이 빈 문자열로 묶여, 「오후 5시 30분으로 옮겨줘」에 shift 를 고른 로컬 E4B 가
                    #   시각을 어디에도 못 내고 minutes=30 만 냈다(Case 10108fc5 · 14dd1f31 · 5a96697a → need_time 3/3).
                    #   상대 이동 크기와 함께 내지는 못한다(minutes=0). 시각 값은 `validate` 가 인용으로 재계산해 확인한다.
                    clock = deepcopy(branch)
                    clock["properties"]["time_edit"]["properties"]["time"] = {"type": "string", "pattern": _CLOCK}
                    clock["properties"]["minutes"] = {"type": "integer", "enum": [0]}
                    result.append(clock)
                    # 같은 뜻의 맨 위 시작 시각 칸(anchor_kind=time · relation=at · anchor_time) — SYSTEM(decision_unit) 「새 시각을 말하면
                    #   anchor_kind=time · anchor_time=새 시작 시각」. ☆실 E4B(로컬 2/2)는 shift 를 고른 뒤 time 을 계속 빈 문자열로 냈다 —
                    #   time_edit 이 먼저 생성되므로 시각을 낼 다음 자리가 이 칸이다. `chat_edit.ops_for` 가 이 칸을 새 시작으로 쓰고(옛 경로 그대로),
                    #   `validate` 가 time 과 같은 인용 재계산으로 확인한다(`_shift_start_clock`). before/after(범위 경계)는 내지 못한다.
                    top = deepcopy(branch)
                    fields = top["properties"]
                    fields["anchor_kind"] = {"type": "string", "enum": ["time"]}
                    fields["anchor_item"] = {"type": "string", "enum": ["none"]}
                    fields["anchor_time"] = {"type": "string", "pattern": _CLOCK}
                    fields["relation"] = {"type": "string", "enum": ["at"]}
                    fields["minutes"] = {"type": "integer", "enum": [0]}
                    result.append(top)
    if template is not None and message.strip():
        for kind in ("none", "time", "item"):
            branch = deepcopy(template)
            fields = branch["properties"]
            fields["action"]["enum"] = ["change_time"]
            fields["target_item"]["enum"] = ["none"]
            fields["target_change"]["enum"] = ["none"]
            fields["fact"]["enum"] = ["none"]
            fields["minutes"] = {"anyOf": [{"type": "integer", "minimum": 1},
                                           {"type": "integer", "maximum": -1}]}
            fields["anchor_kind"]["enum"] = [kind]
            fields["anchor_item"]["enum"] = quoted_items if kind == "item" else ["none"]
            if not fields["anchor_item"]["enum"]:
                continue
            fields["anchor_time"] = ({"type": "string", "pattern": "^([01][0-9]|2[0-3]):[0-5][0-9]$"}
                                     if kind == "time" else {"type": "string", "enum": [""]})
            fields["at_day"]["enum"] = ["none"]
            fields["relation"]["enum"] = ["at"] if kind == "none" else ["before", "after"]
            fields["query"] = deepcopy(query_schema)
            fields["query"]["properties"]["day"]["enum"] = quoted_days or ["all"]
            fields["query"]["properties"]["position"]["enum"] = ["all"]
            if kind in {"time", "item"}:
                fields["query"]["properties"]["period"]["enum"] = ["all"]
            if "query" not in branch["required"]:
                branch["required"].append("query")
            fields["time_edit"] = schemas(aliases)["time_edit"]
            edit = fields["time_edit"]["properties"]
            for key, value in {"boundary": "shift", "scope": "range", "time": "", "duration_minutes": 0,
                               "cascade": False, "continue_previous": False, "evidence": message}.items():
                edit[key] = {"type": "boolean" if type(value) is bool else "integer" if type(value) is int else "string", "enum": [value]}
            # The discriminator precedes the fields whose meaning it selects.
            fields_order = ("action", "time_edit", "anchor_kind", "relation", "query")
            branch["properties"] = {**{key: fields[key] for key in fields_order}, **fields}
            result.append(branch)
    return result


def validate(raw: dict[str, Any], message: str, aliases: set[str]) -> None:
    """Validate structure and quoted evidence; never infer intent with phrase rules."""
    setting = raw.get("place_setting")
    if setting is not None:
        if not isinstance(setting, dict) or setting.get("want") not in SETTINGS:
            raise ValueError("invalid place_setting")
        quote = setting.get("evidence")
        if setting["want"] != "any" and (not isinstance(quote, str) or not quote.strip() or quote not in message):
            raise ValueError("unquoted place_setting")
    for field in ("time_edit", "place_search"):
        value = raw.get(field)
        if value is None:
            continue  # Stored legacy decisions retain their old interpretation.
        if not isinstance(value, dict):
            raise ValueError(f"invalid {field}")
        active = value.get("boundary", "none") != "none" if field == "time_edit" else value.get("relation", "none") != "none"
        if not active:
            continue
        quote = value.get("evidence")
        if not isinstance(quote, str) or not quote.strip() or quote not in message:
            raise ValueError(f"unquoted {field}")
        if field == "place_search":
            if value.get("relation") != "near" or value.get("anchor_item", "none") not in aliases:
                raise ValueError("invalid spatial relation")
            text = value.get("place_text", "")
            if not isinstance(text, str) or (text and text not in message):
                raise ValueError("unquoted spatial origin")
        else:
            if value.get("boundary") not in {"start", "end", "duration", "shift", "reflow"} or value.get("scope") not in {"item", "following", "range"}:
                raise ValueError("invalid temporal relation")
            if _inconsistent(value) and _executes_time_edit(raw):
                raise ValueError("inconsistent temporal scope")
            if value.get("scope") == "range" and (
                    value["boundary"] != "shift" or raw.get("target_item") != "none"
                    or raw.get("anchor_kind") not in {"none", "time", "item"}
                    or value.get("time") or value.get("duration_minutes")
                    or value.get("cascade") or value.get("continue_previous")):
                raise ValueError("inconsistent temporal scope")
            clock = (raw.get("anchor_time", "") if value.get("scope") == "range" or _shift_start_clock(value, raw)
                     else value.get("time", ""))
            if _shift_start_clock(value, raw) and raw.get("minutes") not in (0, None):
                # 새 시작 시각과 상대 이동 크기를 함께 냈다 — 생성 문법은 막고(minutes=0), 문법 없는 유료 답도 조용히 한쪽으로 실행하지 않는다(Codex 검토)
                raise ValueError("inconsistent temporal scope")
            if not isinstance(clock, str) or (clock and not TIME.fullmatch(clock)):
                raise ValueError("invalid temporal clock")
            if clock:
                from ..intake.fact_check import _FULL_CLOCK, _KO_CLOCK, recompute_time

                quoted_clock = _FULL_CLOCK.search(quote) or _KO_CLOCK.search(quote)
                if quoted_clock is None:
                    raise ValueError("unquoted temporal clock")
                quoted_hour = int(quoted_clock.group(1))
                hour = int(clock[:2])
                if 1 <= quoted_hour < 12:
                    explicit_am = re.search(r"오전|\bam\b", quote, re.IGNORECASE)
                    explicit_pm = re.search(r"오후|저녁|밤|\bpm\b", quote, re.IGNORECASE)
                    if (explicit_am and hour == quoted_hour + 12) or (explicit_pm and hour == quoted_hour):
                        raise ValueError("temporal clock contradicts quoted meridian")
                checked, _ = recompute_time(clock, quote)
                if checked != clock:
                    raise ValueError("temporal clock disagrees with evidence")
            duration = value.get("duration_minutes", 0)
            if type(duration) is not int or duration < 0 or duration >= 24 * 60:
                raise ValueError("invalid stay duration")
            if type(value.get("cascade")) is not bool or type(value.get("continue_previous")) is not bool:
                raise ValueError("invalid temporal flags")


#: 장소를 바꾸는 행동 — 이 행동의 time_edit 은 실행되지 않는다(`time_ops` 는 change_time 만 읽는다)
PLACE_ACTIONS = frozenset({"apply_change", "propose_alternatives", "replace_named"})


def _shift_start_clock(value: dict[str, Any], raw: dict[str, Any]) -> bool:
    """한 일정 shift 의 새 시작 시각이 맨 위 칸(anchor_kind=time · relation=at · anchor_time)에 있다 — time_edit.time 이 비었을 때만.
    `[2026-10-28 x600 4fee819c]` 그 시각은 `chat_edit.ops_for` 가 새 시작으로 쓰므로 time 과 같은 인용 재계산 검증을 받는다(칸 구조만 본다)."""
    return (value.get("boundary") == "shift" and value.get("scope") == "item" and not value.get("time")
            and raw.get("anchor_kind") == "time" and raw.get("relation") == "at" and bool(raw.get("anchor_time"))
            and _executes_time_edit(raw))


def _inconsistent(value: dict[str, Any]) -> bool:
    """실행할 수 없는 시간 수정 조합 — 범위가 경계와 맞지 않거나, 이어 받기(continue_previous)가 reflow 가 아니다."""
    return bool((value.get("boundary") in {"start", "end", "duration"} and value.get("scope") != "item")
                or (value.get("boundary") == "reflow" and value.get("scope") != "following")
                or (value.get("continue_previous") and value.get("boundary") != "reflow"))


def _executes_time_edit(raw: dict[str, Any]) -> bool:
    """이 해석의 time_edit 이 시각 옮기기로 실행되는가 — change_time, 또는 시간·날짜 범위라 change_time 으로 옮겨지는 장소 행동."""
    action = raw.get("action")
    return action not in PLACE_ACTIONS or raw.get("change_scope") in ("time", "date")


def temporal_conflict(decision) -> dict[str, Any] | None:
    """`[2026-10-26]` 장소 행동에 실행할 수 없는 시간 수정이 함께 왔다 — 해석 실패(DecisionFailed)도, 장소 교체 실행도 아니다.
    장소를 바꿀지 시각을 옮길지 되묻는다(부르는 쪽 `trip_messages._run_decision`). 인용·시각·형식 검증은 `validate` 가 그대로 했다."""
    raw = decision.raw or {}
    spec = raw.get("time_edit") or {}
    if decision.action not in PLACE_ACTIONS or spec.get("boundary", "none") == "none":
        return None
    if _inconsistent(spec):
        reason = "inconsistent_time_edit"
    elif (decision.action != "replace_named" and not str(raw.get("destination_text") or "").strip()
          and requested_setting(raw) is None):
        # 새 장소의 이름·실내외 조건 없이 시각만 말했다 — 장소 교체로 실행하면 말하지 않은 곳으로 바뀐다(실 E4B D04 2026-10-26)
        reason = "time_without_place"
    else:
        return None
    return {"reason": reason, "action": decision.action, "boundary": spec.get("boundary"), "scope": spec.get("scope"),
            "continue_previous": bool(spec.get("continue_previous")), "evidence": spec.get("evidence", "")}


def ask_on_conflict(decision):
    """`temporal_conflict` 이면 장소를 바꾸지도 해석 실패로 끝내지도 않고 「다른 곳으로 바꿀지, 시각을 옮길지」 되묻는 clarify 로 바꾼다(일정은 그대로).
    선택지는 대상의 장소 바꾸기 하나 — 시각 옮기기는 크기나 새 시각이 있어야 하므로 문장으로 안내한다."""
    conflict = temporal_conflict(decision)
    if conflict is None:
        return decision
    name = f"「{decision.item.title}」을(를) " if decision.item is not None else ""
    choices = ([{"action": "apply_change", "item": decision.item, "change": None, "fact": "none"}]
               if decision.item is not None else [])
    return replace(decision, action="clarify", choices=choices,
                   question=(f"{name}다른 곳으로 바꿀지, 시각을 옮길지 확실하지 않아 일정은 바꾸지 않았어요. "
                             "시각이면 「30분 늦춰 줘」처럼 옮길 크기나 새 시각을 말씀해 주세요."),
                   raw={**(decision.raw or {}), "temporal_conflict": conflict})


def _quoted_clocks(clock: str, quote: str) -> list[str]:
    """인용 안의 시각 언급마다 `validate` 와 같은 재계산(`fact_check.recompute_time`)을 돌린 값들(언급 순서).

    「N시간」(길이)은 시각 언급이 아니다 — 같은 파서(`_KO_CLOCK`)가 「1시간」의 「1시」를 잡으므로 바로 뒤가 「간」이면 뺀다(파서 경계 보정)."""
    from ..intake.fact_check import _FULL_CLOCK, _KO_CLOCK, recompute_time

    found: list[tuple[int, str]] = []
    for match in _FULL_CLOCK.finditer(quote):
        found.append((match.start(), recompute_time(clock, match.group(0))[0]))
    for match in _KO_CLOCK.finditer(quote):
        if quote[match.end():match.end() + 1] == "간" and not match.group(2) and not match.group(3):
            continue
        found.append((match.start(), recompute_time(clock, match.group(0))[0]))
    return [value for _, value in sorted(found)]


def clock_ambiguity(decision) -> dict[str, Any] | None:
    """`[2026-10-26 묶음 L · 수용 X02]` 실행될 절대 시각 바꾸기의 인용이 **값을 하나로 정하는가**(근거 검사 — 뜻을 고르지 않는다).

    인용 안의 시각 언급을 하나씩 재계산해 서로 다른 값이 둘 이상이면 인용이 모델 값을 정하지 못한 것이다. 기준 시각 · 기간 끝 같은
    역할은 인용으로 입증되지 않으므로 빼 주지 않는다(Codex E2 — 보수적). 인용의 첫 시각이 모델 값과 다르면 `validate` 가 이미
    해석 실패로 막는다. ☆실 E4B J 2차 X02 「인사동을 오후 1시로 바꾸면서 동시에 낮 12시로 해줘」 → 인용 = 문장 전체, time 13:00 → 저장됐다."""
    raw = decision.raw or {}
    spec = raw.get("time_edit") or {}
    clock = spec.get("time") or ""
    if (not clock or spec.get("boundary", "none") == "none" or spec.get("scope") == "range"
            or not _executes_time_edit({**raw, "action": decision.action})):
        return None
    quote = str(spec.get("evidence") or "")
    clocks = sorted(set(_quoted_clocks(clock, quote)))
    if len(clocks) < 2:
        return None
    return {"reason": "multiple_clocks", "clocks": clocks, "time": clock, "evidence": quote}


def ask_on_clock_ambiguity(decision):
    """`clock_ambiguity` 이면 바꾸지 않고 어느 시각인지 되묻는 clarify 로 바꾼다(선택지 없음 — 고객이 시각 하나를 말한다)."""
    found = clock_ambiguity(decision)
    if found is None:
        return decision
    name = f"「{decision.item.title}」을(를) " if decision.item is not None else ""
    shown = " · ".join(found["clocks"])
    return replace(decision, action="clarify", choices=[],
                   question=(f"말씀에 시각이 여러 개({shown}) 있어 {name}몇 시로 바꿀지 확실하지 않아 일정은 바꾸지 않았어요. "
                             f"「{found['clocks'][0]}로 옮겨 줘」처럼 시각 하나만 말씀해 주세요."),
                   raw={**(decision.raw or {}), "clock_ambiguity": found})


def range_boundary(raw: dict[str, Any] | None) -> bool:
    """`[2026-10-26 fix5 · 수용 T04]` 해석의 기준 시각이 **범위 경계**인가 — anchor_kind=time · relation before/after · 유효한 HH:MM.

    change_time 의 새 시작 시각은 relation=at 의 anchor_time 이다(`decision_unit.SYSTEM`). before/after 의 기준 시각은 범위 경계이며
    「옮길 새 시작이나 종료가 아니다」(위 `SYSTEM`). 칸 구조만 본다 — 문장을 읽지 않는다."""
    raw = raw or {}
    return (raw.get("anchor_kind") == "time" and raw.get("relation") in ("before", "after")
            and bool(TIME.fullmatch(str(raw.get("anchor_time") or ""))))


def range_anchor_conflict(decision) -> dict[str, Any] | None:
    """실행될 시간 변경이 범위(scope=range)가 아닌데 기준 시각이 범위 경계다 — 한 일정만인지 경계 전후 전부인지 해석이 정하지 못했다.

    ☆실 E4B J 2차 T04 「1월 2일 오후 2시 이전 일정들을 전부 한 시간 당겨줘」 → change_time · target i2 · time_edit start/item ·
      anchor_time 14:00 · relation before → `chat_edit.ops_for` 가 인사동을 14:00 으로 옮기려 했다. 범위로 고쳐 실행하지 않는다(Codex fix5 G2)."""
    raw = decision.raw or {}
    spec = raw.get("time_edit") or {}
    # 한 일정(scope=item)만 본다 — following 은 기준 일정(anchor_item) 경로, range 는 경계 시각을 쓰는 경로다(Codex fix5 q2: 조건을 좁힌다)
    if (spec.get("scope") != "item" or spec.get("boundary", "none") == "none"
            or not _executes_time_edit({**raw, "action": decision.action}) or not range_boundary(raw)):
        return None
    return {"reason": "range_boundary_on_one_item", "anchor_time": raw["anchor_time"], "relation": raw["relation"],
            "scope": spec.get("scope"), "boundary": spec.get("boundary")}


def ask_on_range_anchor(decision):
    """`range_anchor_conflict` 이면 바꾸지 않고 한 일정인지 기준 시각 전후 전부인지 되묻는 clarify 로 바꾼다(선택지 없음 — 고객이 말한다)."""
    found = range_anchor_conflict(decision)
    if found is None:
        return decision
    side = "이전" if found["relation"] == "before" else "이후"
    name = f"「{decision.item.title}」 하나만 옮길지, " if decision.item is not None else ""
    return replace(decision, action="clarify", choices=[],
                   question=(f"{name}{found['anchor_time']} {side} 일정 전부를 옮길지 확실하지 않아 일정은 바꾸지 않았어요. "
                             f"어느 쪽인지 말씀해 주세요."),
                   raw={**(decision.raw or {}), "range_anchor_conflict": found})


def resume(decision, *, items, turns, version: int, now: datetime, ttl_seconds: int):
    spec = (decision.raw or {}).get("time_edit") or {}
    if decision.action != "change_time" or not spec.get("continue_previous"):
        return decision
    previous = next((t for t in reversed(turns) if t.get("role") == "assistant"), {})
    goal = (previous.get("reply") or {}).get("edit_goal") or {}
    try:
        stamp = datetime.fromisoformat(goal["at"])
        valid = (goal["version"] == version and timedelta(0) <= now - stamp <= timedelta(seconds=ttl_seconds))
    except (KeyError, ValueError, TypeError):
        valid = False
    item = next((i for i in items if str(i.item_id) == goal.get("item_id")), None)
    from .trip_facts import _stops
    aliases = {f"i{n}": i for n, i in enumerate(_stops(items), 1)}
    explicit_anchor = aliases.get(decision.raw.get("anchor_item"))
    if explicit_anchor is not None and item is not None and explicit_anchor.item_id != item.item_id:
        valid = False
    saved = goal.get("time_edit") or {}
    # Continuation may add reflow; it cannot silently substitute another explicit goal.
    if (not valid or item is None or spec.get("boundary") != "reflow" or spec.get("scope") != "following"
            or saved.get("boundary") not in {"end", "duration"}):
        return replace(decision, raw={**decision.raw, "stale_edit_goal": True})
    return replace(decision, item=item, raw={**decision.raw, "time_edit": {
        **saved, "scope": "item", "cascade": True, "continue_previous": False,
        "evidence": spec["evidence"]}, "resumed_edit_goal": True})


def pending_goal(decision, *, version: int, now: datetime) -> dict[str, Any] | None:
    spec = (decision.raw or {}).get("time_edit") or {}
    if (decision.item is None or spec.get("boundary") not in {"end", "duration"}
            or decision.raw.get("stale_edit_goal") or decision.raw.get("at_day", "none") not in {"none", "all"}):
        return None
    return {"item_id": str(decision.item.item_id), "version": version, "at": now.isoformat(), "time_edit": spec}


def time_ops(decision, *, items, now: datetime):
    from .chat_edit import EditOp, EditRefused, KST, _hm, _same_day
    from .trip_facts import _stops

    spec = (decision.raw or {}).get("time_edit") or {}
    boundary = spec.get("boundary", "none")
    if boundary == "shift" and spec.get("scope") == "item" and spec.get("time"):
        # A validated absolute clock (quoted and recomputed in `validate`) is the new start, not a shift size.
        boundary = "start"
    if boundary == "shift" and spec.get("scope") == "range":
        if decision.raw.get("stale_edit_goal"):
            # ★`[2026-10-26 L05 이식 · Codex]` 범위 옮기기도 오래된 변경 목표 거절을 먼저 지난다(아래 한 일정 · 뒤 일정 경로와 같다)
            raise EditRefused("need_time_goal", "이전 변경 요청을 현재 일정에서 확인하지 못했어요. 어느 일정에서 몇 시까지 머물지 다시 알려 주세요.")
        from .schedule_query import matching, valid_query
        from .decision_unit import stops_of
        from .chat_edit import shifted

        if not decision.minutes:
            raise EditRefused("need_minutes", "일정을 얼마나 옮길지 알려 주세요.")
        if not valid_query(decision.query, stops_of(items)):
            raise EditRefused("need_target", "옮길 일정의 날짜와 범위를 알려 주세요.")
        targets, _ = matching(decision.query, items=items, now=now)
        anchor_kind = decision.raw.get("anchor_kind")
        relation = decision.raw.get("relation")
        if anchor_kind == "item":
            by_alias = {f"i{n}": stop for n, stop in enumerate(_stops(items), 1)}
            anchor = by_alias.get(decision.raw.get("anchor_item"))
            if anchor is None or relation not in {"before", "after"}:
                raise EditRefused("need_target", "기준으로 삼을 일정을 알려 주세요.")
            targets = [stop for stop in targets if stop.item_id != anchor.item_id
                       and stop.starts_at.astimezone(KST).date() == anchor.starts_at.astimezone(KST).date()
                       and ((stop.starts_at < anchor.starts_at) if relation == "before" else (stop.starts_at > anchor.starts_at))]
        elif anchor_kind == "time":
            clock = decision.raw.get("anchor_time", "")
            if not TIME.fullmatch(clock) or relation not in {"before", "after"}:
                raise EditRefused("need_time", "기준 시각과 이전·이후 범위를 알려 주세요.")
            # An item starting exactly at the boundary clock is not decided by before/after alone.
            on_boundary = [stop for stop in targets if _hm(stop.starts_at) == clock]
            if on_boundary:
                names = "·".join(f"「{stop.title}」" for stop in on_boundary)
                raise EditRefused("need_time_boundary", f"{clock}에 시작하는 {names}도 함께 옮길까요? 포함할지 빼고 옮길지 알려 주세요.")
            targets = [stop for stop in targets if (_hm(stop.starts_at) < clock if relation == "before" else _hm(stop.starts_at) >= clock)]
        elif anchor_kind != "none" or relation != "at":
            raise EditRefused("need_target", "옮길 일정의 범위를 알려 주세요.")
        # ★`[2026-10-26 integ-rm9 · Codex 결정]` 범위 정책은 `chat_edit.shift_range` 한 곳이다(기준 없는 following → query 경로와 같다):
        #   끝난 일정 · 숙소 · 이동은 빼고, 고정 · 예약 · 이미 시작한 일정은 그대로 두고 답에 보이며 나머지를 옮긴다.
        #   하나라도 자정을 넘거나 지난 시각이 되면 전부 그대로 둔다. 바뀐 시각 밖은 맞추지 않는다(reflow 없음)
        from .chat_edit import shift_range

        return shift_range(targets, decision.minutes, now)
    if boundary == "none" or (boundary == "shift" and spec.get("scope") != "following"):
        return None
    if decision.raw.get("stale_edit_goal"):
        raise EditRefused("need_time_goal", "이전 변경 요청을 현재 일정에서 확인하지 못했어요. 어느 일정에서 몇 시까지 머물지 다시 알려 주세요.")
    stops = _stops(items)
    by_alias = {f"i{n}": i for n, i in enumerate(stops, 1)}
    item = (by_alias.get(decision.raw.get("anchor_item")) if spec.get("scope") == "following" else decision.item)
    if (item is None and boundary == "shift" and spec.get("scope") == "following" and decision.item is None
            and decision.raw.get("anchor_item") in (None, "none") and getattr(decision, "query", None) is not None):
        # ★`[2026-10-26 x600 6152ae77]` 기준 일정 없이 following 을 냈지만 검증된 범위(query)가 있다 — 「일정 전부다 1시간씩 미뤄줘」.
        #   기준을 되묻지 않고 범위 이동(`chat_edit.ops_for` 의 query 경로)으로 보낸다. 범위가 없으면 아래에서 그대로 되묻는다(칸 구조만 본다)
        return None
    if item is None:
        raise EditRefused("need_target", "머무는 시각을 바꿀 기준 일정을 알려 주세요.")
    # decision.minutes is source-validated by decision_unit (not raw model minutes).
    # A following reflow must not discard an explicit relative delta; zero-delta
    # reflow/continuation retains the existing anchor-end behavior below.
    if boundary == "shift" or (boundary == "reflow" and spec.get("scope") == "following"
                               and decision.minutes and not spec.get("continue_previous")):
        from .chat_edit import shifted

        if not decision.minutes:
            raise EditRefused("need_minutes", "뒤 일정을 얼마나 옮길지 알려 주세요.")
        after = stops[stops.index(item) + 1:]
        following = [stop for stop in after if stop.starts_at.astimezone(KST).date() == item.starts_at.astimezone(KST).date()
                     and (stop.ends_at or stop.starts_at) > now]
        if not following:
            raise EditRefused("no_following", "같은 날 뒤에 옮길 일정이 없어요.")
        ops = []
        for stop in following:
            if stop.kind not in {"activity", "dining"} or stop.booking_id or stop.locked:
                raise EditRefused("locked_item", "뒤 일정에 예약·고정된 항목이 있어 바꾸지 않았어요.")
            day, begin, until = shifted(stop, decision.minutes)
            if day != stop.starts_at.astimezone(KST).date().isoformat():
                raise EditRefused("crosses_midnight", "뒤 일정이 자정을 넘게 돼 바꾸지 않았어요.")
            _same_day(day, begin, until, stop.title)
            if datetime.fromisoformat(f"{day}T{begin}").replace(tzinfo=KST) < now:
                raise EditRefused("time_in_past", "뒤 일정을 이미 지난 시각으로 옮길 수 없어 바꾸지 않았어요.")
            ops.append(EditOp("time", item_id=stop.item_id, date=day, starts_at=begin, ends_at=until, reflow=True))
        return ops, f"{item.title} 뒤 일정 {len(ops)}개 시각 옮기기"
    if item.kind not in {"activity", "dining"} or item.booking_id or item.locked:
        raise EditRefused("locked_item", "예약·고정된 일정이라 시간을 바꾸지 않았어요.")
    if (item.ends_at or item.starts_at) <= now:
        raise EditRefused("item_in_past", "이미 끝난 일정이라 시간을 바꾸지 않았어요.")
    if boundary == "start":
        from .chat_edit import _day_of, _inside_trip, moved_to

        day = _day_of(decision.raw.get("at_day"), stops, now)
        if not spec.get("time"):
            if decision.raw.get("anchor_kind") == "now":
                return None
            if decision.raw.get("anchor_kind") == "time" and TIME.fullmatch(str(decision.raw.get("anchor_time") or "")):
                return None                     # 구형 시작 시각 칸(anchor_time)만 있으면 기존 시작 시각 변경(`chat_edit.ops_for`)이 날과 함께 쓴다
            if day is None or day == item.starts_at.astimezone(KST).date().isoformat():
                raise EditRefused("need_time", f"「{item.title}」을(를) 시작할 시각을 알려 주세요.")
        # A day-only move keeps the start clock and stay length (`moved_to`).
        day, begin, until = moved_to(item, day=day, start=spec.get("time") or None)
        if not _inside_trip(day, stops):
            raise EditRefused("day_outside_trip", "이 여행에 없는 날이라 바꾸지 않았어요.")
        _same_day(day, begin, until, item.title)
        if datetime.fromisoformat(f"{day}T{begin}").replace(tzinfo=KST) < now:
            raise EditRefused("time_in_past", "이미 지난 시작 시각으로 옮길 수 없어 바꾸지 않았어요. 앞으로 시작할 시각을 알려 주세요.")
        return [EditOp("time", item_id=item.item_id, date=day, starts_at=begin, ends_at=until,
                       reflow=bool(spec.get("cascade")))], f"{item.title} 시작 시각 옮기기"
    # End/duration/reflow currently preserve the anchor day. Do not ignore an explicit other day.
    from .chat_edit import _day_of

    requested_day = _day_of(decision.raw.get("at_day"), stops, now)
    start = item.starts_at.astimezone(KST)
    moved_day = requested_day is not None and requested_day != start.date().isoformat()
    if moved_day:
        # A stay change on another day keeps the start clock on that day, like a day-only move (`moved_to`).
        from .chat_edit import _inside_trip

        if boundary == "reflow":
            raise EditRefused("combined_date_boundary", "다른 날로 옮기면서 뒤 일정만 맞추는 요청은 아직 처리하지 못해 바꾸지 않았어요. 옮길 날과 시각을 알려 주세요.")
        if not _inside_trip(requested_day, stops):
            raise EditRefused("day_outside_trip", "이 여행에 없는 날이라 바꾸지 않았어요.")
        new_start = datetime.fromisoformat(f"{requested_day}T{_hm(start)}").replace(tzinfo=KST)
        end = (new_start + (item.ends_at - item.starts_at)) if item.ends_at else None
        start = new_start
    else:
        end = item.ends_at.astimezone(KST) if item.ends_at else None
    if boundary == "end":
        if not spec.get("time"):
            raise EditRefused("need_end_time", f"「{item.title}」에서 몇 시까지 머무실까요? 종료 시각을 알려 주시면 뒤 일정도 맞출게요.")
        end = start.replace(hour=int(spec["time"][:2]), minute=int(spec["time"][3:]), second=0, microsecond=0)
    elif boundary == "duration":
        if not spec.get("duration_minutes"):
            raise EditRefused("need_duration", f"「{item.title}」에서 얼마나 머무실지 알려 주세요.")
        end = start + timedelta(minutes=spec["duration_minutes"])
    elif boundary != "reflow":
        raise EditRefused("need_time", "바꿀 시각을 알려 주세요.")
    if end is None:
        raise EditRefused("need_end_time", f"「{item.title}」이 끝날 시각을 알려 주세요.")
    if end.date() != start.date():
        raise EditRefused("crosses_midnight", "머무는 시간이 자정을 넘어 일정은 바꾸지 않았어요.")
    _same_day(start.date().isoformat(), _hm(start), _hm(end), item.title)
    if end <= now:
        raise EditRefused("time_in_past", "이미 지난 종료 시각이라 바꾸지 않았어요. 앞으로 머무실 종료 시각을 알려 주세요.")
    if moved_day:
        if start < now:
            raise EditRefused("time_in_past", "이미 지난 시작 시각으로 옮길 수 없어 바꾸지 않았어요. 앞으로 시작할 날과 시각을 알려 주세요.")
        return [EditOp("time", item_id=item.item_id, date=requested_day, starts_at=_hm(start), ends_at=_hm(end),
                       reflow=bool(spec.get("cascade")))], f"{item.title} 날짜·체류 옮기기"
    return [EditOp("time", item_id=item.item_id, ends_at=_hm(end),
                   reflow=bool(spec.get("cascade")) or boundary == "reflow")], f"{item.title} 체류·뒤 일정 맞추기"
