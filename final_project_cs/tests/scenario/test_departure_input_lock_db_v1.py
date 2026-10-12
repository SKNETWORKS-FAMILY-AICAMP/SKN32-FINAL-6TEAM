"""조건 갱신과 출발 안내 저장이 같은 행 잠금에서 기다린 뒤 현재 입력을 읽는다."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from queue import Queue
from time import monotonic, sleep

import pytest

from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.itinerary.itinerary import StaleDeparture
from .test_trip_reminders import world, _notices  # noqa: F401


@pytest.mark.parametrize('first', ['update', 'publish'])
def test_input_update_and_notice_wait_then_follow_committed_order(world, first):
    with get_connection() as conn:
        trip, items = world['store'].latest(conn, world['trip_id'])
    move = next(i for i in items if i.seq == 3)
    snapshot = deepcopy({'party_size':trip['party_size'], 'constraints':trip['constraints']})
    changed = {**trip['constraints'], 'mobility_ease':'needs_rest'}
    started = Queue()

    def operation(conn, kind):
        if kind == 'update':
            with conn.cursor() as cur:
                cur.execute('UPDATE trips SET constraints=%s::jsonb WHERE tenant_id=%s AND trip_id=%s',
                            (json.dumps(changed), world['tenant'], world['trip_id']))
            return True
        return world['store'].enqueue_message(conn, trip_id=world['trip_id'],
            key=f'departure:{move.item_id}', payload={'version':trip['version'],'text':'출발 안내'},
            expected_departure_inputs=snapshot)

    def second():
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='8s'")
            cur.execute('SELECT pg_backend_pid()')
            started.put(cur.fetchone()[0])
            return operation(conn, 'publish' if first == 'update' else 'update')

    with ThreadPoolExecutor(max_workers=1) as pool:
        with get_connection() as conn, conn.transaction():
            operation(conn, first)
            future = pool.submit(second)
            pid = started.get(timeout=5)
            deadline = monotonic()+5
            waited = False
            with get_connection() as monitor:
                monitor.autocommit = True
                while monotonic() < deadline:
                    with monitor.cursor() as cur:
                        cur.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',(pid,))
                        row = cur.fetchone()
                    if row and row[0] == 'Lock':
                        waited = True
                        break
                    if future.done():
                        break
                    sleep(.02)
            assert waited and not future.done()
        if first == 'update':
            with pytest.raises(StaleDeparture, match='departure trip inputs changed'):
                future.result(timeout=5)
        else:
            assert future.result(timeout=5)
    with get_connection() as conn:
        current, _ = world['store'].latest(conn, world['trip_id'])
    assert current['version'] == 1 and current['constraints'] == changed
    assert len(_notices(world)) == (0 if first == 'update' else 1)


def test_other_notice_kinds_keep_existing_contract(world):
    with get_connection() as conn, conn.transaction():
        assert world['store'].enqueue_message(conn, trip_id=world['trip_id'], key='day_start:test',
            payload={'text':'하루 안내'},
            expected_departure_inputs={'party_size':None,'constraints':{'not_current':True}})
    assert len(_notices(world)) == 1
