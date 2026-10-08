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

        from app.domains.travel_ops.instances.dining.ledger import dining_state
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

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any


logger = logging.getLogger(__name__)

#: 라스트오더 주문 여유 기본값(분) — `replan.ORDER_MARGIN_MIN` 과 같아야 한다(시험이 지킨다). 이 파일은 코어를 import 하지 않아 여기 따로 둔다
DEFAULT_ORDER_MARGIN_MIN = 20

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
    if value is None:
        return None
    if isinstance(value, datetime):
        # ★`[2026-10-05 코덱스 검토]` 시간대 없는 시각도 서울 시각으로 읽는다 — 문자열은 그렇게 읽는데 datetime 은 그대로 DB 로 가서,
        #   DB 세션이 UTC 면 서울 정오가 21시로 판정됐다
        return value if value.tzinfo else value.replace(tzinfo=KST)
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
            "dietary": [], "dietary_absent": [], "card_payment": None,
            "confirmed_at": None, "source": "dining_ledger"}


def resolve_place(conn, tenant_id: str, core_place_id: str) -> str | None:
    """코어 장소를 요식 원장 장소로. 이어지지 않았으면 None.

    억지로 이름으로 찾지 않는다. 잘못 이으면 다른 식당의 영업시간으로
    판정하게 되고, 그것은 틀린 답을 자신 있게 말하는 것이다.

    ★아직 이어지지 않았으면 `dining.link_core_place`(220)로 이어 본다(2026-10-01).
      연결은 rebuild 때만 만들어져서, 그 뒤 여행에 들어온 장소는 늘 「모름」이었다.
      관광공사 콘텐츠 ID 가 같은 가게, 아니면 매칭기와 같은 규칙으로 하나만 정해질 때만 잇는다.
      함수나 코어 표가 없는 DB(요식만 세운 DB · 220 이전)에서는 예전처럼 None 이다.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT place_uid FROM dining.dn_core_place_link "
            "WHERE tenant_id = %s AND core_place_id = %s",
            (tenant_id, core_place_id))
        row = cur.fetchone()
    if row:
        return str(row[0])
    try:
        with conn.transaction(), conn.cursor() as cur:   # 실패해도 바깥 트랜잭션을 깨지 않는다
            cur.execute("SELECT dining.link_core_place(%s, %s)", (tenant_id, core_place_id))
            row = cur.fetchone()
    except Exception as exc:   # noqa: BLE001 — 드라이버를 import 하지 않는다(Team 경계). 못 이으면 모름
        # ★`[2026-10-05]` 삼키되 흔적을 남긴다 — 전에는 조용히 「모름」이 돼 연결이 왜 안 되는지 알 수 없었다(원문 · 키 없이 종류만)
        logger.warning("dining link_core_place failed place=%s reason=%s", core_place_id, type(exc).__name__)
        return None
    return str(row[0]) if row and row[0] else None


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
        card_payment          카드 결제 가능 여부. None 은 모름이다
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
                "dietary": [], "dietary_absent": [], "card_payment": None,
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
        cur.execute("SELECT dining.meets_condition(%s, %s)", (place_uid, "card_payment"))
        card_payment = cur.fetchone()[0]

        # ★`[2026-09-28 cs]` 마지막 주문 규칙 — 원장이 「연다」고 해도 도착 + 여유 분이 라스트오더를 넘으면 주문할 수 없다
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
                "dietary": dietary, "dietary_absent": absent, "card_payment": card_payment,
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
        "card_payment": card_payment,
        "confirmed_at": confirmed,
        # 좌표를 바깥에서 채울 때 출처를 남기는 것과 같은 이유다.
        # 우리 값과 코어 값이 한 dict 에 섞이면 틀렸을 때 어디를 고칠지 모른다.
        "source": "dining_ledger",
    }


def dining_states(conn, tenant_id: str, slots: list[dict[str, Any]],
                  order_margin_min: int | None = DEFAULT_ORDER_MARGIN_MIN) -> dict[str, dict[str, Any] | None]:
    """후보별 방문 구간을 한 연결에서 읽는다. 장소마다 하나의 구간을 받는다.

    ★`[2026-10-05]` 라스트오더 주문 여유(`order_ok`, 기본 20분)를 함께 낸다 — 대체 계산(`replan.dining_fits`)이 우리 규칙을 원장 판정에도 걸기 때문이다.
      ★이 파일은 코어(`replan`)를 import 하지 않는 경계라 값을 여기 따로 둔다 — `tests/unit/travel/test_dining_order_margin_same.py` 가 `replan.ORDER_MARGIN_MIN` 과 같은지 지킨다. 요식 표가 없는 DB 는 장소마다 `available=False` 로 돌아온다(모름 — 영업 안 함이 아니다).
    """
    return {str(slot["place_id"]): dining_state(conn, tenant_id, slot["place_id"],
                                               slot.get("at"), slot.get("until"),
                                               order_margin_min=order_margin_min)
            for slot in slots}


def slot_verdicts(conn, slots: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """등록 · 생성기 판정용 — 원장 가게의 그 방문 시각에 여는가. 돌려주는 값 = {seq: 판정}. `[2026-10-02]`

    ★등록할 때는 코어 장소가 아직 없어 `dining_state`(코어 place_id 로 찾는다)를 못 쓴다. 칸마다 원장 가게를 바로 찾는다 —
      `place_uid`(원장 가게 ID, 생성기 후보)가 먼저, 없으면 `content_id`(일정 접수가 싣는 관광공사 ID).
    ★판정은 `dining.open_at_slot` 그대로 — 휴무 · 브레이크 · 자정 넘김 · 폐업을 이미 본다. None 은 모름이다.
    ★원장에 없거나 한 관광공사 ID 가 두 가게로 이어졌으면 결과에 넣지 않는다 — 고르지 않는다(모름).
    """
    out: dict[int, dict[str, Any]] = {}
    with conn.cursor() as cur:
        for slot in slots:
            if slot.get("place_uid"):
                where, key = "p.place_uid::text = %s", str(slot["place_uid"])
            else:
                where, key = ("p.place_uid IN (SELECT r.place_uid FROM dining.dn_source_record r "
                              "WHERE r.source_code = 'tourapi_kor_food' AND r.external_id = %s "
                              "AND r.match_status <> 'rejected')"), str(slot["content_id"])
            cur.execute(
                "SELECT p.record_status = 'closed', dining.open_at_slot(p.place_uid, %s, %s) "
                f"FROM dining.dn_place p WHERE {where} LIMIT 2",
                (slot["at"], slot.get("until"), key))
            rows = cur.fetchall()
            if len(rows) == 1:
                closed, open_at = rows[0]
                out[int(slot["seq"])] = {"open_at_slot": open_at, "closed": bool(closed)}
    return out


def planner_shops(conn) -> list[dict[str, Any]]:
    """일정 생성기의 식당 후보 — 원장의 실제 가게 전부(폐업 · 합성 · 좌표 없음 제외). 읽기만 한다. `[2026-10-02]`

    ★사용자 결정 — 식당은 관광공사 API 를 실시간으로 부르지 않는다. 생성기도 원장에서 고른다.
    ★관광공사 ID 가 없는 가게(미쉐린 · 비건 · 할랄 큐레이션 · 인허가)도 후보다. ID 는 있으면 같이 싣는다.
    ★영업 판정은 여기서 하지 않는다 — 방문 시각이 정해진 뒤 `slot_verdicts` · `open_among` 이 한다.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.place_uid, p.name_ko, p.lat, p.lng, coalesce(p.road_address, p.jibun_address), "
            "       (SELECT min(r.external_id) FROM dining.dn_source_record r "
            "         WHERE r.place_uid = p.place_uid AND r.source_code = 'tourapi_kor_food' "
            "           AND r.external_id IS NOT NULL) "
            "FROM dining.dn_place p "
            "WHERE p.record_status <> 'closed' AND NOT p.is_synthetic AND p.lat IS NOT NULL AND p.lng IS NOT NULL "
            "ORDER BY p.name_ko, p.place_uid")
        rows = cur.fetchall()
        badges = shop_badges(cur)
    return [{"place_uid": str(uid), "name": name, "lat": float(lat), "lng": float(lng),
             "address": address, "content_id": content_id, "badges": badges.get(str(uid), [])}
            for uid, name, lat, lng, address, content_id in rows]


#: 화면 · 일정 생성기가 쓰는 가게 표시. 순서가 곧 화면 순서다. `[2026-10-07]`
BADGE_CODES = ("michelin", "nopo")
_BADGE_LABEL = {"michelin": "미쉐린", "nopo": "노포"}


def shop_badges(cur) -> dict[str, list[dict[str, str]]]:
    """가게별 표시 {place_uid: [{"code", "label", "source"}]}. 읽기만 한다. `[2026-10-07]`

    ★운영에 쓰도록 허용된 출처(`dn_source.production_allowed`)의 살아 있는 「yes」 속성만 — 시험 출처는 화면에 올리지 않는다.
    ★`label` 은 이름 + 상세(「미쉐린 빕 구르망 (2026)」), 상세가 없으면 이름(「노포」). `source` 는 출처 이름 — 화면이 밝힌다.
    """
    cur.execute(
        "SELECT a.place_uid, a.attr_code, a.value_detail, s.display_name FROM dining.dn_attribute a "
        "JOIN dining.dn_source s ON s.source_code = a.source_code "
        "WHERE a.attr_code = ANY(%s) AND a.value_state = 'yes' AND a.retired_at IS NULL AND s.production_allowed "
        "ORDER BY a.place_uid, a.attr_code, a.valid_from DESC", (list(BADGE_CODES),))
    out: dict[str, list[dict[str, str]]] = {}
    for uid, code, detail, source in cur.fetchall():
        badges = out.setdefault(str(uid), [])
        if any(badge["code"] == code for badge in badges):
            continue                     # 같은 표시는 한 번 — 가장 최근 것
        name = _BADGE_LABEL[code]
        label = name if not detail else (detail if detail.startswith(name) else f"{name} {detail}")
        badges.append({"code": code, "label": label, "source": source})
    for badges in out.values():
        badges.sort(key=lambda badge: BADGE_CODES.index(badge["code"]))
    return out


def open_among(conn, place_uids: list[str], at: Any, until: Any = None) -> dict[str, bool | None]:
    """여러 원장 가게가 같은 방문 시각에 여는가 — 한 번에 묻는다(생성기가 닫힌 식사를 바꿀 때). `[2026-10-02]`"""
    if not place_uids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.place_uid::text, dining.open_at_slot(p.place_uid, %s, %s) "
            "FROM dining.dn_place p WHERE p.place_uid::text = ANY(%s)",
            (at, until, [str(uid) for uid in place_uids]))
        return dict(cur.fetchall())


class PlannerLedger:
    """일정 생성기가 원장을 읽는 자리 — 생성기는 이 셋만 부른다(`planner.plan_trip(ledger=…)`). `[2026-10-02]`

    ★생성기와 같은 연결을 쓴다. 요식 표가 없는 DB 에서 SQL 이 실패해도 바깥 트랜잭션을 깨지 않게 저장점 안에서 묻는다.
    ★후보를 못 읽으면 빈 목록(원장 식당 없이 짠다), 판정을 못 읽으면 예외 — 받는 쪽(`with_ledger`)이 「모름」으로 둔다.
    """

    def __init__(self, conn) -> None:
        self._conn = conn

    def shops(self) -> list[dict[str, Any]]:
        try:
            with self._conn.transaction():
                return planner_shops(self._conn)
        except Exception as exc:   # noqa: BLE001 — 드라이버를 import 하지 않는다(Team 경계). 요식 표가 없는 DB
            # ★`[2026-10-05]` 삼키되 흔적을 남긴다(원문 없이 예외 종류만) — 원장 식당 없이 짜인 이유를 알 수 있게
            logger.warning("dining planner shops not read reason=%s", type(exc).__name__)
            return []

    def verdicts(self, slots: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        with self._conn.transaction():
            return slot_verdicts(self._conn, slots)

    def open_among(self, place_uids: list[str], at: Any, until: Any = None) -> dict[str, bool | None]:
        try:
            with self._conn.transaction():
                return open_among(self._conn, place_uids, at, until)
        except Exception as exc:   # noqa: BLE001 — 못 읽으면 모두 모름
            logger.warning("dining open_among not read reason=%s", type(exc).__name__)   # `[2026-10-05]` 흔적을 남긴다
            return {}


#: ★`[2026-10-07]` 이름 찾기 단계 — 정확히 같은 이름 하나가 아니면 모두 확인 필요(`needs_review`)로 낸다
NAME_TYPO_RATIO = 0.2               # 자모 거리 / 긴 쪽 길이 — 이 이하면 오타로 본다(`intake/places.TYPO_RATIO` 와 같다)
NAME_PREFIX_MIN = 4                 # 앞부분 일치로 받는 최소 글자 수(「진옥화할매」 → 「진옥화할매원조닭한마리」)
DISH_RADIUS_M = 800                 # 「근처 칼국수집」 · 「통인시장 기름떡볶이」 — 기준 좌표에서 이 안의 원장 가게
_BRANCH_TAIL = re.compile(r"(본점|직영점|분점|별관|본관|신관|[가-힣a-z0-9]{1,8}점)")
_NEAR_WORDS = ("근처", "주변", "가까운", "아무")


def _name_key(name: str | None) -> str:
    return re.sub(r"[^가-힣a-z0-9]", "", (name or "").lower())


def _base_key(name: str | None) -> str:
    """지점 표시를 뗀 비교 키 — 「소문난성수감자탕 별관」 → 「소문난성수감자탕」. 띄어 쓴 끝말만 뗀다(이름 안의 「점」은 둔다)."""
    text = re.sub(r"[\(\[（【].*?[\)\]）】]", "", name or "").strip()
    parts = text.split()
    if len(parts) > 1 and _BRANCH_TAIL.fullmatch(_name_key(parts[-1])):
        text = " ".join(parts[:-1])
    return _name_key(text)


def _shops(conn) -> list[dict[str, Any]]:
    """이름 찾기 대상 — 폐업 아님 · 합성 아님 · 좌표 있음 · 서울 주소. 관광공사 ID 는 있으면 싣는다(없어도 대상이다)."""
    with conn.transaction(), conn.cursor() as cur:   # 실패해도 바깥 트랜잭션을 깨지 않는다
        cur.execute(
            "SELECT p.place_uid, p.name_ko, p.lat, p.lng, coalesce(p.road_address, p.jibun_address), p.category, "
            "       (SELECT min(r.external_id) FROM dining.dn_source_record r "
            "         WHERE r.place_uid = p.place_uid AND r.source_code = 'tourapi_kor_food' "
            "           AND r.external_id IS NOT NULL) "
            "FROM dining.dn_place p "
            "WHERE p.record_status <> 'closed' AND NOT p.is_synthetic AND p.lat IS NOT NULL AND p.lng IS NOT NULL "
            "  AND coalesce(p.road_address, p.jibun_address, '') LIKE %s", ("서울%",))
        rows = cur.fetchall()
    return [{"place_uid": str(uid), "name": name, "latitude": float(lat), "longitude": float(lng),
             "address": address, "category": category, "content_id": str(cid) if cid else None,
             "key": _name_key(name), "base": _base_key(name)}
            for uid, name, lat, lng, address, category, cid in rows]


def _metres(a: tuple[float, float], b: tuple[float, float]) -> float:
    p = math.pi / 180
    h = (math.sin((b[0] - a[0]) * p / 2) ** 2
         + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2)
    return 12_742_000 * math.asin(math.sqrt(h))


def _pick(shops: list[dict[str, Any]], near: tuple[float, float] | None) -> tuple[dict[str, Any], bool]:
    """여럿 중 하나 — 근처 기준이 있으면 가장 가까운 곳, 없으면 이름이 짧은 곳(본점 표기가 없는 쪽). (고른 곳, 여럿이었나)."""
    if len(shops) == 1:
        return shops[0], False
    if near is not None:
        return min(shops, key=lambda s: _metres(near, (s["latitude"], s["longitude"]))), True
    return sorted(shops, key=lambda s: (len(s["name"]), s["name"]))[0], True


def _found(shop: dict[str, Any], *, match: str, review: bool, note: str | None = None,
           others: int = 0) -> dict[str, Any]:
    """접수(`intake/places._from_tour`)가 읽는 모양 — 관광공사 결과와 같은 칸 + 원장 가게 ID · 확인 필요."""
    return {"content_id": shop["content_id"], "content_type_id": "39", "matched_title": shop["name"],
            "latitude": shop["latitude"], "longitude": shop["longitude"], "address": shop["address"],
            "dining_place_uid": shop["place_uid"], "category": shop["category"], "match": match,
            "needs_review": review, "note": note, "others": others}


def find_place_by_name(conn, name: str | None, *, near: tuple[float, float] | None = None) -> dict[str, Any] | None:
    """일정 접수의 장소 찾기용 — 원장 가게 하나(관광공사 결과 모양 + `dining_place_uid`). 못 찾으면 None.

    ★`[2026-10-01]` 일정 접수가 액티비티 CSV 만 봐서 식당을 하나도 못 찾았다(「토속촌삼계탕」). CSV 에 없을 때 여기를 본다.
    ★`[2026-10-07]` 넓혔다(장소 찾기 평가 v0 — 원장에 있는 가게를 못 꺼냈다). 단계 순서대로, 앞 단계에서 정해지면 멈춘다.
        1 exact   이름(공백 · 기호 뺀 것)이 같다 — 하나면 확정. 여럿이면 근처 기준으로 고르고 확인 필요
        2 branch  지점 표시를 뗀 이름이 같다(「소문난성수감자탕」 = 「소문난성수감자탕 별관」 · 「명동교자」 = 「명동교자 본점」)
        3 prefix  원장 이름이 입력으로 시작한다(4자 이상 — 「진옥화할매」 → 「진옥화할매원조닭한마리」)
        4 typo    자모 거리 비율 0.2 이하인 이름이 하나(「이문설롱탕」 → 「이문설농탕」) — 둘이 똑같이 비슷하면 고르지 않는다
        5 dish    「근처 칼국수집」 · 「통인시장 기름떡볶이」 — 메뉴 말이 이름에 든 가게를 `near` 근처에서(`find_dish_near`)
      2~5 와 「여럿 중 고름」은 **확인 필요**다 — 정확히 같은 이름 하나만 확정한다.
    ★관광공사 ID 가 없는 가게도 낸다 — 원장 가게 ID(`dining_place_uid`)로 등록 때 원장과 잇는다(`trip_api` 등록).
      ☆전에는 관광공사 ID 가 있는 가게만 봤다 — 영업 중 1,767곳 중 204곳(하동관 · 명동교자 본점 …)이 빠졌다.
    ★폐업 · 서울 밖 · 좌표 없음 · 합성 가게는 내보내지 않는다. 요식 표가 없는 DB 에서는 None(「못 찾음」).
    """
    key = _name_key(name)
    if len(key) < 2:
        return None
    try:
        shops = _shops(conn)
    except Exception as exc:   # noqa: BLE001 — 드라이버를 import 하지 않는다(Team 경계). 못 읽으면 못 찾음
        logger.warning("dining find_place_by_name not read reason=%s", type(exc).__name__)
        return None

    exact = [s for s in shops if s["key"] == key]
    if exact:
        shop, many = _pick(exact, near)
        return _found(shop, match="exact", review=many, others=len(exact) - 1,
                      note=f"같은 이름이 {len(exact)}곳 — 어느 곳인지 확인해 주세요" if many else None)
    base = _base_key(name)
    branch = [s for s in shops if s["base"] == base]
    if branch:
        shop, many = _pick(branch, near)
        return _found(shop, match="branch", review=True, others=len(branch) - 1,
                      note=(f"지점이 {len(branch)}곳 — 「{shop['name']}」을 골랐어요. 다르면 고쳐 주세요" if many
                            else f"원장의 「{shop['name']}」로 찾았어요"))
    if len(base) >= NAME_PREFIX_MIN:
        prefix = [s for s in shops if s["base"].startswith(base) or s["key"].startswith(base)]
        if prefix:
            shop, many = _pick(prefix, near)
            return _found(shop, match="prefix", review=True, others=len(prefix) - 1,
                          note=f"「{name}」로 시작하는 「{shop['name']}」로 찾았어요 — 다르면 고쳐 주세요")
    typo = _typo_match(base, shops)
    if typo is not None:
        shop, ratio = typo
        return _found(shop, match="typo", review=True,
                      note=f"오타로 보고 「{shop['name']}」로 찾았어요(자모 거리 비율 {ratio:.2f})")
    if near is not None:
        return find_dish_near(conn, name, near, shops=shops)
    return None


def _typo_match(base: str, shops: list[dict[str, Any]]) -> tuple[dict[str, Any], float] | None:
    """자모 거리 비율이 가장 작은 이름 — 기준 이하이고, 같은 거리의 **다른 이름**이 없을 때만."""
    from app.domains.travel_ops.components.intake.places import edit_distance, jamo

    if len(base) < 3:
        return None
    target = jamo(base)
    scored = []
    for shop in shops:
        if abs(len(shop["base"]) - len(base)) > 2:
            continue
        other = jamo(shop["base"])
        ratio = edit_distance(target, other) / max(len(target), len(other))
        if 0 < ratio <= NAME_TYPO_RATIO:
            scored.append((ratio, shop))
    if not scored:
        return None
    scored.sort(key=lambda s: s[0])
    if len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][1]["base"] != scored[0][1]["base"]:
        return None
    return scored[0][1], scored[0][0]


def dish_words(text: str | None) -> list[str]:
    """입력의 메뉴 말 — 긴 것부터. 「통인시장 기름떡볶이」 → [기름떡볶이, 떡볶이] · 「근처 칼국수집」 → [칼국수]."""
    from app.domains.travel_ops.components.planning.meal_likeness import DISHES

    words = [w for w in re.split(r"\s+", (text or "").strip()) if w and w not in _NEAR_WORDS]
    out: list[str] = []
    for word in reversed(words):                      # 뒤 말이 메뉴다(「통인시장 기름떡볶이」)
        clean = _name_key(re.sub(r"(집|가게|식당|맛집)$", "", word))
        for dish in DISHES:
            if dish in clean:
                for got in (clean, dish):
                    if got and got not in out:
                        out.append(got)
                break
        if out:
            break
    return out


def find_dish_near(conn, text: str | None, near: tuple[float, float], *, radius_m: int = DISH_RADIUS_M,
                   shops: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """메뉴 말이 이름에 든 원장 가게 중 `near` 에서 가장 가까운 곳(반경 안). ★언제나 확인 필요 — 원문이 가게를 말하지 않았다.

    긴 메뉴 말이 먼저다(「기름떡볶이」를 찾고, 없으면 「떡볶이」). 반경 밖이면 고르지 않는다.
    """
    words = dish_words(text)
    if not words:
        return None
    if shops is None:
        try:
            shops = _shops(conn)
        except Exception as exc:   # noqa: BLE001
            logger.warning("dining find_dish_near not read reason=%s", type(exc).__name__)
            return None
    for word in words:
        hits = sorted(((_metres(near, (s["latitude"], s["longitude"])), s) for s in shops if word in s["key"]),
                      key=lambda h: h[0])
        hits = [h for h in hits if h[0] <= radius_m]
        if hits:
            metres, shop = hits[0]
            return _found(shop, match="dish", review=True, others=len(hits) - 1,
                          note=f"「{word}」 가게 중 가까운 「{shop['name']}」({round(metres):,}m) — 다르면 고쳐 주세요")
    return None


def find_license_shop_by_name(conn, name: str | None, *, near: tuple[float, float] | None = None) -> dict[str, Any] | None:
    """원장에 없는 식당을 인허가(사업자 등록) 영업 중 식당에서 이름으로 찾는다 — **이름 찾기 전용**. `[2026-10-05 사용자 지시]`

    ★영업시간을 모른다. 대체 후보 · 영업 판정에는 쓰지 않는다(`dn_license_shop` 마이그레이션 225).
    ★이름이 같은 가게가 하나뿐이면 그것. 여럿이면(체인 · 흔한 이름) `near`(앞 일정의 좌표)가 있을 때만 — 가장 가까운 것이 3km 안이고
      두 번째보다 2배 이상 가까울 때 고른다. 아니면 고르지 않는다(다른 가게로 일정을 짜는 것이 가장 나쁘다).
    ★표가 없거나 못 읽으면 None(「못 찾음」) — 경고 로그는 남긴다.
    """
    key = re.sub(r"[^가-힣a-z0-9]", "", (name or "").lower())
    if len(key) < 2:
        return None
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT mgt_no, name_ko, lat, lng, coalesce(road_address, jibun_address), category "
                        "FROM dining.dn_license_shop WHERE name_key = %s AND lat IS NOT NULL AND lng IS NOT NULL LIMIT 25", (key,))
            rows = cur.fetchall()
    except Exception as exc:   # noqa: BLE001 — 드라이버를 import 하지 않는다(Team 경계)
        logger.warning("dining find_license_shop_by_name not read reason=%s", type(exc).__name__)
        return None
    if not rows:
        return None
    if len(rows) > 1:
        if near is None:
            return None
        import math

        def meters(row) -> float:
            p = math.pi / 180
            h = (math.sin((row[2] - near[0]) * p / 2) ** 2
                 + math.cos(near[0] * p) * math.cos(row[2] * p) * math.sin((row[3] - near[1]) * p / 2) ** 2)
            return 12742000 * math.asin(math.sqrt(h))

        ranked = sorted(rows, key=meters)
        if meters(ranked[0]) > 3000 or (meters(ranked[1]) < 2 * max(meters(ranked[0]), 50)):
            return None
        rows = [ranked[0]]
    mgt_no, title, lat, lng, address, category = rows[0]
    if not str(address or "").startswith("서울"):
        return None
    return {"content_id": str(mgt_no), "content_type_id": "39", "matched_title": title, "latitude": float(lat),
            "longitude": float(lng), "address": address, "license": True, "category": category}


def nearby_shops(conn, tenant_id: str, around: list[tuple[float, float]], *, radius_m: int, limit: int | None = None,
                 visible_core_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """대체 식당 후보 — 기준 좌표들 중 하나에서 `radius_m` 안의 원장 가게, 가까운 순. 읽기만 한다.

    ★`[2026-10-01]` 대체 계산은 코어 `places` 에서만 후보를 찾아, 공용 식당이 1곳뿐인 DB 에서는 후보가 0개였다.
    ★폐업 · 합성 · 좌표 없는 가게는 내보내지 않는다. 그 여행이 이미 보는 코어 장소와 이어진 가게도 뺀다(중복 후보).
    ★영업 판정은 여기서 하지 않는다 — 들여놓은 뒤 `dining_states` 가 방문 시각으로 한다.
    ★기본은 반경 안의 전체 후보 — 영업 판정 전에 개수를 자르면 뒤에 있는 유효 후보를 놓친다.
    """
    if not around:
        return []
    with conn.cursor() as cur:
        cur.execute(
            "WITH pts AS (SELECT * FROM unnest(%s::float8[], %s::float8[]) AS t(lat, lng)) "
            "SELECT p.place_uid, p.name_ko, p.lat, p.lng, "
            "       (SELECT min(r.external_id) FROM dining.dn_source_record r "
            "         WHERE r.place_uid = p.place_uid AND r.source_code = 'tourapi_kor_food' "
            "           AND r.external_id IS NOT NULL), p.category, "
            "       min(dining.distance_m(p.lat, p.lng, pts.lat, pts.lng)) AS d "
            "FROM dining.dn_place p CROSS JOIN pts "
            "WHERE p.record_status <> 'closed' AND NOT p.is_synthetic "
            "  AND p.lat IS NOT NULL AND p.lng IS NOT NULL "
            "  AND dining.distance_m(p.lat, p.lng, pts.lat, pts.lng) <= %s "
            "  AND NOT EXISTS (SELECT 1 FROM dining.dn_core_place_link l "
            "                   WHERE l.tenant_id = %s AND l.place_uid = p.place_uid "
            "                     AND l.core_place_id::text = ANY(%s::text[])) "
            "GROUP BY p.place_uid, p.name_ko, p.lat, p.lng, p.category "
            "ORDER BY d, p.place_uid LIMIT %s",
            ([float(a) for a, _ in around], [float(b) for _, b in around], radius_m,
             tenant_id, [str(i) for i in (visible_core_ids or [])], limit))
        rows = cur.fetchall()
    # ★`[2026-10-07]` 큰 종류(`category` — 한식 · 카페디저트 · 미상 …)를 싣는다 — 대체 순위의 「비슷한 곳」(`meal_likeness`)
    return [{"place_uid": str(uid), "name": name, "latitude": float(lat), "longitude": float(lng),
             "content_id": content_id, "category": category, "distance_m": float(d)}
            for uid, name, lat, lng, content_id, category, d in rows]


def link_core_place_to(conn, tenant_id: str, core_place_id: str, place_uid: str) -> None:
    """들여놓은 코어 장소를 그 원장 가게와 잇는다(이미 이어져 있으면 그대로). 요식 표에만 쓴다."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by) "
            "VALUES (%s, %s, %s, 'nearby') ON CONFLICT ON CONSTRAINT dn_core_place_link_pkey DO NOTHING",
            (tenant_id, str(core_place_id), str(place_uid)))


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
