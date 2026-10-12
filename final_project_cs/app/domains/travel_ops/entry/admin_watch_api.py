"""운영자 전용 여행 감시 현황·회차 이력 읽기. 외부 소스를 호출하지 않는다."""
from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.errors import UndefinedTable

from app.application.job_gate import WATCH_GATE, interval_seconds
from app.core.settings import get_guardrails, get_settings
from app.infrastructure.db.session import get_connection

_COLUMNS = 'run_id,started_at,finished_at,forced,interval_seconds,status,counts,error_type'


def _run(row):
    if row is None:
        return None
    identity, start, end, forced, interval, status, counts, error = row
    return {'run_id': str(identity), 'started_at': start.isoformat(), 'finished_at': end.isoformat() if end else None,
            'forced': forced, 'interval_seconds': interval, 'status': status, 'counts': counts, 'error_type': error,
            'duration_seconds': (end-start).total_seconds() if end else None}


def _decode(cursor: str):
    try:
        stamp, identity = base64.urlsafe_b64decode(cursor.encode()).decode().split('|')
        value = datetime.fromisoformat(stamp)
        if value.tzinfo is None:
            raise ValueError
        return value, UUID(identity)
    except (ValueError, UnicodeError):
        raise HTTPException(422, '이전 회차 위치가 잘못되었습니다. 처음부터 다시 읽어 주세요.') from None


def _encode(row):
    return base64.urlsafe_b64encode(f'{row[1].isoformat()}|{row[0]}'.encode()).decode()


def build_router(*, operator_dependency, require_permission):
    router = APIRouter(prefix='/admin/api/watch-runs', tags=['operations-watch-history'])

    @router.get('')
    def listing(op=Depends(operator_dependency), since: datetime | None = None, until: datetime | None = None,
                status: Literal['running','completed','attention','failed'] | None = None,
                trip_id: UUID | None = None, cursor: str | None = Query(None, max_length=300),
                limit: int = Query(30, ge=1, le=50)):
        require_permission(op, 'ops:introspect')
        tenant = get_settings().tenant_id
        # 기록의 clock_timestamp()와 같은 DB 시계를 쓴다. 앱 시계와의 차이로 최신 기록을 빠뜨리지 않는다.
        with get_connection() as conn:
            now = conn.execute('SELECT clock_timestamp()').fetchone()[0]
        since, until = since or now-timedelta(days=7), until or now
        if since.tzinfo is None or until.tzinfo is None or since >= until:
            raise HTTPException(422, '시작·끝 시각은 시간대를 포함하고 시작이 끝보다 빨라야 합니다.')
        interval, _ = interval_seconds(get_guardrails())
        where, args = ['r.tenant_id=%s', 'r.started_at >= %s', 'r.started_at <= %s'], [tenant, since, until]
        if status:
            where.append('r.status=%s'); args.append(status)
        if trip_id:
            where.append('EXISTS(SELECT 1 FROM travel_watch_checks c WHERE c.tenant_id=r.tenant_id AND c.run_id=r.run_id AND c.trip_id=%s)')
            args.append(trip_id)
        if cursor:
            where.append('(r.started_at,r.run_id)<(%s,%s)'); args.extend(_decode(cursor))
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(f'SELECT {_COLUMNS} FROM travel_watch_runs r WHERE ' + ' AND '.join(where) +
                            ' ORDER BY r.started_at DESC,r.run_id DESC LIMIT %s', (*args, limit+1))
                rows = cur.fetchall()
                cur.execute(f'SELECT {_COLUMNS} FROM travel_watch_runs WHERE tenant_id=%s ORDER BY started_at DESC,run_id DESC LIMIT 1', (tenant,))
                latest = _run(cur.fetchone())
                cur.execute(f'SELECT {_COLUMNS} FROM travel_watch_runs WHERE tenant_id=%s AND NOT forced ORDER BY started_at DESC,run_id DESC LIMIT 1', (tenant,))
                scheduled = _run(cur.fetchone())
                cur.execute('SELECT last_run_at FROM job_gates WHERE tenant_id=%s AND gate=%s', (tenant, WATCH_GATE))
                gate = cur.fetchone()
                cur.execute('SELECT DISTINCT t.trip_id,t.title FROM travel_watch_checks c JOIN trips t '
                            'ON t.tenant_id=c.tenant_id AND t.trip_id=c.trip_id WHERE c.tenant_id=%s ORDER BY t.title,t.trip_id', (tenant,))
                trips = [{'trip_id': str(identity), 'title': title} for identity, title in cur.fetchall()]
        except UndefinedTable:
            raise HTTPException(503, '감시 이력 DB가 준비되지 않았습니다. 마이그레이션 228 적용이 필요합니다.') from None
        gate_at = gate[0] if gate else None
        freshness = 'not_recorded'
        if scheduled:
            reference = datetime.fromisoformat(scheduled['started_at'])
            freshness = 'delayed' if (now-reference).total_seconds() > interval*2 else scheduled['status']
        return {'as_of': now.isoformat(), 'interval_seconds': interval, 'last_gate_at': gate_at.isoformat() if gate_at else None,
                'next_expected_at': (gate_at+timedelta(seconds=interval)).isoformat() if gate_at else None,
                'freshness': freshness, 'latest': latest, 'latest_scheduled': scheduled, 'trips': trips,
                'runs': [_run(row) for row in rows[:limit]], 'next_cursor': _encode(rows[limit-1]) if len(rows)>limit else None}

    @router.get('/{run_id}')
    def detail(run_id: UUID, op=Depends(operator_dependency), after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
        require_permission(op, 'ops:introspect')
        tenant = get_settings().tenant_id
        try:
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute(f'SELECT {_COLUMNS} FROM travel_watch_runs WHERE tenant_id=%s AND run_id=%s', (tenant, run_id))
                run = _run(cur.fetchone())
                if run is None:
                    raise HTTPException(404, '감시 회차를 찾을 수 없습니다.')
                cur.execute('SELECT c.check_id,c.at,c.stage,c.trip_id,t.title,c.item_id,c.target_title,c.report '
                            'FROM travel_watch_checks c LEFT JOIN trips t ON t.tenant_id=c.tenant_id AND t.trip_id=c.trip_id '
                            'WHERE c.tenant_id=%s AND c.run_id=%s AND c.check_id>%s ORDER BY c.check_id LIMIT %s',
                            (tenant, run_id, after, limit+1))
                rows = cur.fetchall()
        except UndefinedTable:
            raise HTTPException(503, '감시 이력 DB가 준비되지 않았습니다. 마이그레이션 228 적용이 필요합니다.') from None
        return {'run': run, 'events': [dict(check_id=identity, at=at.isoformat(), stage=stage,
                trip_id=str(trip) if trip else None, trip_title=title, item_id=str(item) if item else None,
                target_title=target, report=report) for identity, at, stage, trip, title, item, target, report in rows[:limit]],
                'next_after': rows[limit-1][0] if len(rows)>limit else None}

    return router
