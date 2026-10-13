"""사건 소스 없는 직접 도보도 DB 저장 일정의 현재 모델로 안내한다."""
import pytest

from . import test_departure_walk_db_v1 as stored_walk
from .test_trip_reminders import world  # noqa: F401


@pytest.mark.parametrize('no_path', [False, True])
def test_stored_walk_revalidates_or_holds_without_unrelated_incident_source(world, monkeypatch, no_path):
    build = stored_walk._reminders

    def without_incidents(*args, **kwargs):
        reminders = build(*args, **kwargs)
        reminders.route_events = None
        return reminders

    monkeypatch.setattr(stored_walk, '_reminders', without_incidents)
    stored_walk.test_stored_walk_is_revalidated_once_or_held_on_disconnection(world, monkeypatch, no_path)
