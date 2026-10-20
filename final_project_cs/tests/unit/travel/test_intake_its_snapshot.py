"""같은 접수 점검 안의 ITS 실패만 재사용하고 새 요청의 회복은 막지 않는다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo
import time

import httpx

from app.domains.travel_ops.components.intake import risks
from app.domains.travel_ops.ports.data_sources import base
from app.domains.travel_ops.ports.data_sources.cache import ResponseCache
from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck
from app.domains.travel_ops.ports.data_sources.its_traffic import ItsTrafficEvents
from app.domains.travel_ops.ports.data_sources.ratelimit import CacheOnlyLimiter
from app.domains.travel_ops.ports.data_sources.traffic_chain import CombinedTraffic

NOW = datetime(2030, 1, 1, 14, tzinfo=ZoneInfo("Asia/Seoul"))


class Budget:
    def __init__(self):
        self.reserved = self.failed = 0

    def reserve(self, key):
        self.reserved += 1
        return "allowed"

    def record_failure(self, key):
        self.failed += 1


class Transport:
    def __init__(self, *, fails=True, rendezvous=None):
        self.fails, self.rendezvous = fails, rendezvous
        self.calls = []
        self.lock = Lock()

    def __call__(self, url, params):
        with self.lock:
            self.calls.append({key: value for key, value in params.items() if key != "apiKey"})
        if self.rendezvous:
            self.rendezvous.wait(timeout=2)
        time.sleep(.01)
        if self.fails:
            raise httpx.ReadTimeout("mock timeout")
        return httpx.Response(200, json={"header": {"resultCode": 0}, "body": {"items": []}})


def source(*, transport=None, cache=None, enabled=True, **extra):
    transport, budget = transport or Transport(), Budget()
    return ItsTrafficEvents(service_key="unit-only", transport=transport, key_budget=budget,
                            cache=cache, operation_snapshot=enabled, now=lambda: NOW, **extra), transport, budget


def near(adapter, *, latitude=37.5, longitude=127.0):
    return adapter.near(latitude=latitude, longitude=longitude, at=NOW)


def test_same_query_failure_costs_one_attempt_and_never_becomes_clear():
    adapter, transport, budget = source(cache=ResponseCache(ttl_seconds=300))
    assert near(adapter) is None
    assert near(adapter, latitude=37.51) is None
    assert near(adapter) is None
    assert len(transport.calls) == budget.reserved == budget.failed == 1
    assert adapter.misses["operation_failure_reused"] == 2


def test_default_adapter_does_not_change_its_existing_retry_boundary():
    adapter, transport, budget = source(enabled=False)
    assert near(adapter) is None and near(adapter) is None
    assert len(transport.calls) == budget.reserved == 2


def test_failure_is_not_shared_and_a_new_request_can_recover():
    cache = ResponseCache(ttl_seconds=300)
    first, failing, _ = source(cache=cache)
    assert near(first) is None
    next_request, recovered, budget = source(cache=cache, transport=Transport(fails=False))
    assert near(next_request) is not None
    assert len(recovered.calls) == budget.reserved == 1
    # 새 요청이 공유 캐시에 채운 성공 자료는 기존 점검기에서도 읽을 수 있다.
    assert near(first) is not None
    assert len(failing.calls) == 1


def test_concurrent_same_query_failures_reserve_exactly_once():
    adapter, transport, budget = source()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(lambda _: near(adapter), range(8))) == [None] * 8
    assert len(transport.calls) == budget.reserved == budget.failed == 1
    assert adapter.misses["operation_failure_reused"] == 7


def test_different_query_boxes_have_independent_locks_and_failure_state():
    adapter, transport, budget = source(transport=Transport(rendezvous=Barrier(2)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda latitude: near(adapter, latitude=latitude), [37.5, 38.5]))
    assert results == [None, None]
    assert len(transport.calls) == budget.reserved == 2
    assert transport.calls[0] != transport.calls[1]
    assert near(adapter, latitude=38.5) is None
    assert len(transport.calls) == 2


def test_cache_only_never_calls_transport_or_key_budget_even_after_reuse():
    adapter, transport, budget = source(limiter=CacheOnlyLimiter())
    assert near(adapter) is None and near(adapter) is None
    assert transport.calls == [] and budget.reserved == budget.failed == 0


def test_intake_keeps_utic_facts_and_partial_coverage_after_one_its_timeout():
    adapter, transport, budget = source()

    class UTIC:
        name = "utic"

        def near(self, **kwargs):
            return {"for_place": [{"reason": "전체 차로 통제", "message": "합성 도로 양방향 통제", "road": "합성 도로"}],
                    "source": "utic", "confirmed_at": NOW.isoformat()}

    check = DisruptionCheck(SimpleNamespace(traffic=CombinedTraffic([adapter, UTIC()])), limits=lambda: (None, None))
    methods = {name: (lambda *args, category=category: {"category": category, "status": "ok", "source": "unit"})
               for name, category in [("_forecast", "forecast"), ("_warning", "weather_warning"), ("_disaster", "disaster_msg"),
                                      ("_air", "air_quality"), ("_earthquake", "earthquake")]}
    rows = [{"id": str(uuid4()), "kind": "activity", "title": "합성 일정", "date": "2030-01-01", "starts_at": "13:00", "ends_at": "16:00",
             "place": {"name": "합성 장소", "latitude": 37.5, "longitude": 127.0, "weather_sensitive": True}} for _ in range(3)]
    with patch.multiple(check, **methods):
        result = risks.decorate(None, tenant_id="unit", review={"items": rows}, mode="fresh", check=check.check, now=NOW)
    assert len(transport.calls) == budget.reserved == budget.failed == 1
    for item in result["items"]:
        assert item["risk"]["status"] == "problem"
        assert item["risk"]["problems"][0]["message"] == "합성 도로 양방향 통제"
        assert item["risk"]["unknown_categories"][0]["code"] == "partial"


def test_only_intake_source_factory_enables_the_operation_snapshot(monkeypatch):
    settings = SimpleNamespace()
    seen = []
    monkeypatch.setattr("app.core.settings.get_settings", lambda: settings)
    monkeypatch.setattr(base, "build_travel_sources", lambda actual, **kw: seen.append((actual, kw)) or SimpleNamespace())
    for mode in ["fresh", "cached"]:
        assert callable(risks.check_for(mode))
    assert seen == [(settings, {"cache_only": False, "operation_snapshot": True}),
                    (settings, {"cache_only": True, "operation_snapshot": True})]


def test_snapshot_keeps_provider_quota_rotation_and_charges_each_actual_attempt():
    class KeyBudget(Budget):
        def __init__(self):
            super().__init__()
            self.blocked = set()

        def reserve(self, key):
            return "key_exhausted" if key in self.blocked else super().reserve(key)

        def mark_exhausted(self, key, scope):
            assert scope == "month"
            self.blocked.add(key)

    budget, sent = KeyBudget(), []

    def transport(url, params):
        key = params["apiKey"]
        sent.append(key)
        if key == "unit-primary":
            return httpx.Response(401, json={"header": {"resultCode": 4001}})
        raise httpx.ReadTimeout("mock spare timeout")

    adapter = ItsTrafficEvents(service_key="unit-primary", service_keys='["unit-spare"]',
                               key_budget=budget, transport=transport, operation_snapshot=True)
    assert near(adapter) is None and near(adapter) is None
    assert sent == ["unit-primary", "unit-spare"]
    assert budget.reserved == budget.failed == 2
    assert budget.blocked == {"unit-primary"}
