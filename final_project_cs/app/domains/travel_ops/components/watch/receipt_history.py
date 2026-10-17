"""저장된 문자·API 점검·모의 입력을 기간과 입력 구분으로 읽는다."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone

from fastapi import HTTPException

from app.domains.travel_ops.components.planning.safety import SafetyRules
from app.domains.travel_ops.components.watch.monitoring import _safe
from app.domains.travel_ops.components.watch.receipt_impact import SCOPES, describe

KST = timezone(timedelta(hours=9))
PAGE_SIZE = 50
_CATEGORIES = "('forecast','weather_warning','disaster_msg','traffic_control','air_quality','earthquake')"

# 각 가지에서 테넌트·기간을 먼저 제한한 뒤 JSON 배열을 펼친다.
_RECORDS = """
WITH records AS (
 SELECT 'message:'||r.id AS id, r.updated_at AS received_at, 'actual' AS mode,
        'disaster_message' AS record_type, 'disaster_msg' AS category,
        'received' AS status, '공식 재난문자 API' AS source,
        NULL::text AS trip_id, NULL::text AS target_title, 'receipt' AS stage,
        r.value AS payload
 FROM admin_records r
 WHERE r.tenant_id=%s AND r.kind='watch_disaster_receipt'
   AND r.updated_at >= %s AND r.updated_at < %s AND r.updated_at <= %s
 UNION ALL
 SELECT 'receipt:'||r.id, r.updated_at, 'actual', 'api_receipt', 'disaster_msg',
        r.value->>'status', r.value->>'source', NULL, NULL, 'receipt', r.value
 FROM admin_records r
 WHERE r.tenant_id=%s AND r.kind='watch_disaster_api_receipt'
   AND r.updated_at >= %s AND r.updated_at < %s AND r.updated_at <= %s
 UNION ALL
 SELECT 'check:'||c.check_id::text||':'||part.position::text, c.at,
        CASE WHEN COALESCE(part.value->>'mode',part.value#>>'{value,mode}')
                  IN ('simulation','mock','fixture','sample','dataset')
             THEN 'simulation' ELSE 'actual' END,
        'api_check', part.value->>'category', part.value->>'status',
        part.value->>'source', c.trip_id::text, c.target_title, c.stage,
        part.value || jsonb_build_object('disruptions',c.report->'disruptions',
                                        'advisories',c.report->'advisories',
                                        'verdict',c.report->'verdict',
                                        'simulation_target',c.stage='simulation_full' OR EXISTS (
                                            SELECT 1 FROM jsonb_array_elements(
                                                CASE WHEN jsonb_typeof(c.report->'checks')='array'
                                                     THEN c.report->'checks' ELSE '[]'::jsonb END) AS trial
                                            WHERE COALESCE(trial->>'mode',trial#>>'{value,mode}')
                                                IN ('simulation','mock','fixture','sample','dataset')))
 FROM travel_watch_checks c
 CROSS JOIN LATERAL jsonb_array_elements(
   CASE WHEN jsonb_typeof(c.report->'checks')='array' THEN c.report->'checks'
        ELSE '[]'::jsonb END) WITH ORDINALITY AS part(value,position)
 WHERE c.tenant_id=%s AND c.at >= %s AND c.at < %s AND c.at <= %s
   AND part.value->>'category' IN """ + _CATEGORIES + """
 UNION ALL
 SELECT 'input:'||(a.after_value->>'run_id')||':'||part.key, a.at, 'simulation',
        'mock_input', part.key, part.value->>'status', part.value->>'source',
        a.target, a.after_value->>'item_title', 'input', part.value
 FROM admin_audit a
 CROSS JOIN LATERAL jsonb_each(
   CASE WHEN jsonb_typeof(a.after_value#>'{mock_receipt,sources}')='object'
        THEN a.after_value#>'{mock_receipt,sources}' ELSE '{}'::jsonb END) AS part
 WHERE a.tenant_id=%s AND a.action='watch-simulation'
   AND a.after_value->>'run_id' IS NOT NULL
   AND a.after_value->'categories' <> '[]'::jsonb
   AND a.at >= %s AND a.at < %s AND a.at <= %s
   AND part.key IN """ + _CATEGORIES + """
)
"""


def view(conn, tenant: str, *, mode: str = 'actual', date_from: date | None = None,
         date_to: date | None = None, page: int = 1, as_of: datetime | None = None,
         impacts: list[str] | None = None) -> dict:
    now = conn.execute('SELECT clock_timestamp()').fetchone()[0]
    if mode not in ('actual', 'simulation', 'all') or page < 1:
        raise HTTPException(422, '입력 구분과 페이지를 확인해 주세요.')
    if impacts and (len(impacts) > 4 or any(value not in SCOPES for value in impacts)):
        raise HTTPException(422, '일정 영향 조건을 확인해 주세요.')
    selected = list(dict.fromkeys(impacts or []))
    if as_of is not None and as_of.tzinfo is None:
        raise HTTPException(422, '조회 기준 시각에는 시간대가 필요합니다.')
    snapshot = min(as_of, now) if as_of else now
    today = now.astimezone(KST).date()
    first, last = date_from or today-timedelta(days=6), date_to or today
    if first > last or last == date.max:
        raise HTTPException(422, '시작일은 종료일보다 늦을 수 없습니다.')
    start = datetime.combine(first, time.min, KST)
    end = datetime.combine(last+timedelta(days=1), time.min, KST)
    args = (tenant, start, end, snapshot) * 4
    where = '' if mode == 'all' else ' WHERE mode=%s'
    if mode != 'all':
        args += (mode,)
    rules = SafetyRules.from_guardrails()
    if selected:
        # 판정만 필요한 가벼운 자료를 읽는다. 원문 payload는 최종 50건만 읽는다.
        # Python의 기존 안전 판정기를 재사용해 SQL에 별도 재난 규칙을 복제하지 않는다.
        minimal = conn.execute(_RECORDS+"""SELECT id,mode,record_type,category,status,trip_id,stage,
            jsonb_build_object('disruptions',payload->'disruptions','advisories',payload->'advisories',
                '_disruptions',payload->'_disruptions','_advisories',payload->'_advisories',
                'verdict',payload->'verdict','simulation_target',payload->'simulation_target',
                'partial_from',payload->'partial_from',
                'value',jsonb_build_object('partial_from',payload#>'{value,partial_from}'))
            FROM records"""+where, args).fetchall()
        identities = [identity for identity, entry_mode, kind, category, status, trip, stage, payload in minimal
                      if describe(category=category, status=status, record_type=kind, mode=entry_mode,
                                  trip_id=trip, stage=stage, payload=payload, rules=rules)['scope'] in selected]
        total = len(identities)
        where += (' AND ' if where else ' WHERE ') + 'id=ANY(%s)'
        args += (identities,)
    else:
        total = conn.execute(_RECORDS+'SELECT count(*) FROM records'+where, args).fetchone()[0]
    total_pages = max(1, (total+PAGE_SIZE-1)//PAGE_SIZE)
    current = min(page, total_pages)
    rows = conn.execute(_RECORDS+'SELECT * FROM records'+where+
                        ' ORDER BY received_at DESC,id DESC LIMIT %s OFFSET %s',
                        (*args, PAGE_SIZE, (current-1)*PAGE_SIZE)).fetchall()
    records = []
    for identity, at, entry_mode, kind, category, status, source, trip, target, stage, payload in rows:
        payload = dict(payload)
        for field in ('disruptions', 'advisories'):
            if field in payload:
                payload[field] = [v for v in payload[field] or []
                                  if isinstance(v, dict) and v.get('category') == category]
        safe = _safe(payload)
        impact = describe(category=category, status=status, record_type=kind, mode=entry_mode,
                          trip_id=trip, stage=stage, payload=payload, rules=rules)
        impact['summary'] = _safe(impact['summary'])
        records.append(dict(id=identity, received_at=at.isoformat(), mode=entry_mode,
                            record_type=kind, category=category, status=status,
                            source=_safe(source), trip_id=trip, target_title=_safe(target), stage=stage,
                            text=_safe(payload.get('text')), published_at=payload.get('published_at'),
                            regions=[_safe(v) for v in payload.get('regions') or []], payload=safe, impact=impact))
    return dict(records=records, total=total, page=current, page_size=PAGE_SIZE,
                total_pages=total_pages, mode=mode, impacts=selected, date_from=first.isoformat(), date_to=last.isoformat(),
                as_of=snapshot.astimezone(UTC).isoformat())


def targets(due: list, *, start: datetime, end: datetime) -> tuple[list[dict], list[dict]]:
    """시간 범위를 벗어난 시험을 실제 90분 감시 대상으로 표시하지 않는다."""
    actual, simulated = [], []
    for trip, item in due:
        if item.kind not in ('activity', 'dining'):
            continue
        ongoing = item.starts_at <= start < (item.ends_at or item.starts_at)
        upcoming = start <= item.starts_at < end
        trial = bool((item.place or {}).get('_watch_simulation'))
        if not (trial or ongoing or upcoming):
            continue
        row = dict(trip_id=str(trip), item_id=str(item.item_id), title=item.title,
                   starts_at=item.starts_at, ends_at=item.ends_at,
                   reason='simulation' if trial else 'ongoing' if ongoing else 'upcoming')
        (simulated if trial else actual).append(row)
    return actual, simulated
