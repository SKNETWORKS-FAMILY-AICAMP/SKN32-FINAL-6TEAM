"""ITS 예비 키는 확인된 소진에만 전환하며 전체 한도를 우회하지 않는다."""
from __future__ import annotations

import logging
from collections import Counter

import httpx
import pytest

from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.its_key_budget import key_meter
from app.domains.travel_ops.ports.data_sources.its_traffic import ItsTrafficEvents, service_key_ring
from app.domains.travel_ops.ports.data_sources.ratelimit import CacheOnlyLimiter


class CountingBudget:
    def __init__(self, *, total_limit=1000, key_limit=1000, blocked=(), fail=False):
        self.total_limit, self.key_limit, self.fail = total_limit, key_limit, fail
        self.used = 0
        self.per_key = Counter()
        self.blocked = set(blocked)
        self.marked = []
        self.failures = []

    def reserve(self, key):
        if self.fail:
            raise RuntimeError("private database connection details")
        if key in self.blocked or self.per_key[key] >= self.key_limit:
            return "key_exhausted"
        if self.used >= self.total_limit:
            return "total_exhausted"
        self.used += 1
        self.per_key[key] += 1
        return "allowed"

    def mark_exhausted(self, key, scope):
        self.blocked.add(key)
        self.marked.append((key, scope))

    def record_failure(self, key):
        self.failures.append(key)


def response(status=200, code=0):
    return httpx.Response(status, json={"header": {"resultCode": code}, "body": {"items": []}})


def source(budget, transport, **kwargs):
    return ItsTrafficEvents(service_key="test-primary", service_keys='["test-primary","test-spare"]',
                            key_budget=budget, transport=transport, **kwargs)


def test_known_exhausted_primary_is_skipped_without_a_confirmation_request():
    budget = CountingBudget(blocked={"test-primary"})
    sent = []
    reader = source(budget, lambda url, params: sent.append(params["apiKey"]) or response())
    assert reader.records() == []
    assert sent == ["test-spare"] and budget.used == 1 and budget.per_key["test-primary"] == 0


@pytest.mark.parametrize("status", [200, 401])
def test_quota_response_and_spare_request_are_each_reserved_and_counted(status):
    budget = CountingBudget()
    sent = []

    def transport(url, params):
        sent.append(params["apiKey"])
        return response(status, 4001) if params["apiKey"] == "test-primary" else response()

    reader = source(budget, transport)
    assert reader.records() == []
    assert sent == ["test-primary", "test-spare"] and budget.used == 2
    assert budget.marked == [("test-primary", "month")] and budget.failures == ["test-primary"]
    reader.records()
    assert sent == ["test-primary", "test-spare", "test-spare"]


def test_spare_cannot_bypass_the_total_cap_after_a_quota_response():
    budget = CountingBudget(total_limit=1)
    sent = []
    reader = source(budget, lambda url, params: sent.append(params["apiKey"]) or response(401, 4001))
    assert reader.records() is None
    assert sent == ["test-primary"] and budget.used == 1
    assert reader.misses["budget_exhausted"] == 1


def test_a_key_daily_cap_switches_to_spare_and_keeps_the_total_counter():
    budget = CountingBudget(key_limit=1, total_limit=2)
    sent = []
    reader = source(budget, lambda url, params: sent.append(params["apiKey"]) or response())
    assert reader.records() == [] and reader.records() == [] and reader.records() is None
    assert sent == ["test-primary", "test-spare"] and budget.used == 2


def test_database_errors_refuse_without_any_request_or_secret_log(caplog):
    sent = []
    reader = source(CountingBudget(fail=True), lambda *args: sent.append(args) or response())
    with caplog.at_level(logging.WARNING):
        assert reader.records() is None
    assert sent == [] and reader.misses["budget_unavailable"] == 1
    assert "private database" not in caplog.text and "test-primary" not in caplog.text


def test_timeout_is_charged_once_and_never_retried_with_spare(caplog):
    budget = CountingBudget()
    sent = []

    def timeout(url, params):
        sent.append(params["apiKey"])
        raise httpx.ReadTimeout("https://example.test?apiKey=test-primary")

    reader = source(budget, timeout)
    with caplog.at_level(logging.WARNING):
        assert reader.records() is None
    assert sent == ["test-primary"] and budget.used == 1 and budget.failures == ["test-primary"]
    assert "apiKey" not in caplog.text and "test-primary" not in caplog.text


@pytest.mark.parametrize("status,code", [(401, 4005), (500, 4001), (200, 4005)])
def test_authentication_and_transport_errors_do_not_retry_other_keys(status, code):
    budget = CountingBudget()
    sent = []
    reader = source(budget, lambda url, params: sent.append(params["apiKey"]) or response(status, code))
    assert reader.records() is None
    assert sent == ["test-primary"] and budget.used == 1 and budget.marked == []


def test_successful_public_cache_is_shared_between_keys_without_another_reservation():
    cache = ResponseCache(ttl_seconds=60)
    budget = CountingBudget()
    sent = []
    reader = source(budget, lambda url, params: sent.append(params["apiKey"]) or response(), cache=cache)
    assert reader.records() == []
    second = ItsTrafficEvents(service_key="test-spare", key_budget=budget, cache=cache,
                              transport=lambda *args: pytest.fail("cache hit must not call ITS"))
    assert second.records() == [] and budget.used == 1 and sent == ["test-primary"]


def test_cache_only_miss_never_reserves_a_budget_slot():
    budget = CountingBudget()
    reader = source(budget, lambda *args: pytest.fail("cache-only request"), limiter=CacheOnlyLimiter())
    assert reader.records() is None and budget.used == 0


def test_key_ring_keeps_order_deduplicates_and_uses_stable_nonsecret_identity():
    assert service_key_ring(" a ", '["a","b"," b "]') == ("a", "b")
    assert service_key_ring("", "b,a,b") == ("b", "a")
    meter = key_meter("test-primary")
    assert meter.startswith("its:key:") and "test-primary" not in meter
    assert meter == key_meter("test-primary") and meter != key_meter("test-spare")


@pytest.mark.parametrize("raw", ['["private-test", 7]', '["private-test"'])
def test_bad_key_config_raises_without_echoing_its_contents(raw):
    with pytest.raises(ValueError) as caught:
        service_key_ring("", raw)
    assert "private-test" not in str(caught.value)
