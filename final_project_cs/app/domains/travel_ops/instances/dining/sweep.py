"""하루 점검 — 그날 식사 일정을 한 번에 훑는다. 언제 부를지는 여기서 정하지 않는다.

무엇인가.
    아침(하루 시작 안내)과 전날 밤(다음 날 안내)에 코어가 한 번 부른다.
    그날 식당 항목마다 「그 시각에 여는가」를 원장에 묻고, 닫혔으면 대안을 붙여
    안내에 넣을 줄을 돌려준다. 방문 60분·20분 전 확인은 tick.py 가 따로 한다.

        from app.domains.travel_ops.instances.dining.sweep import sweep_day, meal_lines
        checks = sweep_day(conn, tenant_id, items, day=day, now=now)
        text += meal_lines(checks)

왜 깨우는 쪽이 아닌가.
    tick.py 와 같다. 깨우는 쪽은 코어 몫이다(trip_reminders 의 하루 시작 · 전날 저녁,
    시연 버튼, 크론). 부르는 시각이 8시든 22시든 이 파일은 고치지 않는다.
    한 번 불리면 한 번 판정하고 끝난다. 시계를 보지 않고 now 를 받는다.
    쓰지 않는다 — 보낼 말은 부르는 쪽이 바깥함에 넣는다(두 번 안 가는 것도 그쪽 키가 막는다).

무엇을 믿는가.
    1  원장에 이어진 장소면 원장의 판정(dining_state). 브레이크 · 휴무 · 명절까지 본다.
    2  이어지지 않았으면 코어 장소의 영업시간(attributes.hours · break). 거칠지만 없는 것보다 낫다.
    3  둘 다 없으면 「모름」. 닫혔다고 하지 않는다.
    판정이 어디서 왔는지 source 에 남긴다. 틀렸을 때 어디를 고칠지 알아야 한다.

항목은 코어 Item 모양이면 된다(kind · title · place_id · starts_at · ends_at · place).
코어를 import 하지 않는다 — ledger.py · tick.py 와 같은 경계다.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .ledger import dining_state

KST = ZoneInfo("Asia/Seoul")

#: 식당 항목으로 보는 kind. 코어 일정이 식사를 dining 으로 적는다.
MEAL_KINDS = frozenset({"dining"})

#: 대안은 몇 곳까지 적는가. 안내는 짧아야 한다 — 고르는 것은 사람이다.
ALTERNATIVES = 2

#: 식이 조건 이름. 대안이 없을 때 말에 쓴다. 조건은 여행자 선호도 조사에서 온다.
DIET_LABEL = {"vegetarian_menu": "비건·채식", "halal": "할랄"}


def _hm(moment: datetime | None) -> str:
    return moment.astimezone(KST).strftime("%H:%M") if moment else "?"


def _on(moment: datetime, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    local = moment.astimezone(KST)
    return local.replace(hour=h % 24, minute=m, second=0, microsecond=0) + timedelta(days=h // 24)


def core_open(place: dict[str, Any] | None, start: datetime,
              end: datetime | None) -> tuple[bool | None, str]:
    """코어 장소의 영업시간으로 본 판정. (판정, 이유). 영업시간이 없으면 (None, …)."""
    attrs = (place or {}).get("attributes") or {}
    hours = attrs.get("hours")
    if not hours or len(hours) != 2:
        return None, "영업시간 정보가 없어요"
    end = end or start
    if not (_on(start, hours[0]) <= start and end <= _on(start, hours[1])):
        return False, f"영업시간 {hours[0]}–{hours[1]} 밖이에요"
    rest = attrs.get("break")
    if rest and len(rest) == 2 and _on(start, rest[0]) < end and start < _on(start, rest[1]):
        return False, f"브레이크타임 {rest[0]}–{rest[1]}에 걸려요"
    return True, f"영업시간 {hours[0]}–{hours[1]}"


def _alternatives(conn, place_uid: str, starts_at: datetime,
                  ends_at: datetime | None, conds: list[str]) -> list[str]:
    """원장의 대안 후보(207). 이름만 — 축(가까운 곳 · 비슷한 곳)마다 한 곳.
    식이 조건이 있으면 맞다고 확인된 곳만 나온다(219)."""
    with conn.cursor() as cur:
        cur.execute("SELECT name_ko FROM dining.suggest_alternatives(%s, %s, %s, %s) "
                    "WHERE place_uid IS NOT NULL", (place_uid, starts_at, ends_at, conds))
        names = [row[0] for row in cur.fetchall()]
    seen: list[str] = []
    for name in names:
        if name not in seen:
            seen.append(name)
    return seen[:ALTERNATIVES]


def _resolve(conn, tenant_id: str, core_place_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT place_uid FROM dining.dn_core_place_link "
                    "WHERE tenant_id = %s AND core_place_id = %s", (tenant_id, core_place_id))
        row = cur.fetchone()
    return str(row[0]) if row else None


def check_meal(conn, tenant_id: str, item: Any,
               conds: Iterable[str] = ()) -> dict[str, Any]:
    """식당 항목 하나. 돌려주는 것: 무엇이라고 판정했고, 왜, 어디서 왔는지.
    conds 는 여행자의 식이 조건(예: ["halal"]). 대안을 고를 때만 쓴다."""
    conds = list(conds)
    out: dict[str, Any] = {
        "item_id": str(getattr(item, "item_id", "")), "title": item.title,
        "starts_at": item.starts_at, "status": "unknown", "reason": None,
        "source": None, "alternatives": [], "no_alternative": None}
    place_id = str(item.place_id) if item.place_id else None

    state = dining_state(conn, tenant_id, place_id, item.starts_at, item.ends_at) if place_id else None
    if state and state.get("linked") and state.get("open_at_slot") is not None:
        out["source"] = "dining_ledger"
        if state["open_at_slot"] is False:
            out["status"], out["reason"] = "closed", "그 시각에 영업하지 않아요"
            place_uid = _resolve(conn, tenant_id, place_id)
            if place_uid:
                out["alternatives"] = _alternatives(conn, place_uid, item.starts_at,
                                                    item.ends_at, conds)
                diet = [DIET_LABEL[c] for c in conds if c in DIET_LABEL]
                if not out["alternatives"] and diet:
                    out["no_alternative"] = f"근처에 확인된 {'·'.join(diet)} 식당이 없어요"
        elif state.get("needs_check") or state.get("needs_holiday_check"):
            out["status"] = "check"
            out["reason"] = ("명절이라 영업하는지 확인이 필요해요" if state.get("needs_holiday_check")
                             else "마감이 가까워 마지막 주문 시각을 확인해 주세요")
        else:
            out["status"], out["reason"] = "open", "영업 중이에요"
        return out

    opened, why = core_open(item.place, item.starts_at, item.ends_at)
    if opened is not None:
        out["source"] = "core_place"
        out["status"] = "open" if opened else "closed"
        out["reason"] = why
        return out

    out["source"] = "dining_ledger" if state and state.get("linked") else None
    out["reason"] = "영업 정보가 없어 확인하지 못했어요. 문을 닫았다는 뜻은 아니에요"
    return out


def sweep_day(conn, tenant_id: str, items: Iterable[Any], *, day: date,
              now: datetime, conds: Iterable[str] = ()) -> list[dict[str, Any]]:
    """그날 식당 항목 중 아직 시작하지 않은 것을 모두 본다. 시각 순."""
    meals = sorted((i for i in items
                    if i.kind in MEAL_KINDS
                    and i.starts_at.astimezone(KST).date() == day
                    and i.starts_at > now),
                   key=lambda i: i.starts_at)
    conds = list(conds)
    return [check_meal(conn, tenant_id, item, conds) for item in meals]


_MARK = {"open": "영업 확인", "closed": "영업 안 함", "check": "확인 필요", "unknown": "확인 못 함"}


def meal_lines(checks: list[dict[str, Any]]) -> str:
    """안내에 붙일 줄. 식당 항목이 없으면 빈 문자열."""
    if not checks:
        return ""
    lines = ["", "", "식당 점검"]
    for c in checks:
        line = f"· {_hm(c['starts_at'])} {c['title']} — {_MARK[c['status']]}"
        if c["status"] != "open" and c["reason"]:
            line += f" ({c['reason']})"
        if c["alternatives"]:
            line += f"\n  대안: {', '.join(c['alternatives'])}"
        elif c.get("no_alternative"):
            line += f"\n  {c['no_alternative']}"
        lines.append(line)
    if any(c["status"] == "closed" for c in checks):
        lines.append("영업하지 않는 식당은 대안으로 바꿀지 알려 주세요.")
    return "\n".join(lines)


__all__ = ["sweep_day", "check_meal", "meal_lines", "core_open"]
