"""고객이 말한 **기준**(일정 · 끼니 · 시각 · 지금 · 앞 답)과 앞뒤 관계로 **서버가** 답할 일정을 고른다. `[2026-10-14]`

해석 모델은 기준만 적는다 — 답할 일정은 적지 않는다.
- `anchor_kind`: none(기준 없음) · item(고객이 이름이나 끼니로 가리킨 일정) · time(고객이 말한 시각) · now(지금) · previous(앞 답의 일정)
- `anchor_item`: item 일 때 그 일정의 별칭(끼니는 일정 줄의 「점심」「저녁」 표시로 고른다)
- `anchor_time`(HH:MM) · `at_day`: time 일 때 그 시각 · 날
- `relation`(at · before · after) · `steps`(1~3): 기준 그 자체 · 기준 바로 앞 · 기준 바로 뒤, 몇 번째
그 다음은 여기서 일정표로 계산한다: 기준 → 관계 → 답.

☆왜(두 번 고쳤다):
- 1차(at_time 만): 모델이 시각을 보고 일정을 직접 고르자 「오후 3시」에 내일 일정을, 「바로 앞」에 다음 일정을 답했다.
- 3차(배포 011f4e7e): 모델이 「기준」과 「답」을 한 칸에 섞었다 — 「점심 먹고 나서」에 점심 시각 + 「뒤」, 「미술관 바로 앞」에
  이미 앞 일정을 고르고 「앞」까지(재생 106건 중 남은 틀림 31). 그래서 칸을 **기준 전용**으로 나눴다(Codex 와 1회차 합의, D안).

계산 규칙
- 기준이 일정(item · previous): at = 그 일정, before/after = 일정표 순서로 `steps` 칸 앞 · 뒤.
  문장 속 일정 이름이 하나로 잡히는데(`fact_context.named_items`) 모델 기준과 다르면 **되묻는다**(덮어쓰지 않는다).
- 기준이 시각(time · now): at = 그 시각에 걸친 일정(시작 ≤ t ≤ 끝 — 그 시각에 시작하는 것 먼저, 다음 끝나는 것, 없으면 다음 시작),
  before = 그 시각 전에 끝난 일정 중 마지막에서 `steps`, after = 그 시각 뒤에 시작하는 일정 중 첫째에서 `steps`.
- 기준 없음 + 앞뒤만: 「지금」 기준(「다음 일정」). 「지금」 기준인데 다른 날을 말했으면(「내일 첫 일정」) 그날 처음 · 끝에서 센다.
- 모델이 기준 일정 별칭을 적었으면 종류 칸이 비거나 「앞 답」이어도 그 일정을 기준으로 쓴다.
- 계산할 수 없으면(앞 답 없음 · 범위 밖 · 그날 일정 없음) `None` + 사유 — 부른 쪽이 원래 확인 절차로 가거나 되묻는다(지어내지 않는다).
- 모델이 답 일정도 적었고 계산과 다르면 `_cross_check` 가 맞아떨어질 때만 모델 답을 쓴다(재생 v4: 106개 중 계산만 73 → 대조 80,
  배포판 75. 대조 규칙은 개발용 문장만 보고 정했고 확인용 37개에서 28 → 30).
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

from .trip_facts import KST, _stops

RELATIONS = ("at", "before", "after")
KINDS = ("none", "item", "time", "now", "previous")
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def clean(read: dict[str, Any], days: list[str], aliases: list[str] | None = None) -> dict[str, Any]:
    """모델이 낸 칸을 쓸 수 있는 값으로 맞춘다 — 틀린 칸은 비운다(해석 전체를 버리지 않는다). 옛 칸 `at_time` 도 읽는다."""
    raw_time = read.get("anchor_time") if read.get("anchor_time") else read.get("at_time")
    anchor_time = raw_time if isinstance(raw_time, str) and _TIME.match(raw_time or "") else ""
    kind = read.get("anchor_kind") if read.get("anchor_kind") in KINDS else ("time" if anchor_time else "none")
    anchor_item = read.get("anchor_item") if aliases is not None and read.get("anchor_item") in aliases else "none"
    if kind == "item" and anchor_item == "none":
        kind = "none"
    if kind in ("none", "previous") and anchor_item != "none":
        kind = "item"                                  # 기준 일정을 적었으면 그 일정이 기준이다(「앞 답」보다 구체적이다 — 재생 v4 「점심 먹고 나서」)
    if kind == "time" and not anchor_time:
        kind = "none"
    at_day = read.get("at_day") if read.get("at_day") in days else "none"
    relation = read.get("relation") if read.get("relation") in RELATIONS else "at"
    steps = read.get("steps") if isinstance(read.get("steps"), int) and 1 <= read.get("steps") <= 3 else 1
    return {**read, "anchor_kind": kind, "anchor_item": anchor_item, "anchor_time": anchor_time, "at_time": anchor_time,
            "at_day": at_day, "relation": relation, "steps": steps}


def _day(at_day: str, stops: list[Any], now: datetime) -> date | None:
    dates = sorted({s.starts_at.astimezone(KST).date() for s in stops})
    if not dates:
        return None
    today = now.astimezone(KST).date()
    if at_day == "today":
        return today
    if at_day == "tomorrow":
        return today + timedelta(days=1)
    if re.fullmatch(r"d\d+", at_day or ""):
        return dates[0] + timedelta(days=int(at_day[1:]) - 1)
    return today if today in dates else next((d for d in dates if d >= today), dates[0])


def _ends(stop: Any) -> datetime:
    return stop.ends_at or stop.starts_at + timedelta(minutes=60)


def previous_item(turns: Any, items: list[Any], *, version: int, now: datetime, ttl_seconds: int) -> Any | None:
    """앞 답이 남긴 대상(focus) — 같은 일정 판이고 유효 시간 안일 때만(`fact_context.resolve` 와 같은 조건)."""
    previous = next((t for t in reversed(list(turns or [])) if t.get("role") == "assistant"), {})
    focus = (previous.get("reply") or {}).get("focus") or {}
    try:
        age = (now - datetime.fromisoformat(focus["at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        return None
    if focus.get("version") != version or not 0 <= age <= ttl_seconds:
        return None
    return next((i for i in items if str(i.item_id) == str(focus.get("item_id"))), None)


def resolve(read: dict[str, Any], *, items: list[Any], anchor: Any = None, previous: Any = None, named: list[Any] | None = None,
            now: datetime, target: Any = None) -> tuple[Any | None, dict[str, Any] | None]:
    """(고른 일정, 근거). 기준도 앞뒤도 없으면 (None, None) — 모델이 고른 대상을 그대로 쓴다.

    `anchor` 는 anchor_item 별칭이 가리키는 일정, `previous` 는 앞 답 대상, `named` 는 문장에서 이름으로 잡힌 일정들.
    `target` 은 모델이 따로 적은 답 일정 — 계산과 다를 때 `_cross_check` 로 대조한다."""
    kind, relation, steps = read.get("anchor_kind") or "none", read.get("relation") or "at", read.get("steps") or 1
    if kind == "none" and read.get("anchor_time"):
        kind = "time"
    if kind == "none":
        if relation == "at":
            return None, None
        kind = "now"                                   # 기준 없이 「다음」·「앞」만 — 지금 기준
    stops = _stops(items)
    if not stops:
        return None, {"time_anchor": "no_items"}
    basis: dict[str, Any] = {"anchor_kind": kind, "anchor_item": read.get("anchor_item"), "anchor_time": read.get("anchor_time"),
                             "at_day": read.get("at_day"), "relation": relation, "steps": steps}
    base: Any = None
    moment: datetime | None = None
    if kind in ("item", "previous"):
        base = anchor if kind == "item" else previous
        if base is None:
            return None, {**basis, "time_anchor": "no_previous" if kind == "previous" else "no_anchor"}
        if kind == "item" and named is not None and len(named) == 1 and named[0].item_id != base.item_id:
            return None, {**basis, "time_anchor": "anchor_conflict", "named": str(named[0].item_id)}
        index = next((n for n, s in enumerate(stops) if s.item_id == base.item_id), None)
        if index is None:
            return None, {**basis, "time_anchor": "anchor_not_in_trip"}
        index += steps if relation == "after" else -steps if relation == "before" else 0
        basis["matched"] = kind
    else:
        other_day = kind == "now" and (read.get("at_day") or "none") not in ("none", "all", "today")
        if other_day:
            # 「내일 첫 일정」처럼 다른 날을 말했으면 「지금」이 아니라 그날 처음(뒤) · 그날 끝(앞)에서 센다(재생 v4)
            day = _day(read.get("at_day"), stops, now)
            if day is None:
                return None, {**basis, "time_anchor": "no_day"}
            start = datetime.combine(day, time(0, 0), tzinfo=KST)
            moment = start + timedelta(days=1) if relation == "before" else start
            basis["day"] = day.isoformat()
        elif kind == "now":
            moment = now.astimezone(KST)
        else:
            day = _day(read.get("at_day") or "none", stops, now)
            if day is None:
                return None, {**basis, "time_anchor": "no_day"}
            hh, mm = map(int, read["anchor_time"].split(":"))
            moment = datetime.combine(day, time(hh, mm), tzinfo=KST)
            basis["day"] = day.isoformat()
        day_of = (moment - timedelta(seconds=1)).date() if other_day and relation == "before" else moment.date()
        pool = list(range(len(stops))) if kind == "now" and not other_day else [n for n, s in enumerate(stops) if s.starts_at.astimezone(KST).date() == day_of]
        if not pool:
            return None, {**basis, "time_anchor": "no_items_that_day"}
        if relation == "at":
            starting = [n for n in pool if stops[n].starts_at == moment]
            during = [n for n in pool if stops[n].starts_at <= moment < _ends(stops[n])]
            ending = [n for n in pool if _ends(stops[n]) == moment]
            later = [n for n in pool if stops[n].starts_at > moment]
            chosen = starting[:1] or during[-1:] or ending[-1:] or later[:1]
            if not chosen:
                return None, {**basis, "time_anchor": "nothing_at_or_after"}
            index = chosen[0]
        elif relation == "before":
            earlier = [n for n in pool if _ends(stops[n]) <= moment]
            if not earlier:
                return None, {**basis, "time_anchor": "nothing_before"}
            index = earlier[-1] - (steps - 1)
        else:
            later = [n for n in pool if stops[n].starts_at > moment]
            if not later:
                return None, {**basis, "time_anchor": "nothing_after"}
            index = later[0] + (steps - 1)
        basis["matched"] = kind
    if not 0 <= index < len(stops):
        return None, {**basis, "time_anchor": "out_of_range"}
    chosen = stops[index]
    # 모델이 답 일정도 따로 적었으면 계산한 일정과 대조한다 — 모델은 앞뒤 칸을 아무 질문에나 붙이기도 하고(「오후 3시에」 + 뒤),
    #   기준 칸을 틀리게 적기도 한다(「저녁 직전」에 미술관). 답 일정이 기준과 맞아떨어질 때만 그 답을 쓴다(재생 v4 · 아래 판정 규칙).
    pick = _cross_check(target, chosen, stops, kind=kind, base=base if kind in ("item", "previous") else None,
                        day=basis.get("day"), other_day=kind == "now" and "day" in basis,
                        moment=moment if kind == "time" else None)
    if pick is not chosen:
        basis["cross_check"] = {"computed": str(chosen.item_id), "model": str(pick.item_id)}
    return pick, {**basis, "time_anchor": "resolved", "item_id": str(pick.item_id)}


def _cross_check(target: Any, chosen: Any, stops: list[Any], *, kind: str, base: Any, day: str | None, other_day: bool,
                 moment: datetime | None) -> Any:
    """계산한 일정과 모델이 고른 답 일정이 다를 때 고른다(기본은 계산).

    - 기준 「지금」인데 다른 날을 말했으면(「내일 저녁 몇 시야?」): 그날 안에 있는 모델 답 — 「지금」 기준 계산은 그날 첫 · 끝 일정만 안다.
    - 기준이 일정 · 앞 답: 모델 답이 기준과 **다른 일정이고 같은 날**이면 모델 답 — 고객이 가리킨 답을 따로 적은 것이다.
      다른 날이면 계산(앞 대화의 다른 날 일정을 답으로 이어받는 것을 막는다 — 실서버 10-14 「국립현대미술관 바로 앞 일정」).
    - 기준 시각: 모델 답이 그 시각에 걸쳐 있으면 모델 답 — 앞뒤 칸을 덧붙인 것으로 본다(「오전 11시 반에 나 어디 있어?」 + 뒤).
    """
    if target is None or target.item_id == chosen.item_id or not any(s.item_id == target.item_id for s in stops):
        return chosen
    target_day = target.starts_at.astimezone(KST).date().isoformat()
    if kind == "now" and other_day and target_day == day:
        return target
    if base is not None and target.item_id != base.item_id and target_day == base.starts_at.astimezone(KST).date().isoformat():
        return target
    if moment is not None and target.starts_at <= moment <= _ends(target):
        return target
    return chosen
