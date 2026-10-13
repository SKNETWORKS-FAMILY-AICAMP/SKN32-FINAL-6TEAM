"""JSON의 논리값과 숫자를 같은 조건으로 처리하지 않는다."""
from copy import deepcopy
import json

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import StaleDeparture
from .test_trip_reminders import world, _notices  # noqa: F401


def test_boolean_changed_to_number_is_not_the_same_input(world):
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        trip, items = world['store'].latest(conn, world['trip_id'])
        move = next(i for i in items if i.seq == 3)
        before = {**trip['constraints'], 'first_visit':True}
        snapshot = {'party_size':trip['party_size'],'constraints':deepcopy(before)}
        current = {**before,'first_visit':1}
        cur.execute('UPDATE trips SET constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s',
                    (json.dumps(current),world['tenant'],world['trip_id']))
        with pytest.raises(StaleDeparture,match='departure trip inputs changed'):
            world['store'].enqueue_message(conn, trip_id=world['trip_id'],
                key=f'departure:{move.item_id}',payload={'version':trip['version'],'text':'옛 조건 안내'},
                expected_departure_inputs=snapshot)
    assert _notices(world) == []
