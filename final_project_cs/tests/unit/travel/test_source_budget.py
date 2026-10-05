# -*- coding: utf-8 -*-
"""소스별 호출 예산(`source_budget.BudgetedLimiter`) 단위 시험 — DB 없이 가짜 예산으로. `[2026-10-05 사용자 지시 — 한도에 도달하면 API 가 안 돌게]`

지키려는 것
 ①안쪽 제한기를 **먼저** 통과하고, 안쪽이 거절하면 DB 예산을 쓰지 않는다 · 목록 밖 소스는 DB 를 안 부른다
 ②예산이 차면 `BudgetExhausted`(`RateLimited` 의 갈래 · 이유 `budget_exhausted` · 다음 하루 줄까지 초)
 ③DB 오류: `allow`(기본) 면 안쪽 제한기만으로 통과 · `refuse` 면 `BudgetUnavailable` — 어느 쪽이든 오류를 세고, 같은 시간 안에는 DB 를 다시 부르지 않고 지난 뒤엔 다시 시도한다
 ④여유 단계: 80% 경보 · 95% 위험 로그는 (소스, 단계)마다 한 번 · `essential_only` 는 위험 · 찼음에서 True
 ⑤`TravelSource` 와 이어졌을 때: 예산이 차면 호출하지 않고 미스 이유가 `budget_exhausted` · 부른 뒤의 실패만 DB 실패 수로 센다(한도 때문에 안 부른 것은 안 센다)

재현:

    python -m pytest tests/unit/travel/test_source_budget.py -v
"""
from __future__ import annotations

import logging

import httpx
import pytest

from app.infrastructure.travel.base import TravelSource
from app.infrastructure.travel.call_budget import level_of, UNLIMITED
from app.infrastructure.travel.ratelimit import RateLimited
from app.infrastructure.travel.source_budget import (BudgetExhausted, BudgetUnavailable, BudgetedLimiter, RETRY_AFTER_SECONDS)


class FakeInner:
    """안쪽 제한기 — 부른 순서를 기록하고, 이름을 주면 그 소스를 거절한다."""

    def __init__(self, refuse: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.refuse = refuse or set()
        self.refusals = {"x": 7}                     # `__getattr__` 로 넘겨지는 속성 확인용

    def acquire(self, source: str) -> None:
        self.calls.append(source)
        if source in self.refuse:
            raise RateLimited(source, 3.0)


class FakeBudget:
    """DB 예산 흉내 — `grants` 가 남은 허락 수, `fail` 이 True 면 DB 오류, `last` 로 확보 직후 줄 값을 준다."""

    def __init__(self, grants: int = 10, fail: bool = False) -> None:
        self.grants, self.fail = grants, fail
        self.reserved: list[str] = []
        self.failures: list[str] = []
        self.last: dict[str, dict[str, tuple[int, int]]] = {}

    def try_reserve(self, meter: str) -> bool:
        self.reserved.append(meter)
        if self.fail:
            raise ConnectionError("db down")
        if self.grants <= 0:
            return False
        self.grants -= 1
        return True

    def seconds_to_day_end(self) -> float:
        return 7200.0

    def record_failure(self, meter: str) -> None:
        self.failures.append(meter)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(budget=None, inner=None, meters=("its",), policy="allow", clock=None):
    inner = inner or FakeInner()
    budget = budget or FakeBudget()
    return BudgetedLimiter(inner, budget, set(meters), on_db_error=policy, clock=clock or Clock()), inner, budget


# ── ① 안쪽 먼저 · 목록 밖은 DB 안 부름 ──────────────────────────
def test_inner_limiter_runs_first_and_a_granted_call_goes_out():
    limiter, inner, budget = make()
    limiter.acquire("its")
    assert inner.calls == ["its"] and budget.reserved == ["its"]


def test_a_refusal_from_the_inner_limiter_never_touches_the_database_budget():
    limiter, _inner, budget = make(inner=FakeInner(refuse={"its"}))
    with pytest.raises(RateLimited) as caught:
        limiter.acquire("its")
    assert type(caught.value) is RateLimited and caught.value.reason == "rate_limited"
    assert budget.reserved == []                       # 안 부를 호출이 한 칸을 쓰지 않는다


def test_sources_outside_the_list_do_not_use_the_database():
    limiter, inner, budget = make(meters=("its",))
    limiter.acquire("open_meteo")
    assert inner.calls == ["open_meteo"] and budget.reserved == []
    assert limiter.refusals == {"x": 7}                # 안쪽 제한기의 나머지 속성은 그대로 보인다


# ── ② 예산이 참 ─────────────────────────────────────────────────
def test_when_the_budget_is_full_the_call_is_refused_with_a_distinct_reason():
    limiter, _inner, budget = make(budget=FakeBudget(grants=1))
    limiter.acquire("its")
    with pytest.raises(BudgetExhausted) as caught:
        limiter.acquire("its")
    error = caught.value
    assert isinstance(error, RateLimited) and error.reason == "budget_exhausted"     # 어댑터가 같은 자리에서 잡는다
    assert error.source == "its" and error.wait_seconds == 7200.0
    assert limiter.exhausted == {"its": 1} and limiter.essential_only("its") is True


# ── ③ DB 오류 ───────────────────────────────────────────────────
def test_allow_policy_lets_the_call_through_on_a_db_error_and_stops_asking_for_a_while(caplog):
    clock = Clock()
    limiter, _inner, budget = make(budget=FakeBudget(fail=True), policy="allow", clock=clock)
    with caplog.at_level(logging.WARNING):
        limiter.acquire("its")                                           # 오류 → 통과
        limiter.acquire("its")                                           # 오류 직후 → DB 안 부르고 통과
    assert budget.reserved == ["its"] and limiter.db_errors == 1
    assert any("안쪽 제한기만 적용(allow)" in record.getMessage() for record in caplog.records)
    clock.now += RETRY_AFTER_SECONDS["allow"] + 1
    limiter.acquire("its")                                               # 시간이 지나면 다시 시도한다
    assert budget.reserved == ["its", "its"] and limiter.db_errors == 2


def test_refuse_policy_stops_the_call_on_a_db_error_and_for_a_short_while_after():
    clock = Clock()
    limiter, _inner, budget = make(budget=FakeBudget(fail=True), policy="refuse", clock=clock)
    with pytest.raises(BudgetUnavailable) as first:
        limiter.acquire("its")
    assert first.value.reason == "budget_unavailable" and isinstance(first.value, RateLimited)
    with pytest.raises(BudgetUnavailable):
        limiter.acquire("its")                                           # 오류 직후 — DB 를 다시 부르지 않고 같은 규칙
    assert budget.reserved == ["its"] and limiter.db_errors == 1
    budget.fail, budget.grants = False, 5
    clock.now += RETRY_AFTER_SECONDS["refuse"] + 1
    limiter.acquire("its")                                               # DB 가 살아나고 시간이 지나면 풀린다
    assert budget.reserved == ["its", "its"]


def test_an_unknown_policy_is_refused_at_construction():
    with pytest.raises(ValueError):
        BudgetedLimiter(FakeInner(), FakeBudget(), {"its"}, on_db_error="maybe")


# ── ④ 여유 단계 ─────────────────────────────────────────────────
@pytest.mark.parametrize("used,cap,level", [(0, 100, "ok"), (79, 100, "ok"), (80, 100, "warn"), (94, 100, "warn"), (95, 100, "critical"),
                                            (99, 100, "critical"), (100, 100, "exhausted"), (5, UNLIMITED, "ok"), (0, 0, "exhausted")])
def test_level_thresholds(used, cap, level):
    assert level_of(used, cap)[1] == level


def test_warning_is_logged_once_per_source_and_level_and_essential_only_follows(caplog):
    budget = FakeBudget()
    limiter, _inner, _ = make(budget=budget)
    with caplog.at_level(logging.WARNING):
        budget.last["its"] = {"day": (80, 100), "month": (10, UNLIMITED)}
        limiter.acquire("its")
        limiter.acquire("its")                                           # 같은 단계 — 다시 안 적는다
        assert limiter.levels["its"] == "warn" and limiter.essential_only("its") is False
        budget.last["its"] = {"day": (96, 100), "month": (10, UNLIMITED)}
        limiter.acquire("its")
    warnings = [record.getMessage() for record in caplog.records if "source budget its" in record.getMessage()]
    assert len(warnings) == 2 and "warn" in warnings[0] and "critical" in warnings[1]
    assert limiter.essential_only("its") is True


def test_the_worse_of_day_and_month_decides_the_level():
    budget = FakeBudget()
    limiter, _inner, _ = make(budget=budget)
    budget.last["its"] = {"day": (10, 1000), "month": (96, 100)}
    limiter.acquire("its")
    assert limiter.levels["its"] == "critical"


# ── ⑤ TravelSource 와 이어졌을 때 ──────────────────────────────
class Probe(TravelSource):
    name = "its"


def probe(status: int, budget: FakeBudget, **kwargs):
    limiter, _inner, _ = make(budget=budget)
    return Probe(transport=lambda url, params: httpx.Response(status, text="boom"), limiter=limiter, **kwargs)


def test_a_full_budget_means_no_outbound_call_and_the_miss_says_why():
    sent: list[str] = []
    limiter, _inner, budget = make(budget=FakeBudget(grants=0))
    source = Probe(transport=lambda url, params: sent.append(url) or httpx.Response(200, json={}), limiter=limiter)
    assert source._fetch_json("http://example.test", {}) is None
    assert sent == [] and source.misses["budget_exhausted"] == 1 and source.last_wait_seconds == 7200.0
    assert budget.failures == []                                         # 한도 때문에 안 부른 것은 실패 수로 안 센다(거절 수로 센다)


def test_a_call_that_went_out_and_failed_is_counted_as_a_failure():
    budget = FakeBudget()
    source = probe(500, budget)
    assert source._fetch_json("http://example.test", {}) is None
    assert source.misses["http_500"] == 1 and budget.failures == ["its"]


def test_a_source_without_a_limiter_still_works_and_counts_nothing():
    source = Probe(transport=lambda url, params: httpx.Response(500, text="boom"))
    assert source._fetch_json("http://example.test", {}) is None          # 한도 층이 없어도 터지지 않는다
    assert source.misses["http_500"] == 1


# ── ⑥ 제공처가 「한도 초과」를 알렸을 때 ────────────────────────
from app.infrastructure.travel.its_traffic import ItsTrafficEvents  # noqa: E402


class FakeBudgetWithMarks(FakeBudget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.marks: list[tuple[str, str]] = []

    def mark_provider_exhausted(self, meter: str, scope: str = "day") -> None:
        self.marks.append((meter, scope))


def _its(status: int, body: str, budget: FakeBudgetWithMarks):
    limiter, _inner, _ = make(budget=budget)
    return ItsTrafficEvents(service_key="k", limiter=limiter,
                            transport=lambda url, params: httpx.Response(status, content=body.encode("utf-8")))


def test_its_quota_signal_marks_the_month_row_and_stops_further_calls():
    """ITS 는 월 한도가 차면 HTTP 401 + resultCode 4001 로 답한다 — 숫자 코드로 알아보고 월 줄을 멈춘다."""
    budget = FakeBudgetWithMarks()
    source = _its(401, '{"header":{"resultCode":4001,"resultMsg":"월간 API 호출 한도를 초과하였습니다."},"body":""}', budget)
    assert source.records() is None
    assert budget.marks == [("its", "month")]                           # 월 줄에 표시 — 이 소스를 오늘 더 부르지 않게
    assert source.misses["http_401"] == 1


def test_a_plain_401_or_other_codes_do_not_mark_the_budget():
    budget = FakeBudgetWithMarks()
    assert _its(401, '{"header":{"resultCode":4002,"resultMsg":"키가 틀림"}}', budget).records() is None
    assert _its(401, "unauthorized", budget).records() is None
    assert _its(500, '{"header":{"resultCode":4001}}', budget).records() is None                        # 401 이 아니면 신호로 안 본다
    assert budget.marks == []


def test_a_source_without_the_budget_layer_ignores_the_signal_safely():
    source = ItsTrafficEvents(service_key="k", transport=lambda url, params: httpx.Response(401, text='{"header":{"resultCode":4001}}'))
    assert source.records() is None                                                                        # 한도 층이 없어도 터지지 않는다
