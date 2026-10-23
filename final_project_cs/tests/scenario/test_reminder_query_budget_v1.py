"""실제 로컬 DB의 발행 키로 반복 조회 예산을 확인한다. 외부 채널로는 보내지 않는다."""
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import TripStore
from .test_trip_reminders import world, _reminders, _notices, _at  # noqa: F401


class CountEvents:
    def __init__(self):
        self.calls = 0

    def affecting(self, targets):
        self.calls += 1
        return {}


def test_ten_ticks_one_notice_one_route_query(world):
    world['clock'].now = _at('10:50')
    events = CountEvents()
    reminders = _reminders(world, route_events=events)
    first = reminders.tick()
    assert len(first.sent) == 1
    for _ in range(9):
        again = reminders.tick()
        assert again.already == 1 and not again.sent
    assert events.calls == 1
    assert len(_notices(world)) == 1


def test_existing_message_check_is_scoped_to_tenant_trip_and_key(world):
    world['clock'].now = _at('10:50')
    [sent] = _reminders(world, route_events=CountEvents()).tick().sent
    with get_connection() as conn:
        assert world['store'].message_exists(conn, trip_id=world['trip_id'], key=sent['key'])
        assert not world['store'].message_exists(conn, trip_id=world['trip_id'], key='other-key')
        assert not TripStore(world['tenant'] + '_other').message_exists(
            conn, trip_id=world['trip_id'], key=sent['key'])


def test_failed_query_remains_retryable_until_notice_is_enqueued(world):
    class RetryEvents(CountEvents):
        def affecting(self, targets):
            self.calls += 1
            return None if self.calls == 1 else {}

    world['clock'].now = _at('10:50')
    events = RetryEvents()
    reminders = _reminders(world, route_events=events)
    failed = reminders.tick()
    assert failed.fatal and not failed.sent
    assert reminders.tick().sent
    assert reminders.tick().already == 1
    assert events.calls == 2 and len(_notices(world)) == 1
