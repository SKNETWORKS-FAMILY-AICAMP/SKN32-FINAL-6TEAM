"""방문 구간별 무료 휴무 관측과 새벽 구글 조회의 정책 접합."""
from datetime import datetime, timedelta
from uuid import UUID

from app.application import operations_policy as policy
from app.domains.travel_ops.components.team_hooks import activity_ledger, dining_ledger
from app.domains.travel_ops.ports.data_sources.google_places import METER_DETAILS, METER_SEARCH


class PlaceStatus:
    def __init__(self, connection_factory, google=None):
        self.connect, self.google = connection_factory, google

    def lookup(self, *, tenant, customer_id, trip_id, place, start, end, now, context='daytime', kind='dining', scheduled=False):
        end = end or start + timedelta(hours=1)
        resource = f"{place['place_id']}:{start.isoformat()}:{end.isoformat()}"
        if scheduled and context == 'daytime' and not policy.claim_free_check(
                connection_factory=self.connect, tenant=tenant, customer_id=customer_id, trip_id=trip_id,
                resource=resource, now=now):
            return {'status': 'skipped', 'reason': 'check_interval_or_scope'}

        def unknown(source='dining_observation'):
            return policy.Verdict(status='unverifiable', source=source, checked_at=now, valid_until=now)

        #: 활동 원장 판정의 `live_status` 칸(웹 공지로 확인한 임시휴무) — `free()` 가 읽은 것을 아래 「참고」 덧붙임이 다시 쓴다
        seen: dict = {}

        def free():
            if kind == 'activity':
                return live_verdict()
            if kind != 'dining':
                return unknown()
            with self.connect() as conn:
                value = dining_ledger.closure_observation(conn, tenant, place['place_id'], start, end, now)
            return policy.Verdict(**value) if value else unknown()

        def live_verdict():
            """`[2026-10-15]` 활동 → 코어 전달 4번 — 활동 원장 판정의 `live_status` 칸을 읽는다(DB 만 본다 — 웹을 부르지 않는다).

            `llm` 모드이고 판정에 반영(`applied`)된 「닫힘」만 닫힘으로 낸다. `shadow`(정확도를 재는 기간)면 닫힘이어도
            판정은 그대로 모름이고, 값은 결과의 `live_status_reference` 로만 따라간다. 열었다 · 모름 · 아직 안 봄은 닫힘도 열림도 아니다."""
            with self.connect() as conn:
                state = activity_ledger.state(conn, tenant, str(place['place_id']), start, end)
            live = (state or {}).get('live_status')
            if not isinstance(live, dict):
                return unknown('activity_ledger')
            seen['live'] = live
            if live.get('mode') == 'llm' and live.get('applied') is True and live.get('value') == 'closed':
                return policy.Verdict(status='closed', source='activity_live_status', checked_at=_checked_at(live, now),
                                      valid_until=max(end, now + timedelta(seconds=1)))
            return unknown('activity_ledger')

        # 같은 공급 객체를 고객별 상태 보관소로 사용하지 않는다.
        provider = self.google.for_lookup() if self.google is not None else None
        google_id = None
        if provider is not None and context == 'dawn':
            with self.connect() as conn:
                row = conn.execute('SELECT provider_place_id FROM place_provider_ids '
                                   'WHERE tenant_id=%s AND place_id=%s AND provider=%s',
                                   (tenant, place['place_id'], 'google_places')).fetchone()
                google_id = row[0] if row else None

        def paid():
            matched = google_id
            if matched is None:
                found = provider.find_place_id(name=place['name'], latitude=place['latitude'], longitude=place['longitude'])
                if found == 'unmatched':
                    return policy.Verdict(status='unverifiable', source='google_places', checked_at=now,
                                          valid_until=now, reason='place_unmatched')
                if found is None:
                    return unknown('google_places')
                matched, meters = found
                with self.connect() as conn, conn.transaction():
                    conn.execute('INSERT INTO place_provider_ids(tenant_id,place_id,provider,provider_place_id,match_distance_m) '
                                 'VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                                 (tenant, place['place_id'], 'google_places', matched, meters))
            verdict = provider.open_verdict(matched, start=start, end=end)
            if verdict is None or verdict[0] not in ('open', 'closed'):
                return unknown('google_places')
            return policy.Verdict(status=verdict[0], source='google_places', checked_at=now,
                                  valid_until=max(end, now+timedelta(seconds=1)))

        status = policy.select(connection_factory=self.connect, tenant=tenant, customer_id=UUID(str(customer_id)),
                               trip_id=UUID(str(trip_id)), resource=resource,
                               free=free, paid=paid if provider is not None else None,
                               provider_reserve=(lambda: provider.reserve_first(METER_DETAILS if google_id else METER_SEARCH))
                               if provider is not None else None, context=context, now=now)
        live = seen.get('live')
        if live and live.get('mode') != 'llm' and live.get('value') == 'closed':
            # 섀도: 판정에는 넣지 않았다. 감시 결과에는 「참고」로만 싣는다(구분해서 보이게)
            status = {**status, 'live_status_reference': {'value': 'closed', 'mode': live.get('mode'), 'applied': False,
                                                          'checked_at': live.get('checked_at'),
                                                          'citations': live.get('citations') or []}}
        return status

    @staticmethod
    def merge(report, status):
        if status['status'] == 'unverifiable':
            return {**report, 'verdict': 'fatal', 'failed_categories': sorted(set(report.get('failed_categories', [])) | {'place_status'}),
                    'error_code': status['reason'], 'place_status': status, 'diagnostic': status.get('diagnostic')}
        if status['status'] == 'closed':
            causes = list(report.get('disruptions', [])) + [{'category': 'place_status', 'kind': 'closed',
                       'source': status['source'], 'checked_at': status['checked_at']}]
            return {**report, 'verdict': 'fatal' if report.get('verdict') == 'fatal' else 'disrupted',
                    'disruptions': causes, 'place_status': status}
        return {**report, 'place_status': status}

    def merge_case(self, scope, *, place, start, report, now):
        """여행 범위는 모델 인자가 아닌 확인된 사건에서 얻는다."""
        with self.connect() as conn:
            row = conn.execute("SELECT state_json->'subject_ref'->>'id' FROM customer_cases "
                               "WHERE tenant_id=%s AND customer_id=%s AND case_id=%s",
                               (scope.tenant_id, scope.customer_id, scope.case_id)).fetchone()
            if not row or not row[0]:
                return report
            trip_id = UUID(str(row[0]))
            target = conn.execute("SELECT p.kind,EXISTS(SELECT 1 FROM itinerary_items i JOIN trips t "
                                  "ON t.tenant_id=i.tenant_id AND t.trip_id=i.trip_id AND t.latest_version=i.version "
                                  "WHERE i.tenant_id=p.tenant_id AND i.trip_id=%s AND i.place_id=p.place_id "
                                  "AND i.kind='dining' AND i.starts_at=%s),"
                                  "(SELECT i.ends_at FROM itinerary_items i JOIN trips t ON t.tenant_id=i.tenant_id "
                                  "AND t.trip_id=i.trip_id AND t.latest_version=i.version WHERE i.tenant_id=p.tenant_id "
                                  "AND i.trip_id=%s AND i.place_id=p.place_id AND i.kind='dining' AND i.starts_at=%s LIMIT 1) "
                                  "FROM places p WHERE p.tenant_id=%s AND p.place_id=%s "
                                  "AND (p.trip_scope IS NULL OR p.trip_scope=%s)",
                                  (trip_id, start, trip_id, start, scope.tenant_id, place['place_id'], trip_id)).fetchone()
        if not target or (target[0] != 'dining' and not target[1]):
            return report
        status = self.lookup(tenant=scope.tenant_id, customer_id=scope.customer_id, trip_id=trip_id,
                             place=place, start=start, end=target[2], now=now)
        return self.merge(report, status)


def _checked_at(live: dict, now: datetime) -> datetime:
    """저장된 확인 시각(`live_status.checked_at`, ISO 글). 읽을 수 없거나 시각대가 없거나 미래면 지금 — 확인 시각을 지어내 앞당기지 않는다."""
    raw = live.get('checked_at')
    try:
        value = datetime.fromisoformat(raw) if isinstance(raw, str) else raw
    except ValueError:
        return now
    if not isinstance(value, datetime) or value.tzinfo is None or value > now:
        return now
    return value
