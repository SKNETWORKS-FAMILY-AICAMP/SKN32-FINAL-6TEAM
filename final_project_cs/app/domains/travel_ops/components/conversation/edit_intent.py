"""Validated time boundaries and spatial search criteria, independent of wording."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import re
from typing import Any

TIME = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d\Z")


def schemas(aliases: list[str]) -> dict[str, Any]:
    def obj(fields):
        return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}

    def enum(values):
        return {"type": "string", "enum": values}

    return {
        "time_edit": obj({"boundary": enum(["none", "start", "end", "duration", "shift", "reflow"]),
                          "scope": enum(["item", "following"]), "time": {"type": "string"},
                          "duration_minutes": {"type": "integer"}, "cascade": {"type": "boolean"},
                          "continue_previous": {"type": "boolean"}, "evidence": {"type": "string"}}),
        "place_search": obj({"relation": enum(["none", "near"]), "anchor_item": enum(aliases),
                             "place_text": {"type": "string"}, "evidence": {"type": "string"}}),
    }


SYSTEM = """
시간 변경의 뜻은 time_edit, 장소 검색의 기준은 place_search에 별도로 보존한다.
time_edit.boundary=start(시작),end(체류 종료),duration(머무는 분수),shift(상대 이동),reflow(뒤 일정 재배치),none(시간 변경 없음).
종료 시각까지 머물겠다는 요청은 end이며 그 시각에 시작하라는 뜻이 아니다. 정확한 시각이 없는 저녁·늦게 등의 표현으로 시각을 만들지 않고 time=""로 낸다.
scope=item은 target_item 자체, following은 anchor_item 다음의 같은 날 일정 전체이며 기준 항목 자체는 제외한다.
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
"""


def validate(raw: dict[str, Any], message: str, aliases: set[str]) -> None:
    """Validate structure and quoted evidence; never infer intent with phrase rules."""
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
            if value.get("boundary") not in {"start", "end", "duration", "shift", "reflow"} or value.get("scope") not in {"item", "following"}:
                raise ValueError("invalid temporal relation")
            if ((value["boundary"] in {"start", "end", "duration"} and value["scope"] != "item")
                    or (value["boundary"] == "reflow" and value["scope"] != "following")
                    or (value.get("continue_previous") and value["boundary"] != "reflow")):
                raise ValueError("inconsistent temporal scope")
            clock = value.get("time", "")
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
    if boundary == "none" or (boundary == "shift" and spec.get("scope") != "following"):
        return None
    if decision.raw.get("stale_edit_goal"):
        raise EditRefused("need_time_goal", "이전 변경 요청을 현재 일정에서 확인하지 못했어요. 어느 일정에서 몇 시까지 머물지 다시 알려 주세요.")
    stops = _stops(items)
    by_alias = {f"i{n}": i for n, i in enumerate(stops, 1)}
    item = (by_alias.get(decision.raw.get("anchor_item")) if spec.get("scope") == "following" else decision.item)
    if item is None:
        raise EditRefused("need_target", "머무는 시각을 바꿀 기준 일정을 알려 주세요.")
    if boundary == "shift":
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

        if not spec.get("time"):
            if decision.raw.get("anchor_kind") == "now":
                return None
            raise EditRefused("need_time", f"「{item.title}」을(를) 시작할 시각을 알려 주세요.")
        day = _day_of(decision.raw.get("at_day"), stops, now)
        day, begin, until = moved_to(item, day=day, start=spec["time"])
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
    if requested_day is not None and requested_day != item.starts_at.astimezone(KST).date().isoformat():
        raise EditRefused("combined_date_boundary", "날짜와 머무는 시간을 함께 바꾸는 요청은 아직 처리하지 못해 바꾸지 않았어요. 일정 수정 화면에서 날짜와 종료 시각을 함께 고쳐 주세요.")
    start = item.starts_at.astimezone(KST)
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
    return [EditOp("time", item_id=item.item_id, ends_at=_hm(end),
                   reflow=bool(spec.get("cascade")) or boundary == "reflow")], f"{item.title} 체류·뒤 일정 맞추기"
