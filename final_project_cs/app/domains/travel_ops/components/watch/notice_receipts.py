"""공식 재난문자 API에서 실제 읽은 메시지와 수신 상태를 보관한다."""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.core.settings import get_settings
from app.infrastructure.db.session import get_connection
from app.domains.travel_ops.components.watch.monitoring import _safe

log = logging.getLogger(__name__)
MESSAGE_KIND = 'watch_disaster_receipt'
STATUS_KIND = 'watch_disaster_receipt_status'
API_KIND = 'watch_disaster_api_receipt'


def record(receipt: dict) -> None:
    tenant = get_settings().tenant_id
    received_at = datetime.now(UTC).isoformat()
    try:
        with get_connection() as conn, conn.transaction():
            status = {k: receipt.get(k) for k in ('status', 'region', 'source', 'fetched_at', 'from_cache', 'error_code')}
            status.update(observed_at=received_at, count=len(receipt.get('rows') or []))
            conn.execute('INSERT INTO admin_records(tenant_id,kind,id,value) VALUES(%s,%s,%s,%s) '
                         'ON CONFLICT(tenant_id,kind,id) DO UPDATE SET value=EXCLUDED.value,updated_at=now()',
                         (tenant, STATUS_KIND, str(receipt.get('region') or 'unknown'), Jsonb(status)))
            conn.execute('INSERT INTO admin_records(tenant_id,kind,id,value) VALUES(%s,%s,%s,%s)',
                         (tenant, API_KIND, str(uuid4()), Jsonb(_safe({**status, 'category': 'disaster_msg', 'mode': 'api'}))))
            for row in receipt.get('rows') or []:
                identity = hashlib.sha256(str(row.get('serial') or (str(row.get('created_at'))+row.get('text',''))).encode()).hexdigest()
                value = {'serial': str(row.get('serial') or ''), 'kind': _safe(row.get('kind')),
                         'step': _safe(row.get('step')), 'text': _safe(row.get('text')),
                         'regions': [_safe(v) for v in row.get('regions') or []],
                         'published_at': str(row.get('created_at')), 'received_at': received_at,
                         'source': 'disaster_msg', 'mode': 'api', 'fetched_at': receipt.get('fetched_at')}
                conn.execute('INSERT INTO admin_records(tenant_id,kind,id,value) VALUES(%s,%s,%s,%s) '
                             'ON CONFLICT(tenant_id,kind,id) DO NOTHING',
                             (tenant, MESSAGE_KIND, identity, Jsonb(value)))
    except Exception as exc:
        log.error('disaster_receipt_record_failed error_type=%s', type(exc).__name__)


def view(conn, tenant: str, *, limit: int = 50) -> dict:
    status = conn.execute('SELECT value FROM admin_records WHERE tenant_id=%s AND kind=%s ORDER BY updated_at DESC',
                          (tenant, STATUS_KIND)).fetchall()
    total = conn.execute('SELECT count(*) FROM admin_records WHERE tenant_id=%s AND kind=%s',
                         (tenant, MESSAGE_KIND)).fetchone()[0]
    rows = conn.execute("SELECT value FROM admin_records WHERE tenant_id=%s AND kind=%s "
                        "ORDER BY value->>'published_at' DESC,id LIMIT %s", (tenant, MESSAGE_KIND, limit)).fetchall()
    latest = conn.execute('SELECT run_id,status,started_at,finished_at,counts FROM travel_watch_runs '
                          'WHERE tenant_id=%s ORDER BY started_at DESC LIMIT 1', (tenant,)).fetchone()
    return {'statuses': [r[0] for r in status], 'messages': [r[0] for r in rows], 'total': total,
            'limit': limit, 'has_more': total > len(rows),
            'latest_run': dict(zip(('run_id','status','started_at','finished_at','counts'), latest)) if latest else None}


def register() -> None:
    from app.domains.travel_ops.ports.data_sources import disaster_msg
    disaster_msg.set_receipt_sink(record)


def poll(sources) -> None:
    """공유 캐시·호출 예산을 지키며 소스 수신을 여행 검사와 별도로 확인한다."""
    from app.domains.travel_ops.ports.data_sources import disaster_msg
    disaster_msg.set_receipt_sink(record)
    source = getattr(sources, 'disaster', None)
    if source is None or getattr(source, 'mode', None) != 'api':
        record({'status': 'not_connected', 'source': 'disaster_msg', 'region': '서울',
                'error_code': 'live_api_not_connected', 'rows': []})
        return
    try:
        source.active(region='서울', at=datetime.now(UTC))
    except Exception as exc:
        record({'status': 'failed', 'source': 'disaster_msg', 'region': '서울',
                'error_code': type(exc).__name__, 'rows': []})
        log.error('disaster_receipt_poll_failed error_type=%s', type(exc).__name__)
