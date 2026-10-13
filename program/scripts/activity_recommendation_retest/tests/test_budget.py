"""Actual subprocess/SQLite tests, without model clients or credentials."""
from decimal import Decimal
import multiprocessing as mp
import os
from pathlib import Path
import sqlite3
import sys
import uuid

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from budget import Budget, BudgetExceeded, BudgetLocked, FinishConflict, RunLocked, run_lock


BASELINE = 0.349834632


def _race_reserve(path, cap, max_calls, count, gate, connection):
    budget = Budget(path, cap, max_calls, BASELINE)
    gate.wait(20)
    accepted = []
    for _ in range(count):
        try:
            accepted.append(budget.reserve('test', 0.01))
        except BudgetExceeded:
            pass
    connection.send(accepted)
    connection.close()


def _race_finish(path, call_id, gate, connection):
    budget = Budget(path, 0.5, 600, BASELINE)
    gate.wait(20)
    connection.send(budget.finish(call_id, 0.005, True))
    connection.close()


def _reserve_then_exit(path, connection):
    budget = Budget(path, 0.5, 600, BASELINE)
    connection.send(budget.reserve('crash', 0.04))
    connection.close()
    os._exit(23)


def _hold_lock(path, gate, connection, crash):
    with run_lock(path):
        connection.send('locked')
        connection.close()
        gate.wait(20)
        if crash:
            os._exit(24)


def _uncommitted_exit(path, connection):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute('BEGIN IMMEDIATE')
    db.execute("INSERT INTO calls (call_id,lane,upper_usd,metadata,reserved_at) VALUES ('uncommitted','crash','0.49','{}','test')")
    connection.send('inserted')
    connection.close()
    os._exit(25)


def _join(process, expected=0):
    process.join(30)
    if process.is_alive():
        process.terminate()
        process.join(10)
        pytest.fail('subprocess exceeded deadline')
    assert process.exitcode == expected


def _receive(connection):
    assert connection.poll(30), 'subprocess result not received'
    result = connection.recv()
    connection.close()
    return result


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / 'budget.sqlite3'


def test_snapshot_and_uuid(ledger):
    budget = Budget(ledger, 0.5, 600, BASELINE)
    call_id = budget.reserve('nano', 0.02, {'case_id': 'dev_1', 'nested': {'count': 1}})
    assert uuid.UUID(call_id).version == 4
    snap = budget.snapshot()
    assert snap == {'reserved_calls': 1, 'finished_calls': 0, 'known_usd': 0.0,
                    'unknown_reserved_usd': 0.02, 'committed_usd': 0.02,
                    'cap_usd': 0.5, 'baseline_usd': BASELINE,
                    'cumulative_usd': 0.369834632, 'max_calls': 600, 'locked': False}
    assert budget.finish(call_id, 0.004, True) == 0.004
    snap = budget.snapshot()
    assert snap['finished_calls'] == 1
    assert snap['known_usd'] == 0.004
    assert snap['unknown_reserved_usd'] == 0
    assert snap['cumulative_usd'] == 0.353834632


def test_exact_decimal_boundary_and_released_reservation(ledger):
    budget = Budget(ledger, 0.3, 600)
    ids = [budget.reserve('test', 0.1) for _ in range(3)]
    assert budget.snapshot()['committed_usd'] == 0.3
    with pytest.raises(BudgetExceeded):
        budget.reserve('test', 0.000000001)
    budget.finish(ids[0], 0.05, True)
    budget.reserve('test', 0.05)
    assert budget.snapshot()['committed_usd'] == 0.3


def test_call_cap_counts_reserved_even_after_finish(ledger):
    budget = Budget(ledger, 0.5, 2)
    for _ in range(2):
        budget.finish(budget.reserve('test', 0), 0, True)
    with pytest.raises(BudgetExceeded):
        budget.reserve('test', 0)


def test_reopen_preserves_unfinished_and_unknown_usage(ledger):
    first = Budget(ledger, 0.5, 600, BASELINE)
    pending = first.reserve('pending', 0.05)
    unknown = first.reserve('unknown', 0.03)
    assert first.finish(unknown) == 0.03
    reopened = Budget(ledger, 0.5, 600, BASELINE)
    assert reopened.snapshot()['reserved_calls'] == 2
    assert reopened.snapshot()['finished_calls'] == 1
    assert reopened.snapshot()['unknown_reserved_usd'] == 0.08
    assert reopened.finish(unknown) == 0.03
    # Actual usage can arrive later without inventing zero cost in the meantime.
    reopened.finish(unknown, 0.01, True)
    reopened.finish(pending, 0.02, True)
    assert reopened.snapshot()['known_usd'] == 0.03
    assert reopened.snapshot()['unknown_reserved_usd'] == 0


def test_finish_idempotence_and_conflict(ledger):
    budget = Budget(ledger, 0.5, 600)
    call_id = budget.reserve('test', 0.1)
    assert budget.finish(call_id, 0.04, True) == 0.04
    assert budget.finish(call_id, Decimal('0.040'), True) == 0.04
    assert budget.finish(call_id) == 0.04
    with pytest.raises(FinishConflict):
        budget.finish(call_id, 0.03, True)
    assert budget.snapshot()['known_usd'] == 0.04
    with pytest.raises(KeyError):
        budget.finish('not-reserved', 0, True)


def test_overrun_recorded_and_permanently_locks_new_reservations(ledger):
    budget = Budget(ledger, 0.5, 600, BASELINE)
    call_id = budget.reserve('test', 0.01)
    other = budget.reserve('test', 0.02)
    assert budget.finish(call_id, 0.03, True) == 0.03
    assert budget.snapshot()['locked']
    with pytest.raises(BudgetLocked):
        budget.reserve('test', 0)
    reopened = Budget(ledger, 0.5, 600, BASELINE)
    with pytest.raises(BudgetLocked):
        reopened.reserve('test', 0)
    reopened.finish(other, 0.005, True)
    assert reopened.snapshot()['known_usd'] == 0.035
    assert reopened.snapshot()['locked']


def test_overrun_larger_than_cap_is_not_hidden(ledger):
    budget = Budget(ledger, 0.5, 600, BASELINE)
    call_id = budget.reserve('test', 0.5)
    budget.finish(call_id, 0.7, True)
    snap = budget.snapshot()
    assert snap['committed_usd'] == 0.7
    assert snap['cumulative_usd'] == 1.049834632
    assert snap['locked']


@pytest.mark.parametrize('field,value', [('cap', -1), ('cap', float('nan')), ('cap', float('inf')),
                                       ('cap', True), ('baseline', -1), ('baseline', float('inf')),
                                       ('calls', -1), ('calls', True), ('calls', 1.5)])
def test_invalid_configuration(ledger, field, value):
    args = {'cap_usd': 0.5, 'max_calls': 600, 'baseline_usd': BASELINE}
    args[{'cap': 'cap_usd', 'baseline': 'baseline_usd', 'calls': 'max_calls'}[field]] = value
    with pytest.raises(ValueError):
        Budget(ledger, **args)


@pytest.mark.parametrize('value', [-1, True, float('nan'), float('inf'), '0.01', None])
def test_invalid_reservation_value_does_not_consume_call(ledger, value):
    budget = Budget(ledger, 0.5, 600)
    with pytest.raises(ValueError):
        budget.reserve('test', value)
    assert budget.snapshot()['reserved_calls'] == 0


@pytest.mark.parametrize('lane', ['', ' ', ' test', None, 1])
def test_invalid_lane(ledger, lane):
    budget = Budget(ledger, 0.5, 600)
    with pytest.raises(ValueError):
        budget.reserve(lane, 0.01)
    assert budget.snapshot()['reserved_calls'] == 0


@pytest.mark.parametrize('metadata', [{'api_key': 'test-placeholder'}, {'nested': {'ACOP_API_KEY': 'test-placeholder'}},
                                      {'authorization': 'test-placeholder'}, {'x': float('nan')}, [], {1: 'x'}])
def test_reject_sensitive_or_invalid_metadata(ledger, metadata):
    budget = Budget(ledger, 0.5, 600)
    with pytest.raises((ValueError, TypeError)):
        budget.reserve('test', 0.01, metadata)
    assert budget.snapshot()['reserved_calls'] == 0


@pytest.mark.parametrize('actual,known', [(None, True), (0.01, False), (-1, True), (True, True),
                                        (float('nan'), True), (float('inf'), True), (0.01, 1)])
def test_invalid_finish_preserves_reservation(ledger, actual, known):
    budget = Budget(ledger, 0.5, 600)
    call_id = budget.reserve('test', 0.02)
    with pytest.raises(ValueError):
        budget.finish(call_id, actual, known)
    assert budget.snapshot()['unknown_reserved_usd'] == 0.02
    assert budget.snapshot()['finished_calls'] == 0


@pytest.mark.parametrize('cap,calls,baseline', [(0.6, 600, BASELINE), (0.5, 601, BASELINE), (0.5, 600, 0)])
def test_configuration_cannot_change_on_restart(ledger, cap, calls, baseline):
    Budget(ledger, 0.5, 600, BASELINE)
    with pytest.raises(ValueError, match='configuration_mismatch'):
        Budget(ledger, cap, calls, baseline)


def test_zero_cap_and_zero_calls(ledger):
    budget = Budget(ledger, 0, 0)
    with pytest.raises(BudgetExceeded):
        budget.reserve('test', 0)


@pytest.mark.parametrize('cap,max_calls,accepted_count', [(0.1, 600, 10), (0.5, 7, 7)])
def test_actual_multiprocess_reservation_race(ledger, cap, max_calls, accepted_count):
    ctx = mp.get_context('spawn')
    gate = ctx.Event()
    processes = []
    readers = []
    for _ in range(4):
        reader, writer = ctx.Pipe(duplex=False)
        process = ctx.Process(target=_race_reserve, args=(str(ledger), cap, max_calls, 20, gate, writer))
        process.start()
        writer.close()
        processes.append(process)
        readers.append(reader)
    gate.set()
    ids = [call_id for reader in readers for call_id in _receive(reader)]
    for process in processes:
        _join(process)
    assert len(ids) == len(set(ids)) == accepted_count
    assert all(uuid.UUID(call_id).version == 4 for call_id in ids)
    snap = Budget(ledger, cap, max_calls, BASELINE).snapshot()
    assert snap['reserved_calls'] == accepted_count
    assert snap['committed_usd'] == float(Decimal('0.01') * accepted_count)
    assert snap['committed_usd'] <= cap


def test_actual_multiprocess_duplicate_finish(ledger):
    budget = Budget(ledger, 0.5, 600, BASELINE)
    call_id = budget.reserve('test', 0.01)
    ctx = mp.get_context('spawn')
    gate = ctx.Event()
    workers = []
    readers = []
    for _ in range(4):
        reader, writer = ctx.Pipe(duplex=False)
        worker = ctx.Process(target=_race_finish, args=(str(ledger), call_id, gate, writer))
        worker.start()
        writer.close()
        readers.append(reader)
        workers.append(worker)
    gate.set()
    assert [_receive(reader) for reader in readers] == [0.005] * 4
    for worker in workers:
        _join(worker)
    assert budget.snapshot()['finished_calls'] == 1
    assert budget.snapshot()['known_usd'] == 0.005


def test_actual_process_death_keeps_committed_reservation(ledger):
    ctx = mp.get_context('spawn')
    reader, writer = ctx.Pipe(duplex=False)
    worker = ctx.Process(target=_reserve_then_exit, args=(str(ledger), writer))
    worker.start()
    writer.close()
    call_id = _receive(reader)
    _join(worker, 23)
    budget = Budget(ledger, 0.5, 600, BASELINE)
    assert uuid.UUID(call_id).version == 4
    snap = budget.snapshot()
    assert snap['reserved_calls'] == 1
    assert snap['finished_calls'] == 0
    assert snap['unknown_reserved_usd'] == 0.04


def test_actual_process_death_rolls_back_uncommitted_transaction(ledger):
    budget = Budget(ledger, 0.5, 600, BASELINE)
    ctx = mp.get_context('spawn')
    reader, writer = ctx.Pipe(duplex=False)
    worker = ctx.Process(target=_uncommitted_exit, args=(str(ledger), writer))
    worker.start()
    writer.close()
    assert _receive(reader) == 'inserted'
    _join(worker, 25)
    assert budget.snapshot()['reserved_calls'] == 0
    with sqlite3.connect(ledger) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


@pytest.mark.parametrize('crash', [False, True])
def test_actual_process_run_lock_contention_and_release(ledger, crash):
    budget = Budget(ledger, 0.5, 600, BASELINE)
    ctx = mp.get_context('spawn')
    gate = ctx.Event()
    reader, writer = ctx.Pipe(duplex=False)
    worker = ctx.Process(target=_hold_lock, args=(str(ledger), gate, writer, crash))
    worker.start()
    writer.close()
    assert _receive(reader) == 'locked'
    try:
        with pytest.raises(RunLocked):
            with budget.run_lock():
                pytest.fail('lock allowed a competing process')
    finally:
        gate.set()
        _join(worker, 24 if crash else 0)
    with budget.run_lock():
        assert budget.snapshot()['reserved_calls'] == 0


def test_same_process_lock_and_exception_release(ledger):
    with pytest.raises(RuntimeError, match='body_failure'):
        with run_lock(ledger):
            with pytest.raises(RunLocked):
                with run_lock(ledger):
                    pytest.fail('second lock should fail immediately')
            raise RuntimeError('body_failure')
    with run_lock(ledger):
        pass
