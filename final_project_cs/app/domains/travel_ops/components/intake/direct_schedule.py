"""직접 고른 장소의 이동 간격을 맞춘다. 숙박업체 판정 없이 좌표로 이동한다.

원문 판은 바꾸지 않고 시각 편집 목록만 돌려준다. 머무는 시간과 같은 날의
순서를 보존하며 잠금·예약 일정은 기준점으로 쓴다. 실패하면 호출자가 저장하지 않는다.
"""
from __future__ import annotations

from typing import Any

from .moves import leg_between


class ScheduleConflict(ValueError):
    def __init__(self, message: str, *, code: str = "schedule_conflict") -> None:
        super().__init__(message)
        self.code = code


def key(row: dict[str, Any]) -> tuple[str, int]:
    return str(row["source_id"]), row["index"]


def fit(conn, *, tenant_id: str, rows: list[dict[str, Any]], touched: set[tuple[str, int]],
        party_size: int | None = None, engine: Any = None, use_engine: bool = True,
        mode_picks: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """날짜별 시각순 rows를 앞뒤로 맞추고 시각 claim만 반환한다.

    계산기가 꺼진 경우 기존 이동 계약대로 어림 근거를 남긴다. 켜진 계산기의 오류나
    시간 상한 소진은 자동 배치 성공으로 바꾸지 않는다. 운영시간의 확인된 제약도 지킨다.
    """
    from . import review
    from .autofix import ENGINE_BUDGET_S, earliest_start, latest_end
    from .hours import facts_for
    from ..itinerary.itinerary_checks import Part, check_itinerary

    defaulted = engine is None and use_engine
    if defaulted:
        engine = review.default_engine(party_size)
    budget = review._Budgeted(engine, ENGINE_BUDGET_S) if engine is not None else None
    by_mode: dict[str, Any] = {}
    days = {r["date"] for r in rows if key(r) in touched and r["date"]}
    out: list[dict[str, Any]] = []

    def point(row):
        p = row["place"]
        return {"key": f"{row['source_id']}:{row['index']}", "name": p["name"],
                "lat": float(p["latitude"]), "lon": float(p["longitude"])}

    def engine_for(a, b):
        def item_id(r):
            return f"{r.get('order', (0,))[0]}-{r['index']}"
        mode = (mode_picks or {}).get(f"{item_id(a)}~{item_id(b)}") if defaulted else None
        if not mode:
            return budget
        if mode not in by_mode:
            eng = review.default_engine(party_size, [mode])
            if eng is None:
                raise ScheduleConflict("고른 이동수단을 계산하지 못해 변경을 저장하지 않았어요.", code="schedule_check_failed")
            by_mode[mode] = review._Budgeted(eng, ENGINE_BUDGET_S)
        return by_mode[mode]

    def leg(a, b):
        if not a.get("place") or not b.get("place"):
            return None
        eng = engine_for(a, b)
        got = leg_between(eng, point(a), point(b), a["end_at"], b["start_at"], deep=False)
        if eng is not None and (got.basis == "estimate" or eng.exhausted):
            raise ScheduleConflict("이동 계산을 끝내지 못해 변경을 저장하지 않았어요. 잠시 뒤 다시 시도해 주세요.",
                                   code="schedule_check_failed")
        return got

    def protected(row):
        return row.get("locked") or row.get("booked") is True or bool(row.get("booking_no"))

    def hours_fit(row, start, end):
        facts = facts_for(conn, tenant_id, row["place"], row["kind"], start, end)
        violations = check_itinerary([Part(seq=1, kind=row["kind"], title=row["title"] or "일정",
                                            starts_at=start, ends_at=end,
                                            place={"name": (row["place"] or {}).get("name", ""),
                                                   "attributes": dict(facts.attributes)})])
        return not violations and facts.open_at_slot is not False and facts.order_ok is not False

    for day in sorted(days):
        chain = []
        for r in rows:
            if r["date"] != day:
                continue
            start, end = review._dt(day, r["start"]), review._dt(day, r["end"])
            if start is None or end is None:
                if key(r) in touched:
                    raise ScheduleConflict("날짜와 시작·끝 시각을 먼저 알려 주세요.")
                # 빈 시각이 있는 다른 일정은 검증 화면에 남긴다. 이 항목을 넘어
                # 앞뒤 일정이 붙은 것처럼 계산하지 않는다.
                chain.append({**r, "start_at": start, "end_at": end})
                continue
            chain.append({**r, "start_at": start, "end_at": end, "duration": end - start})
        active = set(touched)
        basis: dict[tuple[str, int], str] = {}

        def shift(row, start, why_basis):
            end = start + row["duration"]
            if start.date().isoformat() != day or end.date().isoformat() != day or end <= start:
                raise ScheduleConflict("이동시간을 넣으면 하루를 넘어요. 시각이나 일정을 조정해 주세요.")
            row["start_at"], row["end_at"] = start, end
            active.add(key(row))
            basis[key(row)] = why_basis

        def backwards(index, end, why_basis):
            row = chain[index]
            if protected(row):
                raise ScheduleConflict("잠금·예약 일정 사이에 이동시간이 부족해요. 변경을 저장하지 않았어요.")
            shift(row, end - row["duration"], why_basis)
            for j in range(index - 1, -1, -1):
                a, b = chain[j], chain[j + 1]
                if a["end_at"] is None or b["start_at"] is None:
                    raise ScheduleConflict("앞 일정의 시각이 없어 이동을 맞출 수 없어요.")
                route = leg(a, b)
                if route is None:
                    if a["end_at"] > b["start_at"]:
                        raise ScheduleConflict("앞 일정의 장소가 없어 겹친 시각을 맞출 수 없어요.")
                    break
                if route.ok:
                    break
                if protected(a):
                    raise ScheduleConflict("잠금·예약 일정 사이에 이동시간이 부족해요. 변경을 저장하지 않았어요.")
                latest = latest_end(engine_for(a, b), a["place"], b["place"], b["start_at"])
                if latest is None:
                    raise ScheduleConflict("앞 일정에서 이동 가능한 시각을 찾지 못했어요.")
                shift(a, latest - a["duration"], route.basis)

        for i in range(1, len(chain)):
            a, b = chain[i - 1], chain[i]
            if key(a) not in active and key(b) not in active:
                continue
            if a["end_at"] is None or b["start_at"] is None:
                raise ScheduleConflict("앞뒤 일정의 시작·끝 시각을 먼저 알려 주세요.")
            route = leg(a, b)
            if route is None:
                if a["end_at"] > b["start_at"]:
                    raise ScheduleConflict("앞뒤 일정의 장소가 없어 겹친 시각을 맞출 수 없어요.")
                continue
            if route.ok:
                continue
            if protected(b):
                latest = latest_end(engine_for(a, b), a["place"], b["place"], b["start_at"])
                if latest is None:
                    raise ScheduleConflict("예약 일정에 도착 가능한 시각을 찾지 못했어요.")
                backwards(i - 1, latest, route.basis)
            else:
                earliest = earliest_start(engine_for(a, b), a["place"], b["place"], a["end_at"])
                if earliest is None:
                    raise ScheduleConflict("다음 일정에 도착 가능한 시각을 찾지 못했어요.")
                earliest = max(b["start_at"], earliest)
                if (earliest + b["duration"]).date().isoformat() != day:
                    # 뒤쪽 여유가 모자라면 날짜를 넘기지 말고 앞의 여유를 쓴다.
                    backwards(i, b["start_at"].replace(hour=23, minute=59), route.basis)
                elif not hours_fit(b, earliest, earliest + b["duration"]) and hours_fit(b, b["start_at"], b["end_at"]):
                    # 닫는 시각·브레이크타임 때문에 뒤로 밀 수 없으면, 현재 방문
                    # 시각을 지키고 앞의 변경 가능한 일정에서 여유를 확보한다.
                    backwards(i, b["end_at"], route.basis)
                else:
                    shift(b, earliest, route.basis)

        # 앞당기면서 생긴 앞 구간도 최종 시각으로 검증한다.
        for a, b in zip(chain, chain[1:]):
            if key(a) not in active and key(b) not in active:
                continue
            route = leg(a, b) if a["end_at"] is not None and b["start_at"] is not None else None
            if route is not None and not route.ok:
                raise ScheduleConflict("앞뒤 이동시간을 함께 맞추지 못해 변경을 저장하지 않았어요.")
        for r in chain:
            if key(r) not in basis:
                continue
            if not hours_fit(r, r["start_at"], r["end_at"]):
                raise ScheduleConflict("이동에 맞춰 시각을 옮기면 운영시간에 맞지 않아요. 다른 시각이나 장소를 골라 주세요.")
            for field, moment in (("starts_at", r["start_at"]), ("ends_at", r["end_at"])):
                value = moment.strftime("%H:%M")
                if value == r["start" if field == "starts_at" else "end"]:
                    continue
                out.append({"source_id": str(r["source_id"]), "field": f"items[{r['index']}].{field}",
                            "value": value, "basis": basis[key(r)]})
    return out
