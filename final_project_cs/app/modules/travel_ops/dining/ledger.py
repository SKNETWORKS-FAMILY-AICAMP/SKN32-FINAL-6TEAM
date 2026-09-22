"""요식 원장을 코어가 읽을 수 있는 모양으로 돌려준다.

무엇인가.
    `places.open_at_slot` 을 채우는 자리다. 지금 그 칸은 아무도 안 채운다 —
    `dining.py` 는 읽고, 시드는 박아 넣고, `tour_api.py` 는 못 채운다고 밝힌다.
    `watch.py` 주석의 「식사 항목의 시스템 감지는 소스가 없다」도 같은 말이다.

왜 칸이 아니라 함수인가.
    `read.place` 는 시각을 받지 않는다. 그런데 「그 시각에 여는가」는 시각이
    있어야 답할 수 있다. 칸 하나에 미리 채워 두면 12시 예약과 22시 예약이
    같은 값을 보게 된다. 그래서 시각을 받는 함수로 둔다.

경계.
    코어 표를 읽지 않는다. 코어 place_id 를 우리 place_uid 로 바꾸는 것은
    `dn_core_place_link` 이고 그것도 요식 표다. 코어 표에 쓰지도 않는다.

쓰는 쪽.
    코어의 도구 계층이 부른다. `read.dining_state` 로 등록하면 된다.

        from app.modules.travel_ops.dining.ledger import dining_state
        ...
        "read.dining_state": self.dining_state,

        def dining_state(self, scope, *, place_id=None, at=None, until=None, **_):
            with self.connection_factory() as conn:
                return dining_state(conn, scope.tenant_id, place_id, at, until)

모르는 것은 모른다고 돌려준다.
    이어지지 않은 장소, 규칙이 없는 요일, 확인한 적 없는 속성은 모두 None 이다.
    받는 쪽이 None 을 「아니다」로 읽으면 안 된다. 그 구분은 Team 이 한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

KST = timezone(timedelta(hours=9))

#: 코어 `dietary` 와 우리 속성 코드의 대응.
#: 코어는 「되는 것」과 「안 되는 것」을 두 목록으로 나눠 받는다. 모르는 것은
#: 어느 목록에도 넣지 않는다 — 그래야 Team 이 모름으로 읽는다.
DIETARY = {
    "halal": "halal",
    "vegetarian": "vegetarian_menu",
    "kids": "kids_allowed",
}


def _as_datetime(value: Any) -> datetime | None:
    """문자열로 온 시각을 datetime 으로. 못 읽으면 None — 지금으로 대체하지 않는다.

    지금 시각으로 대체하면 저녁 예약을 물었는데 점심 영업으로 답한다.
    """
    if value is None or isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        got = datetime.fromisoformat(text)
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=KST)


def resolve_place(conn, tenant_id: str, core_place_id: str) -> str | None:
    """코어 장소를 요식 원장 장소로. 이어지지 않았으면 None.

    억지로 이름으로 찾지 않는다. 잘못 이으면 다른 식당의 영업시간으로
    판정하게 되고, 그것은 틀린 답을 자신 있게 말하는 것이다.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT place_uid FROM dining.dn_core_place_link "
            "WHERE tenant_id = %s AND core_place_id = %s",
            (tenant_id, core_place_id))
        row = cur.fetchone()
    return str(row[0]) if row else None


def dining_state(conn, tenant_id: str, place_id: str | None,
                 at: Any = None, until: Any = None) -> dict[str, Any] | None:
    """그 시각 그 장소의 요식 판정. 어느 장소인지 모르면 None.

    돌려주는 것
        open_at_slot          그 시각에 여는가. None 은 모름이다
        needs_check           종료가 임박해 마지막 주문을 확인해야 하는가
        needs_holiday_check   명절인데 그 장소의 규칙을 모르는가
        holiday_context       무슨 날인지와 확인할 곳. 경고가 아니면 None
        hours                 코어 attributes 형식의 영업시간
        dietary               맞는 것으로 확인된 조건
        dietary_absent        아닌 것으로 확인된 조건
        confirmed_at          영업 정보를 확인한 시각. 현장 확인이 아니다
        source                어디서 온 값인지
    """
    if place_id is None:
        return None                      # 어느 장소인지 모르면 조회하지 않는다
    starts_at = _as_datetime(at)
    if starts_at is None:
        return None                      # 언제인지 모르면 답할 수 없다
    ends_at = _as_datetime(until)

    place_uid = resolve_place(conn, tenant_id, str(place_id))
    if place_uid is None:
        # 이어지지 않은 장소다. 「영업 안 함」이 아니라 「모름」이다.
        return {"place_id": str(place_id), "linked": False,
                "open_at_slot": None, "needs_check": None,
                "needs_holiday_check": None, "holiday_context": None,
                "attributes": {}, "hours": None, "break": None,
                "dietary": [], "dietary_absent": [],
                "confirmed_at": None, "source": "dining_ledger"}

    with conn.cursor() as cur:
        cur.execute(
            "SELECT open_at_slot, needs_check, needs_holiday_check, "
            "       holiday_context, attributes, hours_confirmed_at "
            "FROM dining.core_place_state(%s, %s, %s, %s)",
            (tenant_id, str(place_id), starts_at, ends_at))
        got = cur.fetchone()

        dietary, absent = [], []
        for core_name, attr_code in DIETARY.items():
            cur.execute("SELECT dining.meets_condition(%s, %s)", (place_uid, attr_code))
            meets = cur.fetchone()[0]
            if meets is True:
                dietary.append(core_name)
            elif meets is False:
                absent.append(core_name)
            # None 은 어느 쪽에도 넣지 않는다. 모르는 것은 모르는 것이다.

    if got is None:
        return {"place_id": str(place_id), "linked": True,
                "open_at_slot": None, "needs_check": None,
                "needs_holiday_check": None, "holiday_context": None,
                "attributes": {}, "hours": None, "break": None,
                "dietary": dietary, "dietary_absent": absent,
                "confirmed_at": None, "source": "dining_ledger"}

    open_at, needs_check, needs_holiday, holiday_ctx, attributes, confirmed = got
    # attributes 를 통째로 넘긴다. hours 만 꺼내면 break 가 사라져서,
    # 브레이크타임이 있는 집을 「11:00~22:00 내내 영업」으로 보여 주게 된다.
    # 판정은 open_at_slot 이 맞게 하더라도 화면에 잘못 적히면 사람이 헛걸음한다.
    return {
        "place_id": str(place_id),
        "linked": True,
        "open_at_slot": open_at,
        "needs_check": needs_check,
        "needs_holiday_check": needs_holiday,
        "holiday_context": holiday_ctx,
        "attributes": attributes or {},
        "hours": (attributes or {}).get("hours"),
        "break": (attributes or {}).get("break"),
        "dietary": dietary,
        "dietary_absent": absent,
        "confirmed_at": confirmed,
        # 좌표를 바깥에서 채울 때 출처를 남기는 것과 같은 이유다.
        # 우리 값과 코어 값이 한 dict 에 섞이면 틀렸을 때 어디를 고칠지 모른다.
        "source": "dining_ledger",
    }


def enrich_place(conn, tenant_id: str, place: dict[str, Any] | None,
                 at: Any = None, until: Any = None) -> dict[str, Any] | None:
    """코어 `read.place` 결과에 요식 원장 값을 얹는다.

    코어가 이미 가진 값을 덮어쓰지 않는다. 비어 있을 때만 채운다.
    덮어쓰면 코어가 확인해 둔 값을 우리가 지우게 되고, 그것은 우리 권한이 아니다.

    `read.place` 가 시각을 받게 되면 이 함수를 그 안에서 부르면 된다.
    시각이 없으면 아무것도 채우지 않는다 — 시각 없이 답할 수 있는 척하지 않는다.
    """
    if place is None:
        return None
    state = dining_state(conn, tenant_id, place.get("place_id"), at, until)
    if state is None or not state.get("linked"):
        return place

    out = dict(place)
    filled = []
    for core_key, our_key in (("open_at_slot", "open_at_slot"),
                              ("hours_confirmed_at", "confirmed_at")):
        if out.get(core_key) is None and state.get(our_key) is not None:
            out[core_key] = state[our_key]
            filled.append(core_key)

    # 목록은 합친다. 코어가 아는 것을 지우지 않는다.
    for key in ("dietary", "dietary_absent"):
        merged = list(out.get(key) or [])
        for item in state.get(key) or []:
            if item not in merged:
                merged.append(item)
                filled.append(key)
        out[key] = merged

    # 판정에 쓰지는 않되 Team 이 표시할 수 있게 함께 넘긴다.
    out["dining"] = {k: state[k] for k in
                     ("needs_check", "needs_holiday_check", "holiday_context",
                      "hours", "break")}
    if filled:
        out["dining_source"] = "dining_ledger"
    return out
