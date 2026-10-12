"""출발 문구 계산과 저장 사이 변경, 출발 발행과 적용 사이 순서를 로컬 DB에서 제어한다."""
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from time import monotonic, sleep

import pytest

from app.infrastructure.db.session import get_connection
from app.core.actions import ActionConflict
from app.domains.travel_ops.components.actions.itinerary_actions import ItineraryApply, change_arguments
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange
from app.domains.travel_ops.components.itinerary.itinerary import StaleDeparture
from .test_trip_reminders import world, _at, _NoEvents, _reminders, _notices  # noqa: F401


def _proposal(world, batch=False):
    with get_connection() as conn:
        trip, items = world['store'].latest(conn, world['trip_id'])
    move = next(i for i in items if i.seq == 3)
    new = move.replaced_by(place=None, title=move.title+' · 재계산')
    causes = [{'category': 'departure_revalidation', 'kind': 'current_route_replan'}]
    change = ItineraryChange(reason='route_event', causes=causes, notice={'text': '새 이동'},
        replacements={move.item_id: new})
    arguments = change_arguments(trip_id=world['trip_id'], base_version=trip['version'], change=change)
    if batch:
        arguments['batch'] = {'causes': {str(move.item_id): causes}, 'retry': []}
        arguments['causes'] = []  # 묶음에서는 항목별 원인이 판정 기준이다.
    return trip, items, move, arguments


@pytest.mark.parametrize('replace_move', [False, True])
def test_reminder_discards_payload_when_version_changes_after_calculation(world, monkeypatch, replace_move):
    world['clock'].now = _at('10:50')
    reminders = _reminders(world, route_events=_NoEvents())
    original = reminders._payload

    def calculate_then_change(*args, **kwargs):
        payload = original(*args, **kwargs)
        with get_connection() as conn, conn.transaction():
            trip, items = world['store'].latest(conn, world['trip_id'])
            if replace_move:
                items = [i.replaced_by(place=None, title=i.title+' · 변경') if i.seq == 3 else i for i in items]
            world['store'].append_version(conn, trip_id=world['trip_id'], base_version=trip['version'],
                items=items, reason='controlled interleaving', causes=[])
        return payload

    monkeypatch.setattr(reminders, '_payload', calculate_then_change)
    result = reminders.tick()
    assert not result.sent, result
    assert len(result.stale) == 1 and result.already == 0
    assert _notices(world) == []
    # 다음 반복은 최신 판의 경로만 안내한다.
    latest = _reminders(world, route_events=_NoEvents()).tick()
    assert len(latest.sent) == 1
    assert _notices(world)[0][1]['version'] == 2


@pytest.mark.parametrize('batch', [False, True])
def test_departure_published_after_proposal_blocks_replan_at_apply(world, batch):
    trip, _, move, arguments = _proposal(world, batch)
    with get_connection() as conn, conn.transaction():
        world['store'].enqueue_message(conn, trip_id=world['trip_id'], key=f'departure:{move.item_id}',
            payload={'version': trip['version'], 'text': '발행된 출발 안내'})
    with pytest.raises(ActionConflict, match='departure already announced'):
        with get_connection() as conn, conn.transaction():
            ItineraryApply().apply(conn, tenant_id=world['tenant'], customer_id=trip['customer_id'],
                case_id=None, arguments=arguments)
    with get_connection() as conn:
        latest, _ = world['store'].latest(conn, world['trip_id'])
    assert latest['version'] == trip['version']
    assert len(_notices(world)) == 1


def test_departure_for_missing_current_item_is_not_inserted(world):
    with get_connection() as conn, conn.transaction():
        with pytest.raises(RuntimeError, match='departure item is no longer current'):
            world['store'].enqueue_message(conn, trip_id=world['trip_id'], key=f'departure:{uuid4()}',
                payload={'text': '현재 판에 없는 항목'})
    assert _notices(world) == []


@pytest.mark.parametrize('first', ['publish', 'replan'])
def test_concurrent_transactions_wait_then_recheck_committed_winner(world, first):
    trip, _, move, arguments = _proposal(world)
    started = Queue()

    def operation(conn, kind):
        if kind == 'publish':
            return world['store'].enqueue_message(conn, trip_id=world['trip_id'],
                key=f'departure:{move.item_id}', payload={'version': trip['version'], 'text': '출발 안내'})
        return ItineraryApply().apply(conn, tenant_id=world['tenant'], customer_id=trip['customer_id'],
            case_id=None, arguments=arguments)

    def second():
        with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='8s'")  # 시험이 교착하면 유한 시간 안에 실패한다.
            cur.execute('SELECT pg_backend_pid()')
            started.put(cur.fetchone()[0])
            return operation(conn, 'replan' if first == 'publish' else 'publish')

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
                        cur.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s', (pid,))
                        row = cur.fetchone()
                    if row and row[0] == 'Lock':
                        waited = True
                        break
                    if future.done():
                        break
                    sleep(.02)
            assert waited and not future.done(), '두 번째 연결이 같은 여행의 잠금에서 대기해야 한다'
        expected = ActionConflict if first == 'publish' else StaleDeparture
        with pytest.raises(expected):
            future.result(timeout=5)
    with get_connection() as conn:
        current, _ = world['store'].latest(conn, world['trip_id'])
    assert current['version'] == (1 if first == 'publish' else 2)
    assert len(_notices(world)) == (1 if first == 'publish' else 0)
