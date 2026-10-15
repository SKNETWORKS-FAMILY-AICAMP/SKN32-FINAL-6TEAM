"""모델이 해석한 조회 범위를 최신 일정에 적용한다. 변경·추천을 실행하지 않는다."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from .trip_facts import KST, _day_label, _stop_line, booking_fact

QUERY_FACTS = ("schedule", "changeability")
PERIODS = {"all": (0, 24), "morning": (0, 12), "afternoon": (12, 18), "evening": (18, 24)}
PERIOD_LABELS = {"all": "전체", "morning": "오전", "afternoon": "오후", "evening": "저녁"}
KINDS = ("all", "activity", "dining", "lodging")


def query_days(stops: list[Any]) -> list[str]:
    dates = [s.item.starts_at.astimezone(KST).date() for s in stops]
    count = (max(dates) - min(dates)).days + 1 if dates else 0
    return ["all", "today", "tomorrow"] + [f"d{i}" for i in range(1, count + 1)]


def query_schema(stops: list[Any]) -> dict[str, Any]:
    return {"type": "object", "properties": {
        "day": {"type": "string", "enum": query_days(stops)},
        "period": {"type": "string", "enum": list(PERIODS)},
        "kind": {"type": "string", "enum": list(KINDS)}},
        "required": ["day", "period", "kind"], "additionalProperties": False}


def valid_query(query: Any, stops: list[Any]) -> bool:
    return (isinstance(query, dict) and set(query) == {"day", "period", "kind"}
            and all(isinstance(v, str) for v in query.values())
            and query["day"] in query_days(stops) and query["period"] in PERIODS
            and query["kind"] in KINDS)


def reply(fact: str, query: dict[str, str], *, items: list[Any], now: Any) -> tuple[str, dict[str, Any]]:
    from app.domains.travel_ops.components.planning.pending import protected_reason

    stops = sorted((i for i in items if i.kind != "mobility"), key=lambda i: (i.starts_at, i.seq))
    day = query["day"]
    wanted = None
    if day in ("today", "tomorrow"):
        wanted = now.astimezone(KST).date() + timedelta(days=day == "tomorrow")
    elif day.startswith("d") and stops:
        wanted = stops[0].starts_at.astimezone(KST).date() + timedelta(days=int(day[1:]) - 1)
    start, end = PERIODS[query["period"]]
    matches = [i for i in stops
               if (wanted is None or i.starts_at.astimezone(KST).date() == wanted)
               and start <= i.starts_at.astimezone(KST).hour < end
               and (query["kind"] == "all" or i.kind == query["kind"])]
    head = f"{_day_label(wanted) if wanted else '전체 여행 날짜'} {PERIOD_LABELS[query['period']]}"
    basis = {"kind": fact, "query": dict(query), "writer": "template",
             "source": "latest_itinerary", "item_ids": [str(i.item_id) for i in matches], "checks": []}
    if not matches:
        return f"{head} 범위에는 등록된 일정이 없어요. 일정을 바꾸지는 않았어요.", basis
    lines = [f"{head} 일정 {len(matches)}개를 확인했어요."]
    for item in matches:
        label = f"· {_day_label(item.starts_at.astimezone(KST).date())} {_stop_line(item)}"
        if fact == "schedule":
            lines.append(label)
            continue
        protection = protected_reason(item)
        booked = booking_fact(item)[0] == "있음"
        if protection == "customer_pinned":
            state, note = "pinned", "고정한 일정 — 고정 해제 의사를 먼저 확인해야 해요."
        elif protection or booked:
            state, note = "confirm_first", "예약·보호 일정 — 변경 의사와 예약 조건을 먼저 확인해야 해요."
        elif item.kind not in ("dining", "activity"):
            state, note = "unsupported", "현재 자동 대체 검토를 지원하는 종류가 아니에요."
        elif not item.place:
            state, note = "missing_place", "장소가 연결되지 않아 대체 검토 전에 장소 확인이 필요해요."
        else:
            state, note = "reviewable", "대체 일정 검토 가능 — 예약 기록이 없으므로 실제 예약 여부는 확인해야 해요."
        lines.append(f"{label} — {note}")
        basis["checks"].append({"item_id": str(item.item_id), "state": state, "protected_by": protection})
    if fact == "changeability":
        lines.append("아직 바꾸지는 않았어요. 실제 변경 전에는 후보의 시간·이동 조건도 확인해요.")
    return "\n".join(lines), basis
