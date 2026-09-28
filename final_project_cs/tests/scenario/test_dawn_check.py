# -*- coding: utf-8 -*-
"""새벽 3시 식당 영업 확인. `[2026-09-25]` D-020 · 마이그레이션 026

★구글 키가 아직 없다 — 바깥 호출은 **가짜 응답**으로 본다. 응답 모양은 Places API (New) 공식 문서 기준이고
  `[미확인]` 실제 키로 부른 적이 없다. 키가 들어오면 라이브로 다시 본다.

재현:

    python -m pytest tests/scenario/test_dawn_check.py -v
"""
from __future__ import annotations

from datetime import datetime, time
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.infrastructure.db.session import get_connection
from app.infrastructure.travel.call_budget import CallBudget, google_caps
from app.infrastructure.travel.google_places import GooglePlaces, verdict_from_details
from app.modules.travel_ops.case_engine import cleanup_tenant
from app.modules.travel_ops.dawn_check import DawnCheck
from app.modules.travel_ops.survey import SURVEY_VERSION

from .test_case_version_day import SCENARIO, Clock, _at, _seed

KST = ZoneInfo("Asia/Seoul")
LUNCH = next(p["name"] for p in SCENARIO["places"] if p["key"] == "seongsu_lunch")


class _Open:
    """시험용 — 늘 허락하는 예산(어댑터 모양만 볼 때)."""

    def try_reserve(self, meter):
        return True


OPEN = _Open()


def _k(day: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=KST)


# ── 영업시간 판정 (순수 함수) ─────────────────────────────────────
WED = "2026-09-23"      # 수요일 — 구글 요일 3


def _period(open_day, open_hm, close_day=None, close_hm=None):
    oh, om = map(int, open_hm.split(":"))
    period = {"open": {"day": open_day, "hour": oh, "minute": om}}
    if close_hm is not None:
        ch, cm = map(int, close_hm.split(":"))
        period["close"] = {"day": open_day if close_day is None else close_day, "hour": ch, "minute": cm}
    return period


@pytest.mark.parametrize("payload, start, end, expected", [
    ({"businessStatus": "CLOSED_TEMPORARILY"}, "13:00", "13:50", "closed"),
    ({"businessStatus": "CLOSED_PERMANENTLY"}, "13:00", "13:50", "closed"),
    ({"regularOpeningHours": {"periods": [_period(0, "00:00")]}}, "13:00", "13:50", "open"),      # 24시간
    ({"regularOpeningHours": {"periods": [_period(3, "11:00", None, "21:00")]}}, "13:00", "13:50", "open"),
    ({"regularOpeningHours": {"periods": [_period(3, "11:00", None, "13:30")]}}, "13:00", "13:50", "closed"),
    ({"regularOpeningHours": {"periods": [_period(4, "11:00", None, "21:00")]}}, "13:00", "13:50", "closed"),
    ({"regularOpeningHours": {"periods": [_period(2, "18:00", 3, "02:00")]}}, "00:30", "01:30", "open"),
    ({"currentOpeningHours": {"periods": [{"open": {"day": 3, "hour": 17, "minute": 0,
                                                    "date": {"year": 2026, "month": 9, "day": 23}},
                                           "close": {"day": 3, "hour": 22, "minute": 0,
                                                     "date": {"year": 2026, "month": 9, "day": 23}}}]},
      "regularOpeningHours": {"periods": [_period(3, "11:00", None, "22:00")]}},
     "13:00", "13:50", "closed"),                                    # ★특별 영업일(current)이 이긴다
    ({"businessStatus": "OPERATIONAL"}, "13:00", "13:50", "unknown"),  # 영업시간 칸 없음 — 연다고 하지 않는다
])
def test_the_verdict_covers_the_whole_planned_slot(payload, start, end, expected):
    state, reason = verdict_from_details(payload, start=_k(WED, start), end=_k(WED, end))
    assert state == expected, reason


# ── 어댑터 ───────────────────────────────────────────────────────
def _response(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://example.invalid"))


def test_the_adapter_sends_key_and_field_mask_and_matches_only_nearby():
    seen = []

    def request(method, url, headers, json):
        seen.append((method, url, headers, json))
        return _response(200, {"places": [
            {"id": "far", "location": {"latitude": 37.60, "longitude": 127.10}},
            {"id": "near", "location": {"latitude": 37.5444, "longitude": 127.0549}}]})

    places = GooglePlaces(api_key="k", budget=OPEN, request=request)
    assert places.find_place_id(name=LUNCH, latitude=37.5443, longitude=127.0548)[0] == "near"
    method, _, headers, body = seen[0]
    assert method == "POST" and headers["X-Goog-Api-Key"] == "k" and "places.id" in headers["X-Goog-FieldMask"]
    assert body["locationBias"]["circle"]["radius"] == 300.0

    nothing = GooglePlaces(api_key="k", budget=OPEN, request=lambda *a: _response(200, {"places": [
        {"id": "far", "location": {"latitude": 37.60, "longitude": 127.10}}]}))
    assert nothing.find_place_id(name=LUNCH, latitude=37.5443, longitude=127.0548) == "unmatched"


def test_an_error_body_or_status_is_a_counted_miss_not_a_verdict():
    broken = GooglePlaces(api_key="k", budget=OPEN, request=lambda *a: _response(200, {"error": {"code": 403}}))
    assert broken.open_verdict("x", start=_k(WED, "13:00"), end=_k(WED, "14:00")) is None
    assert broken.misses["body_error"] == 1
    denied = GooglePlaces(api_key="k", budget=OPEN, request=lambda *a: _response(403, {"message": "no"}))
    assert denied.find_place_id(name="x", latitude=37.5, longitude=127.0) is None
    assert denied.misses["http_403"] == 1


def test_no_key_no_adapter():
    with pytest.raises(ValueError):
        GooglePlaces(api_key="", budget=OPEN)


def test_no_budget_no_adapter():
    """★무료 한도를 무조건 지킨다 — 예산 없이 구글을 부르는 어댑터는 만들어지지 않는다."""
    with pytest.raises(ValueError):
        GooglePlaces(api_key="k", budget=None)


# ── 호출 예산 (027) ──────────────────────────────────────────────
@pytest.fixture()
def budget_meter():
    meter = "test_meter_" + uuid4().hex[:8]
    yield meter
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM external_call_budget WHERE meter=%s", (meter,))


def test_the_budget_refuses_once_the_cap_is_reached_and_the_call_is_never_made(budget_meter):
    budget = CallBudget(connection_factory=get_connection, caps={budget_meter: {"month": 100, "day": 2}})
    assert budget.try_reserve(budget_meter) and budget.try_reserve(budget_meter)
    assert budget.try_reserve(budget_meter) is False                       # 하루 2건 찼다
    # ★하루 줄이 차서 거절되면 월 줄도 **올라가지 않는다**(한 트랜잭션)
    assert budget.used(budget_meter) == {"month": 2, "day": 2}

    calls = []
    places = GooglePlaces(api_key="k", budget=budget, request=lambda *a: calls.append(a))
    places._call("GET", "https://x.invalid", "id", budget_meter)
    assert calls == [] and places.misses["budget_exhausted"] == 1          # ★아예 안 불렀다


def test_the_month_cap_holds_across_budget_objects_like_separate_processes(budget_meter):
    """★프로세스마다 새로 세는 제한기와 달리, DB 예산은 **새 객체(= 새 프로세스)도 같이 센다.**"""
    caps = {budget_meter: {"month": 3, "day": 10}}
    used = [CallBudget(connection_factory=get_connection, caps=caps).try_reserve(budget_meter) for _ in range(5)]
    assert used == [True, True, True, False, False]


def test_an_unknown_meter_is_refused():
    budget = CallBudget(connection_factory=get_connection, caps={})
    assert budget.try_reserve("anything") is False


def test_the_configured_caps_stay_under_the_free_tier():
    """★모든 요금 단위: 월 상한 + 하루 상한 ≤ 무료 한도, 하루 ≤ 월 ÷ 31 — 월 경계가 어긋나도 넘지 않게."""
    from app.core.settings import get_guardrails
    from app.infrastructure.travel.call_budget import UNLIMITED
    from app.infrastructure.travel.google_places import METER_DETAILS, METER_SEARCH

    free = get_guardrails().get("travel.google_budget.free_monthly")
    caps = google_caps()
    assert set(caps) == set(free) and len(free) >= 60
    for meter, cap in caps.items():
        if free[meter] is None:
            assert cap == {"month": UNLIMITED, "day": UNLIMITED}
            continue
        assert cap["month"] + cap["day"] <= free[meter], meter
        assert 1 <= cap["day"] <= cap["month"] // 31, meter
    # ★새벽 식당 확인이 실제로 쓰는 둘 — 영업시간(Enterprise 1,000) · 장소 찾기(Pro 5,000)
    assert caps[METER_DETAILS] == {"month": 969, "day": 31}
    assert caps[METER_SEARCH] == {"month": 4844, "day": 156}


# ── 새벽 작업 ────────────────────────────────────────────────────
class FakeSource:
    """이름으로 답하는 가짜 구글. `closed` 에 든 이름은 안 연다. `down=True` 면 못 부른다."""

    def __init__(self, closed=(), unmatched=(), down=False):
        self.closed, self.unmatched, self.down = set(closed), set(unmatched), down
        self.calls = {"find": 0, "verdict": 0}

    def find_place_id(self, *, name, latitude, longitude):
        self.calls["find"] += 1
        if self.down:
            return None
        return "unmatched" if name in self.unmatched else (f"g:{name}", 3.0)

    def open_verdict(self, place_id, *, start, end):
        self.calls["verdict"] += 1
        if self.down:
            return None
        return ("closed", "임시 휴업") if place_id[2:] in self.closed else ("open", "계획한 시각에 영업")


@pytest.fixture()
def world():
    tenant = "dawn_" + uuid4().hex[:10]
    store, customer, trip_id = _seed(tenant)
    clock = Clock(_at("03:05"))
    yield {"tenant": tenant, "store": store, "trip_id": trip_id, "clock": clock}
    cleanup_tenant(tenant)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM place_open_checks WHERE tenant_id=%s", (tenant,))
        cur.execute("DELETE FROM place_provider_ids WHERE tenant_id=%s", (tenant,))


def _dawn(world, source):
    return DawnCheck(store=world["store"], connection_factory=get_connection, clock=world["clock"],
                     source=source, start=time(3, 0), until=time(8, 0))


def _latest(world):
    with get_connection() as conn:
        return world["store"].latest(conn, world["trip_id"])


def test_without_a_key_it_says_so_and_calls_nothing(world):
    result = _dawn(world, None).tick()
    assert result.disabled and "ACOP_GOOGLE_MAPS_API_KEY" in result.disabled


def test_outside_the_dawn_window_it_does_not_call_the_restaurant(world):
    """★팀 결정 — 3시 이후 하루 중에는 식당을 부르지 않는다."""
    source = FakeSource()
    for hhmm in ("02:59", "08:00", "13:00"):
        world["clock"].now = _at(hhmm)
        assert _dawn(world, source).tick().outside_window is True
    assert source.calls == {"find": 0, "verdict": 0}


def test_a_lunch_that_is_closed_today_is_replaced_before_the_day_starts(world):
    source = FakeSource(closed={LUNCH})
    result = _dawn(world, source).tick()
    assert [c["place"] for c in result.closed] == [LUNCH]
    assert len(result.adjusted) == 1 and result.fatal == []
    trip, items = _latest(world)
    assert trip["version"] == 2
    lunch = next(i for i in items if i.starts_at.hour == 13 and i.kind == "dining")
    assert lunch.place["name"] != LUNCH and lunch.starts_at == _at("13:00")    # ★계획한 시각 그대로
    # 판정만 남는다 — 영업시간 원문은 없다
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT verdict, detail FROM place_open_checks WHERE tenant_id=%s ORDER BY checked_at",
                    (world["tenant"],))
        verdicts = cur.fetchall()
    assert ("closed", "임시 휴업") in verdicts

    # ★항목·날짜마다 한 번만 — 다시 돌아도 같은 항목을 또 부르지 않는다(바뀐 새 점심만 한 번 본다)
    before = dict(source.calls)
    _dawn(world, source).tick()
    again = _dawn(world, source).tick()
    assert again.checked == 0 and source.calls["verdict"] - before["verdict"] == 1


def test_the_day_start_notice_carries_what_changed_at_dawn(world):
    """★새벽에 고친 것은 하루 시작 알림(08:00)에 실린다 — 「어제 이후 바뀐 일정이 1건」."""
    from app.modules.travel_ops.trip_reminders import ReminderRules, TripReminders

    _dawn(world, FakeSource(closed={LUNCH})).tick()
    # ★버전 기록 시각은 DB 의 실제 now() 다 — 시험 시계(03:05)에 맞춰 둔다(`test_trip_reminders` 와 같은 방식)
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE itinerary_versions SET created_at=%s WHERE tenant_id=%s AND version=2",
                    (_at("03:05"), world["tenant"]))
    world["clock"].now = _at("08:00")
    TripReminders(store=world["store"], connection_factory=get_connection, clock=world["clock"],
                  route_events=None, rules=ReminderRules(eve_hour=None),
                  link=lambda trip_id: f"https://plan.example/{trip_id}").tick()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT payload_json FROM outbox WHERE tenant_id=%s AND dedupe_key LIKE %s",
                    (world["tenant"], "%day_start%"))
        [(payload,)] = cur.fetchall()
    assert "바뀐 일정이 1건" in payload["text"]


def test_ask_first_asks_instead_of_replacing(world):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trips SET constraints = constraints || %s::jsonb WHERE tenant_id=%s",
                    ('{"survey": {"version": "%s", "on_disruption": "ask_first"}}' % SURVEY_VERSION,
                     world["tenant"]))
    result = _dawn(world, FakeSource(closed={LUNCH})).tick()
    assert len(result.asked) == 1 and result.adjusted == []
    assert _latest(world)[0]["version"] == 1


def test_unmatched_and_failed_calls_are_counted_not_called_open(world):
    source = FakeSource(unmatched={LUNCH}, down=False)
    result = _dawn(world, source).tick()
    assert [u["place"] for u in result.unmatched] == [LUNCH] and result.open >= 1

    down = FakeSource(down=True)
    world2 = {**world, "clock": Clock(_at("03:05"))}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM place_open_checks WHERE tenant_id=%s", (world["tenant"],))
        cur.execute("DELETE FROM place_provider_ids WHERE tenant_id=%s", (world["tenant"],))
    failed = _dawn(world2, down).tick()
    assert failed.fatal and failed.checked == 0
    with get_connection() as conn, conn.cursor() as cur:        # ★못 부른 것은 기록하지 않는다 → 다시 부른다
        cur.execute("SELECT count(*) FROM place_open_checks WHERE tenant_id=%s", (world["tenant"],))
        assert cur.fetchone()[0] == 0
