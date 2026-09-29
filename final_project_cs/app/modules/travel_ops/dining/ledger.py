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


def ledger_ready(conn) -> bool:
    """요식 표가 이 DB 에 있나. ★`[2026-09-28 cs]` 없으면 조회가 `UndefinedTable` 로 죽었다.

    코드는 저장소에 들어왔는데 마이그레이션 200~219 가 아직 안 올라간 DB 가 있다(공용 개발 DB 가 그랬다).
    그때 Team 이 죽으면 원장 없이 돌던 것까지 멈춘다 — 원장은 더해 주는 것이지 없으면 못 도는 것이 아니다.
    대신 **조용히 넘기지 않는다** — 부르는 쪽이 `available=False` 를 받고 「원장 없음」을 근거에 남긴다.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('dining.dn_core_place_link') IS NOT NULL")
        return bool(cur.fetchone()[0])


def _unavailable(place_id: str | None) -> dict[str, Any]:
    """원장이 없는 DB. 「영업 안 함」이 아니라 「원장에 물을 수 없음」이다."""
    return {"place_id": str(place_id) if place_id is not None else None, "linked": False,
            "available": False, "reason": "요식 표가 이 DB 에 없다(마이그레이션 200~219 미적용)",
            "open_at_slot": None, "order_ok": None, "needs_check": None,
            "needs_holiday_check": None, "holiday_context": None,
            "attributes": {}, "hours": None, "break": None,
            "dietary": [], "dietary_absent": [],
            "confirmed_at": None, "source": "dining_ledger"}


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
                 at: Any = None, until: Any = None,
                 order_margin_min: int | None = None) -> dict[str, Any] | None:
    """그 시각 그 장소의 요식 판정. 어느 장소인지 모르면 None.

    돌려주는 것
        available             요식 표가 이 DB 에 있나. False 면 나머지는 전부 모름이다
        open_at_slot          그 시각에 여는가. None 은 모름이다
        order_ok              `order_margin_min` 을 줬을 때만 — 도착 + 그 분이 라스트오더 안인가.
                              ★`[2026-09-28 cs]` 탈락 기준 20분(replan `ORDER_MARGIN_MIN`)을 원장에도 건다.
                              원장 판정(`open_at_slot`)은 「도착이 라스트오더 전인가」만 보고 주문할 여유는 안 본다
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

    if not ledger_ready(conn):
        return _unavailable(place_id)

    place_uid = resolve_place(conn, tenant_id, str(place_id))
    if place_uid is None:
        # 이어지지 않은 장소다. 「영업 안 함」이 아니라 「모름」이다.
        return {"place_id": str(place_id), "linked": False, "available": True,
                "open_at_slot": None, "order_ok": None, "needs_check": None,
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

        order_ok = None
        if got is not None and got[0] is True and order_margin_min:
            cur.execute("SELECT dining.open_at_slot(%s, %s, %s)",
                        (place_uid, starts_at + timedelta(minutes=int(order_margin_min)), ends_at))
            order_ok = cur.fetchone()[0]

    if got is None:
        return {"place_id": str(place_id), "linked": True, "available": True,
                "open_at_slot": None, "order_ok": None, "needs_check": None,
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
        "available": True,
        "open_at_slot": open_at,
        "order_ok": order_ok,
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


def alternatives_for(conn, tenant_id: str, core_place_id: str | None, at: Any = None,
                     until: Any = None, conds: list[str] | None = None,
                     next_lat: float | None = None, next_lng: float | None = None) -> dict[str, Any]:
    """대체 후보 — 원장이 축마다 하나씩 낸 곳을 **코어 장소 id** 로 돌려준다. `[2026-09-28 cs]`

    ★고르지 않는다. 고르는 것은 코어 `replan.choose` 다(사용자 결정 — 원장은 후보, 고르기는 코어).
    ★코어 장소와 짝이 없는 원장 후보는 일정에 넣을 수 없어 뺀다 — 몇 곳 뺐는지 `unlinked` 로 센다.
    돌려주는 것: `{"available", "reason", "candidates": [{place_id, axis, axis_label, name}], "unlinked"}`
    """
    empty = {"available": True, "reason": None, "candidates": [], "unlinked": 0}
    if core_place_id is None:
        return {**empty, "reason": "원래 장소를 모른다"}
    starts_at, ends_at = _as_datetime(at), _as_datetime(until)
    if starts_at is None:
        return {**empty, "reason": "시각을 모른다"}
    if not ledger_ready(conn):
        return {**empty, "available": False, "reason": _unavailable(None)["reason"]}
    origin = resolve_place(conn, tenant_id, str(core_place_id))
    if origin is None:
        return {**empty, "reason": "원래 식당이 원장과 짝이 없다"}
    codes = [DIETARY.get(c, c) for c in (conds or []) if c in DIETARY and c != "kids"]
    out, unlinked = [], 0
    with conn.cursor() as cur:
        cur.execute("SELECT axis, axis_label, place_uid, name_ko FROM dining.suggest_alternatives("
                    "%s, %s, %s, %s::text[], %s, %s) WHERE place_uid IS NOT NULL",
                    (origin, starts_at, ends_at, codes, next_lat, next_lng))
        rows = cur.fetchall()
        for axis, label, place_uid, name in rows:
            cur.execute("SELECT core_place_id FROM dining.dn_core_place_link "
                        "WHERE tenant_id = %s AND place_uid = %s", (tenant_id, place_uid))
            linked = [str(r[0]) for r in cur.fetchall()]
            if not linked:
                unlinked += 1
                continue
            out += [{"place_id": pid, "axis": axis, "axis_label": label, "name": name} for pid in linked]
    return {**empty, "candidates": out, "unlinked": unlinked,
            "reason": None if out else "원장 후보 중 짝이 있는 곳이 없다"}


#: 여행 등록 때 고객이 적은 식당을 요식 식당과 같은 곳으로 보는 거리. 221 promote_to_core 의 재사용 거리와 같다
SAME_PLACE_M = 150


def ledger_place_for(conn, tenant_id: str, name: str, kind: str,
                     lat: float | None, lon: float | None) -> Any | None:
    """고객이 적은 식당 → 코어로 올린 요식 식당의 장소 번호. 하나로 정해질 때만. `[2026-09-28 cs]`

    ★여행 등록은 식당을 이름·좌표로 넘긴다. 요식 식당은 이름 유일 조건 밖이라(마이그레이션 222) 그대로 넣으면
      같은 이름의 행이 하나 더 생긴다. 그래서 먼저 찾는다 — 이름(공백·기호를 뗀 비교)이 같고 `SAME_PLACE_M` 안.
    ★둘 이상이면(같은 이름 지점이 가까이) 고르지 않는다 — None 이면 예전처럼 새 행을 만든다.
    """
    if kind != "dining" or lat is None or lon is None or not ledger_ready(conn):
        return None
    with conn.cursor() as cur:
        cur.execute(
            "SELECT place_id FROM places WHERE tenant_id=%s AND trip_scope IS NULL "
            "AND source_name='dining_ledger' AND kind='dining' "
            "AND dining.norm_name(name) = dining.norm_name(%s) "
            "AND latitude IS NOT NULL AND longitude IS NOT NULL "
            "AND dining.distance_m(latitude, longitude, %s, %s) <= %s LIMIT 2",
            (tenant_id, name, lat, lon, SAME_PLACE_M))
        rows = cur.fetchall()
    return rows[0][0] if len(rows) == 1 else None          # 다른 장소 번호와 같은 형식(UUID)


def link_trip(conn, tenant_id: str, trip_id: Any) -> dict[str, int] | None:
    """새 여행의 전용 식당을 원장과 잇는다(마이그레이션 221 `link_trip_places`). `[2026-09-28 cs]`

    ★여행 등록 트랜잭션 안에서 부른다. 잇기가 실패해도 **여행 등록은 막지 않는다** — 세이브포인트로 되돌리고
      None 을 돌려준다(원장은 더해 주는 것이다). 요식 표가 없는 DB 도 None.
    """
    if not ledger_ready(conn):
        return None
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT result, n FROM dining.link_trip_places(%s, %s)", (tenant_id, str(trip_id)))
            return {str(r): int(n) for r, n in cur.fetchall()}
    except Exception:                                   # noqa: BLE001 — 잇기 실패로 여행 등록을 막지 않는다
        import logging
        logging.getLogger(__name__).warning("dining link_trip failed for trip %s", trip_id, exc_info=True)
        return None


class DbLedgerView:
    """`itinerary_changes.ledger_pool` 이 부르는 모양 — DB 를 직접 쓰는 쪽(감시 · 신고 창구 · 새벽 확인). `[2026-09-28 cs]`

    Team 은 DB 연결이 없어 같은 모양을 읽기 도구로 만든다(`dining/team.py` `ToolLedgerView`).
    """

    def __init__(self, connection_factory, tenant_id: str, order_margin_min: int = 20) -> None:
        self._connect, self.tenant_id, self.margin = connection_factory, tenant_id, order_margin_min

    def alternatives(self, meal_place: dict[str, Any], starts_at, ends_at,
                     next_place: dict[str, Any] | None, conds: list[str]) -> list[dict[str, Any]]:
        with self._connect() as conn:
            got = alternatives_for(conn, self.tenant_id, meal_place.get("place_id"), starts_at, ends_at,
                                   conds, (next_place or {}).get("latitude"), (next_place or {}).get("longitude"))
        return got["candidates"]

    def state(self, place_id: str, starts_at, ends_at) -> dict[str, Any] | None:
        with self._connect() as conn:
            return dining_state(conn, self.tenant_id, place_id, starts_at, ends_at,
                                order_margin_min=self.margin)


def merge_state(place: dict[str, Any] | None,
                state: dict[str, Any] | None) -> dict[str, Any] | None:
    """코어 장소 정보에 원장 판정을 얹는다. DB 를 쓰지 않는다.

    Team 은 도구로 받은 dict 만 갖고 있고 연결이 없다. 그래서 합치는 일을
    따로 떼어 둔다. 도구를 통해 오든 함수를 직접 부르든 같은 규칙으로 합쳐진다.

    코어가 이미 가진 값을 덮어쓰지 않는다. 비어 있을 때만 채운다.
    덮어쓰면 코어가 확인해 둔 값을 우리가 지우게 되고, 그것은 우리 권한이 아니다.
    """
    if place is None:
        return None
    if state is None or not state.get("linked"):
        return place

    out = dict(place)
    filled = []
    # 코어 SQL 칸 이름은 hours_confirmed_at 이지만 도구가 돌려주는 dict 의 키는
    # confirmed_at 이다 (_PLACE_COLUMNS). 받는 쪽 이름에 맞춘다.
    for core_key, our_key in (("open_at_slot", "open_at_slot"),
                              ("confirmed_at", "confirmed_at")):
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


def enrich_place(conn, tenant_id: str, place: dict[str, Any] | None,
                 at: Any = None, until: Any = None) -> dict[str, Any] | None:
    """`read.place` 결과에 원장을 얹는다. 조회와 합치기를 한 번에 한다.

    `read.place` 가 시각을 받게 되면 이 함수를 그 안에서 부르면 된다.
    시각이 없으면 아무것도 채우지 않는다 — 시각 없이 답할 수 있는 척하지 않는다.
    """
    if place is None:
        return None
    state = dining_state(conn, tenant_id, place.get("place_id"), at, until)
    return merge_state(place, state)
