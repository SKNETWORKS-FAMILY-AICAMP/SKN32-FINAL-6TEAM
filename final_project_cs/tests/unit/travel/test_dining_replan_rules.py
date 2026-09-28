"""대체 식당 규칙 (2026-09-28 사용자 결정) — 가격 · 라스트오더 20/60분 · 요식 원장 후보.

- 식당은 가격으로 탈락시키지도 줄 세우지도 않는다
- 라스트오더를 알면 도착 + 20분이 넘을 때 탈락, 모르면 마감 60분 안이면 경고만
- 요식 원장이 후보를 내면 그중에서 하나를 고르고, 원장이 못 주면 장소 목록으로 돌아간다
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.modules.travel_ops.itinerary import Item
from app.modules.travel_ops.itinerary_changes import NoChange, plan_closed_on_day
from app.modules.travel_ops.replan import (LAST_ORDER_WARN_MIN, ORDER_MARGIN_MIN, choose,
                                           dining_candidates, dining_fits, dining_warnings)

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 10, 7, tzinfo=KST)          # 수요일


def at(hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return DAY.replace(hour=h, minute=m)


def place(name: str, *, lat=37.5700, lon=126.9800, **attributes) -> dict:
    return {"place_id": str(uuid4()), "name": name, "kind": "dining",
            "latitude": lat, "longitude": lon, "attributes": attributes}


ORIGINAL = place("원래식당", hours=["11:00", "22:00"])


def candidates(places, arrival="12:00", minutes=60, **kw):
    return dining_candidates(original=ORIGINAL, places=places, arrival=at(arrival), minutes=minutes,
                             constraints={}, radius_m=700, next_start=None, **kw)


# ── 가격 ─────────────────────────────────────────────────────
def test_가격을_몰라도_탈락하지_않는다():
    """★전에는 「가격을 몰라 추가 비용을 계산할 수 없다」로 가격 칸이 빈 식당이 전부 빠졌다."""
    got = candidates([place("가격모름", hours=["11:00", "22:00"])])
    assert got[0].rejected == []
    assert got[0].extra_cost_krw is None


def test_식당은_가격이_아니라_가까운_곳이_먼저다():
    near = place("가깝고비쌈", lat=37.5701, hours=["11:00", "22:00"], price_krw=90000)
    far = place("멀고쌈", lat=37.5740, hours=["11:00", "22:00"], price_krw=5000)
    best, _, _ = choose(candidates([far, near]))
    assert best.name == "가깝고비쌈"


# ── 라스트오더: 알면 20분 탈락 ────────────────────────────────
def test_라스트오더를_알면_도착_20분_뒤가_넘을_때_탈락한다():
    p = place("저녁집", hours_week={"wed": {"open": "11:00", "close": "22:00", "last_entry": "21:00"}})
    ok, why = dining_fits(p, at("20:50"), 30)
    assert ok is False and f"{ORDER_MARGIN_MIN}분" in why
    assert dining_fits(p, at("20:40"), 30)[0] is True       # 20:40 + 20분 = 21:00 — 딱 맞으면 통과


def test_라스트오더를_알면_경고하지_않는다():
    p = place("저녁집", hours_week={"wed": {"open": "11:00", "close": "22:00", "last_entry": "21:00"}})
    assert dining_warnings(p, at("20:00"), 30) == []


# ── 라스트오더: 모르면 60분 경고 ──────────────────────────────
def test_라스트오더를_모르고_마감_60분_안에_끝나면_경고만_한다():
    p = place("늦은집", hours=["11:00", "22:00"])
    assert dining_fits(p, at("20:10"), 60)[0] is True       # 탈락은 아니다
    warned = dining_warnings(p, at("20:10"), 60)            # 21:10 에 끝나 마감 22:00 까지 50분
    assert warned and "마지막 주문" in warned[0]
    assert dining_warnings(p, at("19:00"), 60) == []        # 20:00 에 끝나 마감까지 120분


def test_경고_기준은_60분이다():
    p = place("늦은집", hours=["11:00", "22:00"])
    end_at_limit = at("22:00") - timedelta(minutes=LAST_ORDER_WARN_MIN)
    assert dining_warnings(p, end_at_limit - timedelta(minutes=60), 60)      # 딱 60분 — 경고
    assert not dining_warnings(p, end_at_limit - timedelta(minutes=61), 60)  # 61분 — 경고 없음


def test_경고가_붙은_후보는_같은_조건이면_뒤로_간다():
    late = place("마감가까움", hours=["11:00", "21:30"])
    easy = place("여유있음", hours=["11:00", "23:59"])
    best, _, _ = choose(candidates([late, easy], arrival="20:00"))
    assert best.name == "여유있음"


# ── 요식 원장이 후보를 내고 여기서 고른다 ──────────────────────
class FakeLedger:
    def __init__(self, pool, states):
        self.pool, self.states, self.asked = pool, states, []

    def alternatives(self, meal_place, starts_at, ends_at, next_place, conds):
        self.asked.append("alternatives")
        return self.pool

    def state(self, place_id, starts_at, ends_at):
        self.asked.append(place_id)
        return self.states.get(place_id)


def _meal() -> Item:
    return Item(item_id=uuid4(), seq=1, kind="dining", title="점심", place_id=ORIGINAL["place_id"],
                starts_at=at("12:00"), ends_at=at("13:00"), place=ORIGINAL)


def _state(open_at_slot, **extra):
    return {"available": True, "linked": True, "open_at_slot": open_at_slot, "order_ok": True,
            "needs_check": False, "needs_holiday_check": False, **extra}


def test_원장_후보에서_하나를_고르고_나머지는_다른_안이다():
    a, b, c, other = (place(n, hours=["11:00", "22:00"]) for n in ("원장A", "원장B", "원장C", "목록만"))
    pool = [{"place_id": a["place_id"], "axis": "impact", "axis_label": "일정이 가장 덜 밀리는 곳"},
            {"place_id": b["place_id"], "axis": "similar", "axis_label": "비슷한 곳"},
            {"place_id": c["place_id"], "axis": "near", "axis_label": "가장 가까운 곳"}]
    ledger = FakeLedger(pool, {p["place_id"]: _state(True) for p in (a, b, c)})
    plan = plan_closed_on_day(trip={"constraints": {}}, items=[_meal()], places=[a, b, c, other],
                              meal=_meal(), source="test", detail="휴무", checked_at=at("03:00"),
                              ledger=ledger)
    assert not isinstance(plan, NoChange)
    assert plan.summary["candidates_from"] == "dining_ledger"
    assert plan.summary["to"] in {"원장A", "원장B", "원장C"}
    replacement = next(iter(plan.replacements.values()))
    assert {x["name"] for x in replacement.detail["alternates"]} <= {"원장A", "원장B", "원장C"}
    assert all(x.get("axis") for x in replacement.detail["alternates"])
    assert all(x.get("judged_by") == "dining_ledger" for x in replacement.detail["alternates"])


def test_원장이_닫혔다고_한_곳은_고르지_않는다():
    a, b = place("닫힘", hours=["11:00", "22:00"]), place("열림", lat=37.5720, hours=["11:00", "22:00"])
    pool = [{"place_id": a["place_id"], "axis": "near"}, {"place_id": b["place_id"], "axis": "similar"}]
    ledger = FakeLedger(pool, {a["place_id"]: _state(False), b["place_id"]: _state(True)})
    plan = plan_closed_on_day(trip={"constraints": {}}, items=[_meal()], places=[a, b], meal=_meal(),
                              source="test", detail="휴무", checked_at=at("03:00"), ledger=ledger)
    assert plan.summary["to"] == "열림"


def test_원장이_후보를_못_주면_장소_목록으로_돌아간다():
    other = place("목록식당", hours=["11:00", "22:00"])
    ledger = FakeLedger([], {})
    plan = plan_closed_on_day(trip={"constraints": {}}, items=[_meal()], places=[other], meal=_meal(),
                              source="test", detail="휴무", checked_at=at("03:00"), ledger=ledger)
    assert plan.summary == {"to": "목록식당", "candidates_from": "places"}


def test_원장_후보가_전부_떨어지면_장소_목록으로_다시_찾는다():
    a, other = place("원장닫힘", hours=["11:00", "22:00"]), place("목록식당", hours=["11:00", "22:00"])
    ledger = FakeLedger([{"place_id": a["place_id"], "axis": "near"}], {a["place_id"]: _state(False)})
    plan = plan_closed_on_day(trip={"constraints": {}}, items=[_meal()], places=[a, other], meal=_meal(),
                              source="test", detail="휴무", checked_at=at("03:00"), ledger=ledger)
    assert plan.summary["to"] == "목록식당"


def test_원장이_모른다고_하면_기본_영업시간으로_판정한다():
    a = place("원장모름", hours=["11:00", "22:00"])
    ledger = FakeLedger([{"place_id": a["place_id"], "axis": "near"}],
                        {a["place_id"]: {"available": False, "linked": False, "open_at_slot": None}})
    got = candidates([a], ledger=ledger, pool={a["place_id"]: {"axis": "near"}})
    assert got[0].judged_by == "core_place" and got[0].rejected == []


def test_원장의_주문_여유_판정으로_탈락한다():
    a = place("원장", hours=["11:00", "22:00"])
    ledger = FakeLedger([], {a["place_id"]: _state(True, order_ok=False)})
    got = candidates([a], ledger=ledger, pool={a["place_id"]: {"axis": "near"}})
    assert any("주문 여유" in r for r in got[0].rejected)
