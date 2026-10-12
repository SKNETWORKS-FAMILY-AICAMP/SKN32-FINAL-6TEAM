"""복구 실행 시작 경합에서 먼저 실행 중인 Case를 실패로 닫지 않는다."""
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.case_service import ActiveRunError
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, bind_services, current_bindings
from app.domains.travel_ops.components.watch import trip_watch_cases


class Connection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def transaction(self):
        return nullcontext()


def test_a_lost_run_start_race_does_not_close_the_winning_active_case(monkeypatch):
    monkeypatch.setattr(trip_watch_cases.PendingStore, "expire", lambda *a, **k: [])
    case_id = uuid4()

    def raced(**kwargs):
        assert current_bindings() is not None
        raise ActiveRunError("another round started first")

    watcher = trip_watch_cases.TripWatchCaseOpener(
        store=SimpleNamespace(tenant_id="watch-race-test", due=lambda *a, **k: []), check=None,
        connection_factory=Connection, clock=lambda: datetime.now(UTC), repository=None, run_case=raced)
    monkeypatch.setattr(watcher, "_open_issues", lambda issues, now, result, opened: opened.append(case_id))
    monkeypatch.setattr(watcher, "_close_failed", lambda *a: pytest.fail("the winning active Case was closed"))
    with bind_services(BindingTable({}, TeamRegistry(), "watch-race-test")):
        result = watcher.tick()
    assert result.existing == [{"case_id": str(case_id), "reason": "active_run"}]
    assert not result.failed and not result.ran
