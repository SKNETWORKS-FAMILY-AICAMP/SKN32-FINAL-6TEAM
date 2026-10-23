"""Persist service announcements and customer delivery in the same transaction."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from app.application import admin_service

KST = ZoneInfo('Asia/Seoul')


def prepare(conn, tenant: str, command: dict) -> bool:
    """Lock a request and reject conflicting retries before changing public state."""
    if command.get('audience', 'all') == 'customer':
        if not command.get('notifyUsers'):
            raise admin_service.AdminServiceError(422, '지정 고객 공지는 고객 알림을 켠 뒤 보내 주세요.')
        if not command.get('customerId'):
            raise admin_service.AdminServiceError(422, '알림 받을 고객 계정 ID를 입력해 주세요.')
        admin_service.require_customer(conn, tenant, str(command['customerId']))
    elif command.get('customerId'):
        raise admin_service.AdminServiceError(422, '전체 고객을 선택하면 개별 고객 ID를 비워 주세요.')
    identity = command.get('requestId')
    if not identity:
        if command.get('notifyUsers'):
            raise admin_service.AdminServiceError(422, '알림 요청 번호가 필요합니다. 화면에서 다시 보내 주세요.')
        return False
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (f'service-notice:{tenant}:{identity}',))
    previous = admin_service.record(conn, tenant, 'service_delivery', str(identity))
    if previous and previous.get('fingerprint') != fingerprint(command):
        raise admin_service.AdminServiceError(409, '같은 요청 번호의 내용이 달라졌습니다. 목록을 다시 읽어 주세요.')
    return bool(previous)


def fingerprint(command: dict) -> str:
    return hashlib.sha256(json.dumps(command, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def persist(conn, tenant: str, actor: str, command: dict, *, title: str, body: str,
            start: datetime, end: datetime | None) -> None:
    identity = command.get('requestId')
    if not identity:
        return
    queued = 0
    if command.get('notifyUsers'):
        with conn.cursor() as cur:
            query = ('SELECT c.customer_id, COALESCE((SELECT t.locale FROM trips t '
                     'WHERE t.tenant_id=c.tenant_id AND t.customer_id=c.customer_id '
                     'ORDER BY t.created_at DESC LIMIT 1), %s) FROM customers c '
                     'WHERE c.tenant_id=%s AND NOT EXISTS (SELECT 1 FROM admin_records u '
                     "WHERE u.tenant_id=c.tenant_id AND u.kind='user' AND u.id=c.customer_id::text "
                     "AND u.value->>'blocked'='true')")
            params = ['ko', tenant]
            if command.get('audience') == 'customer':
                query += ' AND c.customer_id=%s'
                params.append(UUID(str(command['customerId'])))
            cur.execute(query, params)
            recipients = cur.fetchall()
            for customer, locale in recipients:
                payload = {'type':'change_notice', 'kind':'service_notice', 'locale':locale,
                           'text':f'📢 {title}\n{body}', 'service_notice_id':str(identity),
                           'visible_at':start.isoformat(), 'expires_at':end.isoformat() if end else None}
                cur.execute('INSERT INTO outbox(tenant_id,topic,dedupe_key,payload_json,available_at) '
                            "VALUES(%s,'customer.notice',%s,%s,%s) "
                            'ON CONFLICT(tenant_id,topic,dedupe_key) DO NOTHING RETURNING message_id',
                            (tenant, f'{customer}:service:{identity}', Jsonb(payload), start))
                queued += int(cur.fetchone() is not None)
    admin_service.put(conn, tenant, 'service_delivery', str(identity),
                      {'fingerprint':fingerprint(command), 'queued':queued, 'kind':command['type']},
                      actor=actor, action='service-notice-enqueued', reason='고객 공지 알림 등록')


def delivery(conn, tenant: str, identity: str) -> dict:
    marker = admin_service.record(conn, tenant, 'service_delivery', identity)
    if not marker:
        raise admin_service.AdminServiceError(404, '고객 발송 기록을 찾을 수 없습니다.')
    with conn.cursor() as cur:
        cur.execute("SELECT status,count(*) FROM outbox WHERE tenant_id=%s AND topic='customer.notice' "
                    "AND payload_json->>'service_notice_id'=%s GROUP BY status", (tenant, identity))
        counts = dict(cur.fetchall())
    return {'stored':sum(counts.values()), 'delivered':counts.get('delivered',0),
            'pending':counts.get('pending',0)+counts.get('processing',0),
            'skipped':counts.get('skipped',0), 'unknown':counts.get('unknown',0),
            'failed':counts.get('dead_letter',0)}
