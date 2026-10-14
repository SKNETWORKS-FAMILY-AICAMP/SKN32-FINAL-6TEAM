"""고객이 말한 날·시각·앞뒤 관계로 **서버가** 답할 일정을 고른다. `[2026-10-14]`

해석 모델은 「오후 3시」 「정오」 「30분 뒤」 같은 말을 날(`at_day`) · 시각(`at_time`, HH:MM)으로 옮기고,
「바로 앞」 「다음」 「다다음」을 관계(`relation`) · 몇 번째(`steps`)로 옮기기만 한다. 그 시각에 어느 일정이 있는지는
일정표를 보고 여기서 계산한다.

☆왜: 모델이 일정을 직접 고르게 했더니 「오후 3시에 뭐 해?」에 오늘 14:30~16:00 미술관 대신 **내일** 15:00 일정을,
「바로 앞 일정」에 다음 일정을 답했다(x600 서버 웹 채팅 재시험 2026-10-14 — 「확인 못 함」은 2% 로 줄었지만 틀린 일정을 확실한 듯 답함).
날짜·시각 비교는 모델보다 일정표 계산이 정확하다.

규칙(고객 말 → 고르는 일정) — `[2026-10-14 재생 107건 뒤 v2]`
- 시각을 말했다: 그 날(말하지 않았으면 「지금」 날짜 — 여행 날이 아니면 여행 첫날) 그 시각에 걸친 일정(시작 ≤ 시각 ≤ 끝).
  그 시각에 시작하는 일정이 있으면 그쪽, 없으면 그 시각에 끝나는 일정(「정오」 = 12:00 에 끝나는 관람). 걸친 것이 없으면
  그 시각 다음에 시작하는 같은 날 일정(관계가 「앞」이면 그 시각 전에 끝난 일정). 시각이 있으면 관계로 다시 옮기지 않는다.
- 시각 없이 모델이 일정을 골랐다: **그 일정을 그대로 쓴다**(None 을 돌려준다). 모델은 「바로 앞」을 이미 반영해 고르면서
  관계까지 적어, 관계를 또 적용하면 두 칸을 넘어갔다(재생 107건 v1: 「미술관 바로 앞」 → 점심을 고르고 「앞」 → 그 앞).
- 시각도 일정도 없이 「다음」·「앞」만 말했다: 「지금」 기준 — 「다음」 = 지금 뒤에 시작하는 첫 일정, 「앞」 = 지금 전에 끝난 마지막 일정.
  `steps` 는 1~3(「다다음」은 2).
- 계산할 수 없으면(일정 없음 · 범위 밖) `None` — 부른 쪽이 원래 확인 절차로 간다(지어내지 않는다).
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

from .trip_facts import KST, _stops

RELATIONS = ("at", "before", "after")
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def clean(read: dict[str, Any], days: list[str]) -> dict[str, Any]:
    """모델이 낸 칸을 쓸 수 있는 값으로 맞춘다 — 틀린 칸은 비운다(해석 전체를 버리지 않는다)."""
    at_time = read.get("at_time") if isinstance(read.get("at_time"), str) and _TIME.match(read.get("at_time") or "") else ""
    at_day = read.get("at_day") if read.get("at_day") in days else "none"
    relation = read.get("relation") if read.get("relation") in RELATIONS else "at"
    steps = read.get("steps") if isinstance(read.get("steps"), int) and 1 <= read.get("steps") <= 3 else 1
    return {**read, "at_time": at_time, "at_day": at_day, "relation": relation, "steps": steps}


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


def resolve(read: dict[str, Any], *, items: list[Any], target: Any, now: datetime) -> tuple[Any | None, dict[str, Any] | None]:
    """(고른 일정, 근거). 계산할 것이 없으면 (None, None) — 모델이 고른 대상을 그대로 쓴다."""
    at_time, relation, steps = read.get("at_time") or "", read.get("relation") or "at", read.get("steps") or 1
    if not at_time and (relation == "at" or target is not None):
        return None, None
    stops = _stops(items)
    if not stops:
        return None, {"time_anchor": "no_items"}
    basis: dict[str, Any] = {"at_day": read.get("at_day"), "at_time": at_time, "relation": relation, "steps": steps}
    if at_time:
        day = _day(read.get("at_day") or "none", stops, now)
        if day is None:
            return None, {**basis, "time_anchor": "no_day"}
        hh, mm = map(int, at_time.split(":"))
        moment = datetime.combine(day, time(hh, mm), tzinfo=KST)
        same_day = [n for n, s in enumerate(stops) if s.starts_at.astimezone(KST).date() == day]
        if not same_day:
            return None, {**basis, "time_anchor": "no_items_that_day", "day": day.isoformat()}
        starting = [n for n in same_day if stops[n].starts_at == moment]
        during = [n for n in same_day if stops[n].starts_at <= moment < _ends(stops[n])]
        ending = [n for n in same_day if _ends(stops[n]) == moment]
        if starting or during or ending:
            index, basis["matched"] = (starting or during or ending)[-1 if not starting else 0], "at_time"
        elif relation == "before":
            earlier = [n for n in same_day if _ends(stops[n]) <= moment]
            if not earlier:
                return None, {**basis, "time_anchor": "nothing_before", "day": day.isoformat()}
            index, basis["matched"] = earlier[-1], "ended_before"
        else:
            later = [n for n in same_day if stops[n].starts_at > moment]
            if not later:
                return None, {**basis, "time_anchor": "nothing_after", "day": day.isoformat()}
            index, basis["matched"] = later[0], "next_after_time"
        basis["day"] = day.isoformat()
    else:
        current = now.astimezone(KST)
        pool = ([n for n, s in enumerate(stops) if s.starts_at > current] if relation == "after"
                else [n for n, s in enumerate(stops) if _ends(s) <= current])
        if not pool:
            return None, {**basis, "time_anchor": f"nothing_{relation}_now"}
        index = pool[0] + (steps - 1) if relation == "after" else pool[-1] - (steps - 1)
        basis["matched"] = "now"
    if not 0 <= index < len(stops):
        return None, {**basis, "time_anchor": "out_of_range"}
    return stops[index], {**basis, "time_anchor": "resolved", "item_id": str(stops[index].item_id)}
