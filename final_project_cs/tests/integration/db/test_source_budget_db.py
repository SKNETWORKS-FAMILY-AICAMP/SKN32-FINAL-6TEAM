# -*- coding: utf-8 -*-
"""소스별 호출 예산 — **실제 DB** 로. `[2026-10-05 사용자 지시 — 한도에 도달하면 API 가 안 돌게 · 키별 호출 횟수 DB 추적]`

가짜 예산으로는 못 보는 것 — 프로세스(연결)를 건너 같은 줄을 세는지 · 한국 시각 자정에 줄이 바뀌는지 · 월·일 줄이 한 트랜잭션으로 함께 움직이는지 · 실패·거절 칸이 맞게 느는지.
★소스 이름은 시험마다 새로 만든다(`t_<무작위>`) — 개발 DB 의 진짜 줄(`its` 등)을 건드리지 않고, 끝나면 그 줄만 지운다.

지키려는 것
 ①하루·월 줄의 경계는 **한국 시각** 자정(UTC 14:59:59 → 15:00:00)이다
 ②두 번째 프로세스(새 제한기 · 새 연결)가 첫 번째가 쓴 만큼을 이어서 센다 — 일꾼이 매번 새로 떠도 한도를 지킨다 · 동시 8 스레드도 상한을 넘지 않는다
 ③하루·월 중 하나라도 차면 **아무 줄도 안 올린다**(월 줄만 오르지 않는다) · 찬 시도는 `rejected` 로 센다(`used` 에는 안 들어간다)
 ④`record_failure` 는 `failed` 만 올리고 `used` 는 그대로다
 ⑤`report` 는 사용 / 상한 / 여유율 / 단계를 주고, 줄이 아직 없는 소스는 0 과 설정 상한으로 보인다
 ⑥조립(`build_travel_sources`)이 ITS · UTIC 등에 실제로 DB 예산을 얹는다 · `build_gate`(따릉이처럼 `TravelSource` 밖에서 직접 부르는 코드)도 같은 문이다

재현:

    python -m pytest tests/integration/db/test_source_budget_db.py -v
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.ports.data_sources.base import TravelSource, build_travel_sources
from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
from app.domains.travel_ops.ports.data_sources.ratelimit import RateLimiter
from app.domains.travel_ops.ports.data_sources.source_budget import BudgetExhausted, BudgetedLimiter, build_gate, with_db_budget

KST = ZoneInfo("Asia/Seoul")


@pytest.fixture()
def meter():
    name = "t_" + uuid4().hex[:10]
    yield name
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM external_call_budget WHERE meter=%s", (name,))


def rows(name: str) -> dict[str, tuple[int, int, int, int]]:
    """{period: (used, cap, failed, rejected)}"""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT period, used, cap, failed, rejected FROM external_call_budget WHERE meter=%s", (name,))
        return {row[0]: tuple(row[1:]) for row in cur.fetchall()}


def budget(name: str, *, day: int, month: int, now: datetime | None = None) -> CallBudget:
    clock = (lambda: now) if now else None
    return CallBudget(connection_factory=get_connection, caps={name: {"day": day, "month": month}}, tz=KST, clock=clock)


# ── ⑦ 낮은 우선순위의 몫(`share`) `[2026-10-06 — MCP 「새로 확인」이 감시 · 채팅 몫을 먹지 않게, 코덱스 검토 반영]` ──────────
def share_budget(name: str, *, day: int, month: int, share: float) -> CallBudget:
    return CallBudget(connection_factory=get_connection, caps={name: {"day": day, "month": month}}, tz=KST, share=share)


def test_a_low_priority_budget_stops_at_its_share_and_the_rest_is_left_for_the_normal_caller(meter):
    low = share_budget(meter, day=10, month=100, share=0.5)
    assert [low.try_reserve(meter) for _ in range(6)] == [True] * 5 + [False]                   # 일 상한 10 × 0.5 = 5 에서 멈춘다
    day = next(v for k, v in rows(meter).items() if k.startswith("day:"))
    assert day[0] == 5 and day[1] == 10 and day[3] == 0                                          # ★줄의 상한은 진짜 값(10) · 몫으로 거절한 것은 rejected 에 안 센다
    normal = budget(meter, day=10, month=100)
    assert [normal.try_reserve(meter) for _ in range(6)] == [True] * 5 + [False]                 # 남은 5 는 일반 호출 몫 — 진짜 한도에서 막힌다
    assert next(v for k, v in rows(meter).items() if k.startswith("day:"))[3] == 1               # 진짜 한도가 차서 거절한 것만 rejected


def test_the_share_also_guards_the_month_row_so_a_low_priority_caller_cannot_eat_the_last_of_the_month(meter):
    low = share_budget(meter, day=1000, month=10, share=0.5)
    assert [low.try_reserve(meter) for _ in range(6)] == [True] * 5 + [False]                   # 하루는 넉넉해도 월 몫(10 × 0.5)이 먼저 찬다
    month = next(v for k, v in rows(meter).items() if k.startswith("month:"))
    assert month[0] == 5 and month[1] == 10
    assert all(budget(meter, day=1000, month=10).try_reserve(meter) for _ in range(5))          # 일반 호출은 월의 나머지를 쓴다


def test_concurrent_low_priority_callers_never_pass_the_share(meter):
    low = share_budget(meter, day=40, month=1000, share=0.5)
    granted, lock = [], threading.Lock()

    def worker():
        for _ in range(5):
            got = low.try_reserve(meter)
            with lock:
                granted.append(got)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(granted) == 20 and next(v for k, v in rows(meter).items() if k.startswith("day:"))[0] == 20      # 40 번 몰려도 몫(40 × 0.5)을 못 넘는다 — 읽고 나서 차감이 아니라 한 SQL 의 조건이라서


def test_an_unlimited_row_is_not_scaled_and_a_bad_share_is_refused(meter):
    from app.domains.travel_ops.ports.data_sources.call_budget import UNLIMITED

    low = CallBudget(connection_factory=get_connection, caps={meter: {"day": 4, "month": UNLIMITED}}, tz=KST, share=0.5)
    assert [low.try_reserve(meter) for _ in range(3)] == [True, True, False]                    # 월 상한을 모르면(UNLIMITED) 곱하지 않는다 — 일 몫(4 × 0.5)만 본다
    for bad in (0, -0.5, 1.5):
        with pytest.raises(ValueError):
            share_budget(meter, day=1, month=1, share=bad)


def test_the_low_priority_door_refuses_when_the_budget_cannot_be_read_even_if_the_normal_policy_allows():
    """일반 호출은 DB 를 못 읽으면 `allow`(안쪽 제한기만) — 낮은 우선순위는 **부르지 않는다**."""
    def broken():
        raise RuntimeError("DB 가 죽었다")

    caps = {"x": {"day": 10, "month": 100}}
    for share, expected in ((1.0, "allowed"), (0.5, "refused")):
        door = BudgetedLimiter(RateLimiter(), CallBudget(connection_factory=broken, caps=caps, tz=KST, share=share), frozenset(caps),
                               on_db_error="refuse" if share < 1.0 else "allow")
        try:
            door.acquire("x")
            outcome = "allowed"
        except Exception:                                                                       # noqa: BLE001 — BudgetUnavailable
            outcome = "refused"
        assert outcome == expected


def test_with_db_budget_forces_refuse_for_a_share(monkeypatch, meter):
    limiter = with_db_budget(RateLimiter(), {meter: 10}, {meter: 100}, [meter], on_db_error="allow", share=0.5)
    assert limiter._on_db_error == "refuse" and limiter._budget.share == 0.5
    assert with_db_budget(RateLimiter(), {meter: 10}, {meter: 100}, [meter], on_db_error="allow")._on_db_error == "allow"


# ── ① 한국 시각 경계 ────────────────────────────────────────────
def test_the_day_row_changes_exactly_at_korean_midnight(meter):
    before = datetime(2026, 10, 5, 14, 59, 59, tzinfo=timezone.utc)          # 한국 2026-10-05 23:59:59
    after = datetime(2026, 10, 5, 15, 0, 0, tzinfo=timezone.utc)             # 한국 2026-10-06 00:00:00
    assert budget(meter, day=5, month=50, now=before).reserve(meter) is True
    assert budget(meter, day=5, month=50, now=after).reserve(meter) is True
    found = rows(meter)
    assert found["day:2026-10-05"][0] == 1 and found["day:2026-10-06"][0] == 1             # 한국 하루 둘로 갈린다(UTC 였다면 한 줄)
    assert found["month:2026-10"][0] == 2                                                  # 같은 한국 달
    assert budget(meter, day=5, month=50, now=before).seconds_to_day_end() == 1.0           # 자정 1초 전
    assert budget(meter, day=5, month=50, now=after).seconds_to_day_end() == 86400.0        # 자정 정각 = 다음 자정까지 하루


def test_the_month_row_changes_at_korean_midnight_of_the_first(meter):
    last = datetime(2026, 10, 31, 14, 59, 59, tzinfo=timezone.utc)           # 한국 10-31 23:59:59
    first = datetime(2026, 10, 31, 15, 0, 0, tzinfo=timezone.utc)            # 한국 11-01 00:00:00
    budget(meter, day=5, month=50, now=last).reserve(meter)
    budget(meter, day=5, month=50, now=first).reserve(meter)
    found = rows(meter)
    assert found["month:2026-10"][0] == 1 and found["month:2026-11"][0] == 1 and found["day:2026-11-01"][0] == 1


# ── ② 프로세스를 건너 센다 ──────────────────────────────────────
def test_a_second_process_continues_the_count_of_the_first(meter):
    first, second = budget(meter, day=3, month=30), budget(meter, day=3, month=30)           # 연결 · 객체가 따로 = 프로세스가 따로
    assert [first.try_reserve(meter), first.try_reserve(meter), second.try_reserve(meter), second.try_reserve(meter)] == [True, True, True, False]
    assert second.refused[meter] == 1


def test_eight_threads_never_exceed_the_cap(meter):
    granted, lock = [], threading.Lock()

    def worker():
        mine = budget(meter, day=20, month=200)
        for _ in range(5):
            ok = mine.try_reserve(meter)
            with lock:
                granted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert granted.count(True) == 20 and granted.count(False) == 20          # 40번 시도 → 정확히 20번만 허락
    found = rows(meter)
    day = next(v for k, v in found.items() if k.startswith("day:"))
    assert day[0] == 20 and day[3] == 20                                      # 사용 20 · 거절 20


# ── ③ 월·일은 함께 움직인다 · 거절은 거절 칸으로 ─────────────────
def test_a_full_month_row_blocks_without_raising_the_day_row(meter):
    mine = budget(meter, day=10, month=2)
    assert [mine.try_reserve(meter) for _ in range(3)] == [True, True, False]
    found = rows(meter)
    day = next(v for k, v in found.items() if k.startswith("day:"))
    month = next(v for k, v in found.items() if k.startswith("month:"))
    assert day[0] == 2 and month[0] == 2                                      # 셋째 시도가 하루 줄만 올리지 않았다
    assert day[3] == 1 and month[3] == 1                                      # 거절은 두 줄 모두 1 — `used` 에는 안 들어갔다


# ── ④ 실패 ──────────────────────────────────────────────────────
def test_a_failure_raises_only_the_failed_column(meter):
    mine = budget(meter, day=5, month=50)
    mine.try_reserve(meter)
    mine.record_failure(meter)
    mine.record_failure(meter)
    for used, cap, failed, rejected in rows(meter).values():
        assert (used, failed, rejected) == (1, 2, 0)


# ── ⑤ 보고 ──────────────────────────────────────────────────────
def test_report_gives_ratio_and_level_and_shows_a_source_with_no_rows_as_zero(meter):
    mine = budget(meter, day=10, month=1000)
    for _ in range(8):
        mine.try_reserve(meter)
    mine.record_failure(meter)
    report = mine.report([meter])
    assert report[0]["meter"] == meter and report[0]["day"] == {"used": 8, "cap": 10, "failed": 1, "rejected": 0, "ratio": 0.8, "level": "warn",
                                                                 "provider_exhausted": False, "learned_cap": None}
    assert report[0]["month"]["level"] == "ok" and report[0]["level"] == "warn"
    for _ in range(2):
        mine.try_reserve(meter)
    assert mine.try_reserve(meter) is False
    full = mine.report([meter])[0]
    assert full["day"]["level"] == "exhausted" and full["day"]["rejected"] == 1 and full["level"] == "exhausted"
    ghost = "t_" + uuid4().hex[:10]
    empty = CallBudget(connection_factory=get_connection, caps={ghost: {"day": 7, "month": 70}}, tz=KST).report([ghost])[0]
    assert empty["day"] == {"used": 0, "cap": 7, "failed": 0, "rejected": 0, "ratio": 0.0, "level": "ok", "provider_exhausted": False, "learned_cap": None}


# ── ⑥ 일꾼 경로 · 조립 · 문 ─────────────────────────────────────
class Probe(TravelSource):
    pass


def test_a_fresh_worker_process_keeps_counting_where_the_last_one_stopped(meter):
    """일꾼은 1분마다 새로 뜬다 — 새 안쪽 제한기는 비어 있어도 DB 가 하루 상한을 지킨다(이 층이 없던 때의 구멍)."""
    Probe.name = meter
    sent: list[str] = []

    def fresh_worker():
        inner = RateLimiter(intervals={}, bursts={})                           # 안쪽은 아무것도 안 막는다 — 막는 것은 DB 뿐
        limiter = with_db_budget(inner, {meter: 3}, {}, [meter], on_db_error="refuse")
        return Probe(transport=lambda url, params: sent.append(url) or httpx.Response(200, json={"ok": 1}), limiter=limiter)

    results = [fresh_worker()._fetch_json("http://example.test", {"q": i}) for i in range(5)]       # 다섯 번 = 새 일꾼 다섯
    assert [r is not None for r in results] == [True, True, True, False, False]
    assert len(sent) == 3                                                       # 4번째부터 바깥으로 안 나갔다
    last = fresh_worker()
    assert last._fetch_json("http://example.test", {"q": 9}) is None and last.misses["budget_exhausted"] == 1
    day = next(v for k, v in rows(meter).items() if k.startswith("day:"))
    assert day[0] == 3 and day[3] == 3                                         # 사용 3 · 거절 3(넷째 · 다섯째 · 여섯째 일꾼)


def test_the_assembly_puts_the_database_budget_on_its_and_utic():
    sources = build_travel_sources(__import__("app.core.settings", fromlist=["get_settings"]).get_settings())
    assert isinstance(sources.limiter, BudgetedLimiter)
    assert {"its", "utic", "subway_notice", "seoul_subway_arrival"} <= sources.limiter.meters


def test_build_gate_serves_code_that_calls_outbound_without_a_travel_source(meter):
    settings = SimpleNamespace(source_rate_limits=lambda: {meter: 2}, source_monthly_limits=lambda: {}, rate_max_wait_seconds=1.0)
    gate = build_gate(settings, [meter])
    gate.acquire(meter)
    gate.acquire(meter)
    with pytest.raises(BudgetExhausted) as caught:
        build_gate(settings, [meter]).acquire(meter)                          # 새 문(= 새 프로세스)도 같은 줄을 이어서 센다
    assert caught.value.reason == "budget_exhausted"
    unknown = build_gate(settings, ["no_such_limit"])                          # 한도를 모르는 이름은 센 줄이 없다 — 통과
    unknown.acquire("no_such_limit")


# ── ⑦ 제공처가 「한도 초과」를 알렸을 때 ────────────────────────
def test_provider_exhaustion_blocks_until_korean_midnight_then_probes_again(meter):
    """제공처가 월 한도 초과를 알리면 그날 한국 자정까지 안 부르고, 그때까지 센 사용 수를 한도로 기록한다 — 다음 날 첫 호출이 한 번 시험한다."""
    noon = datetime(2026, 10, 5, 3, 0, 0, tzinfo=timezone.utc)                  # 한국 12:00
    tomorrow = datetime(2026, 10, 5, 15, 30, 0, tzinfo=timezone.utc)            # 한국 다음 날 00:30
    today = budget(meter, day=1000, month=10000, now=noon)
    for _ in range(7):
        assert today.try_reserve(meter) is True
    today.mark_provider_exhausted(meter, "month")
    assert today.try_reserve(meter) is False                                     # 오늘은 더 안 부른다
    assert budget(meter, day=1000, month=10000, now=noon).try_reserve(meter) is False         # 다른 프로세스도 같다
    month = rows_full(meter)["month:2026-10"]
    assert month["used"] == 7 and month["learned_cap"] == 7 and month["exhausted_at"] is not None     # 관측한 한도 = 7
    report = today.report([meter])[0]["month"]
    assert report["provider_exhausted"] is True and report["level"] == "exhausted" and report["learned_cap"] == 7
    later = budget(meter, day=1000, month=10000, now=tomorrow)
    assert later.try_reserve(meter) is True                                      # 다음 날 첫 호출이 한 번 시험한다(풀렸을 수 있다)
    later.mark_provider_exhausted(meter, "month")                                # 여전히 초과면 다시 표시 — 그날은 다시 멈춘다
    assert later.try_reserve(meter) is False


def test_next_month_is_a_new_row_so_the_block_lifts_by_itself(meter):
    last_day = datetime(2026, 10, 31, 3, 0, 0, tzinfo=timezone.utc)
    first_day = datetime(2026, 11, 1, 3, 0, 0, tzinfo=timezone.utc)
    october = budget(meter, day=1000, month=10000, now=last_day)
    october.try_reserve(meter)
    october.mark_provider_exhausted(meter, "month")
    assert october.try_reserve(meter) is False
    assert budget(meter, day=1000, month=10000, now=first_day).try_reserve(meter) is True      # 11월 줄은 새로 시작


def rows_full(name: str) -> dict[str, dict]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT period, used, cap, exhausted_at, learned_cap FROM external_call_budget WHERE meter=%s", (name,))
        return {r[0]: {"used": r[1], "cap": r[2], "exhausted_at": r[3], "learned_cap": r[4]} for r in cur.fetchall()}
