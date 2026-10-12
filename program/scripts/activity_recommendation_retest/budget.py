"""SQLite research budget; no credentials, provider imports, or network access.

Amounts are stored as decimal text and summed as Decimal while an IMMEDIATE
transaction holds the write lock. The caller supplies conservative upper bounds.
Use ``with budget.run_lock():`` around a paid run, in addition to per-call reserve.
Metadata must contain public research identifiers only, never credentials.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Iterator
import uuid


class BudgetExceeded(RuntimeError):
    pass


class BudgetLocked(RuntimeError):
    pass


class RunLocked(RuntimeError):
    pass


class FinishConflict(ValueError):
    pass


def _amount(value, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(name + ': expected finite nonnegative number')
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError(name + ': expected finite nonnegative number')
    # Public snapshots use JSON-compatible floats; reject values they cannot hold.
    if not math.isfinite(float(result)):
        raise ValueError(name + ': number exceeds snapshot range')
    return result


def _metadata(value) -> str:
    if value is None:
        return '{}'
    if not isinstance(value, dict):
        raise ValueError('metadata: expected object')
    sensitive = {'api_key', 'apikey', 'api-key', 'authorization', 'password',
                 'secret', 'access_token', 'refresh_token', 'token'}

    def check(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError('metadata: string field names required')
                lowered = key.lower()
                if lowered in sensitive or lowered.endswith(('_api_key', '_secret', '_password', '_token')):
                    raise ValueError('metadata: credential field forbidden')
                check(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check(child)

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


@contextmanager
def run_lock(path) -> Iterator[None]:
    """Nonblocking OS process lock associated with a SQLite ledger path.

    The file is intentionally retained. Removing a held lock file could create
    two different lock objects for the same ledger. Process death releases the
    operating-system lock, including Windows ``msvcrt`` byte-range locks.
    """
    ledger = Path(path).expanduser().resolve()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(ledger) + '.run.lock')
    with lock_path.open('a+b') as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RunLocked('run_locked') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Budget:
    def __init__(self, path, cap_usd, max_calls, baseline_usd=0.0):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cap = _amount(cap_usd, 'cap_usd')
        baseline = _amount(baseline_usd, 'baseline_usd')
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 0:
            raise ValueError('max_calls: expected nonnegative integer')
        if not math.isfinite(float(cap + baseline)):
            raise ValueError('cumulative cap exceeds snapshot range')
        with self._transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), cap TEXT NOT NULL, max_calls INTEGER NOT NULL, baseline TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS calls (call_id TEXT PRIMARY KEY, lane TEXT NOT NULL, upper_usd TEXT NOT NULL, actual_usd TEXT, finished INTEGER NOT NULL DEFAULT 0, usage_known INTEGER NOT NULL DEFAULT 0, metadata TEXT NOT NULL, reserved_at TEXT NOT NULL, finished_at TEXT)')
            settings = db.execute('SELECT * FROM settings WHERE id=1').fetchone()
            if settings is None:
                db.execute('INSERT INTO settings (id,cap,max_calls,baseline) VALUES (1,?,?,?)', (str(cap), max_calls, str(baseline)))
            elif (Decimal(settings['cap']), settings['max_calls'], Decimal(settings['baseline'])) != (cap, max_calls, baseline):
                raise ValueError('budget_configuration_mismatch')

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _totals(db):
        rows = db.execute('SELECT upper_usd,actual_usd,finished,usage_known FROM calls').fetchall()
        known = sum((Decimal(r['actual_usd']) for r in rows if r['usage_known']), Decimal(0))
        unknown = sum((Decimal(r['upper_usd']) for r in rows if not r['usage_known']), Decimal(0))
        return rows, known, unknown

    def reserve(self, lane, upper_usd, metadata=None):
        upper = _amount(upper_usd, 'upper_usd')
        if not isinstance(lane, str) or not lane.strip() or lane != lane.strip():
            raise ValueError('lane: expected nonempty trimmed string')
        encoded = _metadata(metadata)
        with self._transaction() as db:
            settings = db.execute('SELECT * FROM settings WHERE id=1').fetchone()
            if settings['locked']:
                raise BudgetLocked('budget_locked_after_reservation_exceeded')
            rows, known, unknown = self._totals(db)
            if len(rows) >= settings['max_calls'] or known + unknown + upper > Decimal(settings['cap']):
                raise BudgetExceeded('budget_stop')
            call_id = str(uuid.uuid4())
            db.execute('INSERT INTO calls (call_id,lane,upper_usd,metadata,reserved_at) VALUES (?,?,?,?,?)',
                       (call_id, lane, str(upper), encoded, datetime.now(timezone.utc).isoformat()))
        return call_id

    def finish(self, call_id, actual_usd=None, usage_known=False):
        if type(usage_known) is not bool:
            raise ValueError('usage_known: expected bool')
        if usage_known != (actual_usd is not None):
            raise ValueError('actual_usd required exactly when usage_known is true')
        actual = _amount(actual_usd, 'actual_usd') if usage_known else None
        with self._transaction() as db:
            row = db.execute('SELECT * FROM calls WHERE call_id=?', (call_id,)).fetchone()
            if row is None:
                raise KeyError('unknown_call_id')
            upper = Decimal(row['upper_usd'])
            if row['usage_known']:
                recorded = Decimal(row['actual_usd'])
                # A late missing-usage notification must not undo known accounting.
                if actual is None or actual == recorded:
                    return float(recorded)
                raise FinishConflict('conflicting_finish')
            if actual is not None:
                db.execute('UPDATE calls SET actual_usd=?,finished=1,usage_known=1,finished_at=? WHERE call_id=?',
                           (str(actual), datetime.now(timezone.utc).isoformat(), call_id))
                if actual > upper:
                    db.execute('UPDATE settings SET locked=1 WHERE id=1')
                return float(actual)
            if not row['finished']:
                db.execute('UPDATE calls SET finished=1,finished_at=? WHERE call_id=?',
                           (datetime.now(timezone.utc).isoformat(), call_id))
            return float(upper)

    def snapshot(self):
        with self._transaction() as db:
            settings = db.execute('SELECT * FROM settings WHERE id=1').fetchone()
            rows, known, unknown = self._totals(db)
            committed = known + unknown
            baseline = Decimal(settings['baseline'])
            return {'reserved_calls': len(rows), 'finished_calls': sum(r['finished'] for r in rows),
                    'known_usd': float(known), 'unknown_reserved_usd': float(unknown),
                    'committed_usd': float(committed), 'cap_usd': float(Decimal(settings['cap'])),
                    'baseline_usd': float(baseline), 'cumulative_usd': float(baseline + committed),
                    'max_calls': settings['max_calls'], 'locked': bool(settings['locked'])}

    def run_lock(self):
        return run_lock(self.path)
