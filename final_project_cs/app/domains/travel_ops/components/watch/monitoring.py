"""실제 감시 실행의 회차·점검 결과를 보관한다. 조회는 외부 소스를 호출하지 않는다."""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.domains.travel_ops.components import candidate_diagnostics

from app.infrastructure.db.session import get_connection

_current: ContextVar[tuple | None] = ContextVar('travel_watch_run', default=None)
# 공급자 원문 전체를 저장하지 않는다. 판정에 쓰는 값과 알려진 상태만 보관한다.
_FIELDS = frozenset('verdict checks category status mode simulation_id source confirmed_at checked_at starts_at '
    'failed_categories not_connected disruptions advisories field value limit kind magnitude distance_km '
    'precipitation_probability wind_speed_kmh temperature pm10 pm25 reason tried fell_back_from '
    'target targets event_type code name level label phase pause_id case_id item item_id trip_id '
    'issue_code shelters shelter_status number released attempt outcome action counts observation '
    'target_place review_target district_basis basis_source impact impact_by messages matched unrelated unassessed relation '
    'exception_type error text message road station at indoor_unknown '
    'region regions serial published_at received_at fetched_at observed_at from_cache count error_code '
    'for_region announced_at areas events active window rules magnitude_min radius_km lookback_hours '
    'pm10_grade pm25_grade warning message_id unclassified weather_held_back partial_from note '
    'created_at occurred_at latitude longitude covered step district district_basis coverage from to '
    'for_place depth_km location intensity remark notice_type candidate_key reasons rank'.split())


def _safe(value):
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if k in _FIELDS}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value[:100]]
    if isinstance(value, (UUID, datetime)):
        return str(value)
    if isinstance(value, str):
        # 오류 원문·주소를 결과 필드에 끼워 넣어도 접속 정보는 보관하지 않는다.
        import re
        value = re.sub(r'https?://\S+|\b(?:\d{1,3}\.){3}\d{1,3}\b', '[주소 가림]', value)
        value = re.sub(r'(?i)(token|secret|password|api[_-]?key|authorization)\s*[:=]\s*\S+', r'\1=[가림]', value)
        return value[:1000]
    return value if value is None or isinstance(value, (int, float, bool)) else str(type(value).__name__)


def recording() -> bool:
    """정상 회차에 결과를 보관할 수 있는 문맥인가."""
    return _current.get() is not None


def record(stage: str, *, trip_id=None, item_id=None, target_title=None, report: dict) -> None:
    current = _current.get()
    if current is None:
        return
    tenant, run_id, connect = current
    with connect() as conn, conn.transaction():
        conn.execute('INSERT INTO travel_watch_checks(tenant_id,run_id,stage,trip_id,item_id,target_title,report) '
                     'VALUES(%s,%s,%s,%s,%s,%s,%s)',
                     (tenant, run_id, stage, trip_id, item_id, _safe(target_title), Jsonb(_safe(report))))


def outcomes(stage: str, result) -> None:
    if _current.get() is None:
        return
    for action, values in vars(result).items():
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                record(stage, trip_id=value.get('trip_id'), target_title=value.get('item'),
                       report={'action': action, **value})


def execute(tenant: str, *, forced: bool, interval: float, work, connection_factory=None):
    connect = connection_factory or get_connection
    run_id = uuid4()
    with connect() as conn, conn.transaction():
        conn.execute('INSERT INTO travel_watch_runs(tenant_id,run_id,forced,interval_seconds,status) '
                     "VALUES(%s,%s,%s,%s,'running')", (tenant, run_id, forced, interval))
    token = _current.set((tenant, run_id, connect))
    try:
        def candidate_record(event):
            record('candidate_evaluation', trip_id=event.get('trip_id'), item_id=event.get('item_id'),
                   target_title=event.get('target_title'), report=event)

        with candidate_diagnostics.observe(candidate_record):
            counts = work()
    except Exception as exc:
        with connect() as conn, conn.transaction():
            conn.execute("UPDATE travel_watch_runs SET status='failed',finished_at=clock_timestamp(),error_type=%s "
                         'WHERE tenant_id=%s AND run_id=%s', (type(exc).__name__, tenant, run_id))
        raise
    else:
        attention = any(v for k, v in counts.items() if any(word in k for word in ('fatal', 'errored', 'escalated', 'unchecked', 'unhandled')))
        with connect() as conn, conn.transaction():
            conn.execute('UPDATE travel_watch_runs SET status=%s,finished_at=clock_timestamp(),counts=%s '
                         'WHERE tenant_id=%s AND run_id=%s',
                         ('attention' if attention else 'completed', Jsonb(counts), tenant, run_id))
        return counts
    finally:
        _current.reset(token)
