"""공식 식별정보와 검증된 일반열차 경로로 현재 승차 예측을 고른다.

호출자가 공급하는 경로는 정적 노선 연결로 확인한 역ID 순서다. 급행 정차역과
순환선 방향의 별도 계약은 아직 지원하지 않는다. recptnDt가 ETA 기준이며,
HTTP 보관 시간은 신선도만 판정한다(서울 OA-12764 이용 안내).
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
import math
from zoneinfo import ZoneInfo

from app.domains.travel_ops.instances._shared.subway_train_identity import valid_train_number
from app.domains.travel_ops.instances._shared.subway_route_identity import matched_arrival_service, valid_service_direction

KST = ZoneInfo('Asia/Seoul')
ARRIVAL_STATES = {'0', '1', '3', '4', '5', '99'}
AT_STATION_STATES = {'0', '1'}


def _id(value):
    return isinstance(value, str) and value.isascii() and value.isdigit() and any(c != '0' for c in value)


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def selection_input_error(*, line_id, station_id, target_station_id, allowed_services,
                          now, ready_at, max_age_seconds, max_provider_age_seconds,
                          max_provider_clock_ahead_seconds):
    if (not all(_id(x) for x in (line_id, station_id, target_station_id))
            or station_id == target_station_id):
        return 'boarding_identity_invalid'
    if (not isinstance(now, datetime) or now.utcoffset() is None
            or not isinstance(ready_at, datetime) or ready_at.utcoffset() is None):
        return 'timezone_required'
    if ready_at < now:
        return 'invalid_ready_at'
    for value, allow_zero in ((max_age_seconds, False), (max_provider_age_seconds, False),
                              (max_provider_clock_ahead_seconds, True)):
        if not _finite_number(value) or value < 0 or (value == 0 and not allow_zero):
            return 'invalid_freshness_policy'
    if not isinstance(allowed_services, list) or not allowed_services:
        return 'service_path_invalid'
    identities = set()
    for service in allowed_services:
        if not isinstance(service, dict) or service.get('train_status') != '일반':
            return 'service_path_invalid'
        path = service.get('path_station_ids')
        if (not isinstance(path, list) or len(path) < 2 or not all(_id(x) for x in path)
                or len(set(path)) != len(path) or path[0] != station_id or target_station_id not in path[1:]):
            return 'service_path_invalid'
        if not valid_service_direction(service):
            return 'service_path_invalid'
        identity = (path[1], path[-1], service['train_status'])
        if identity in identities:
            return 'service_path_invalid'
        identities.add(identity)
    return None


def select_boardable_arrival(snapshot, *, line_id, station_id, target_station_id, allowed_services,
                            now, ready_at, max_age_seconds, max_provider_age_seconds,
                            max_provider_clock_ahead_seconds):
    """현재 역 접근 이후의 일반열차 하나. 예상 도착이며 실제 탑승 보장이 아니다."""
    base = {'source': snapshot.get('source') if isinstance(snapshot, dict) else None,
            'line_id': line_id, 'station_id': station_id, 'target_station_id': target_station_id}

    def fail(status, reason):
        return {**base, 'status': status, 'reason': reason}

    error = selection_input_error(line_id=line_id, station_id=station_id, target_station_id=target_station_id,
        allowed_services=allowed_services, now=now, ready_at=ready_at, max_age_seconds=max_age_seconds,
        max_provider_age_seconds=max_provider_age_seconds,
        max_provider_clock_ahead_seconds=max_provider_clock_ahead_seconds)
    if error:
        return fail('unavailable', error)
    if not isinstance(snapshot, dict) or snapshot.get('kind') != 'subway_arrival' or not base['source']:
        return fail('unavailable', 'invalid_snapshot')
    try:
        confirmed = datetime.fromisoformat(str(snapshot.get('confirmed_at')))
        if confirmed.utcoffset() is None:
            return fail('unavailable', 'timezone_required')
    except (TypeError, ValueError):
        return fail('unavailable', 'invalid_confirmed_at')
    elapsed = (now - confirmed).total_seconds()
    base.update(confirmed_at=confirmed.isoformat(), observation_age_seconds=elapsed,
                ready_at=ready_at.isoformat())
    if elapsed < 0:
        return fail('unavailable', 'confirmation_in_future')
    if elapsed >= max_age_seconds:
        return fail('stale', 'refresh_required')
    rows = snapshot.get('trains')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return fail('unavailable', 'invalid_trains')
    if 'coverage_complete' in snapshot and snapshot['coverage_complete'] is not True:
        # 부분 응답의 후보나 빈 목록은 전체에서 가장 이른 열차/무운행을 증명하지 않는다.
        return fail('unavailable', 'incomplete_arrivals' if snapshot['coverage_complete'] is False
                    else 'arrival_total_unknown')
    counts = Counter(row.get('train_number') for row in rows
                     if row.get('line_id') == line_id and row.get('station_id') == station_id
                     and valid_train_number(row.get('train_number')))
    choices, excluded = [], []
    for row in rows:
        reason = None
        service = matched_arrival_service(row, allowed_services)
        code_value = row.get('arrival_code')
        code = str(code_value) if isinstance(code_value, (str, int)) and not isinstance(code_value, bool) else None
        eta = row.get('eta_seconds')
        if row.get('line_id') != line_id or row.get('station_id') != station_id:
            reason = 'boarding_identity_mismatch'
        elif service is None:
            reason = 'service_path_mismatch'
        elif not valid_train_number(row.get('train_number')):
            reason = 'train_identity_missing'
        elif counts[row['train_number']] != 1:
            reason = 'duplicate_train_identity'
        elif code not in ARRIVAL_STATES:
            reason = 'departed_or_unknown_state'
        elif (isinstance(eta, bool) or not isinstance(eta, int) or eta < 0
              or row.get('eta_status') != 'valid'):
            reason = 'no_numeric_eta'
        elif eta == 0 and code not in AT_STATION_STATES:
            reason = 'zero_eta_without_arrival_state'
        else:
            try:
                received = datetime.fromisoformat(str(row.get('received_at')))
                if received.utcoffset() is None:
                    received = received.replace(tzinfo=KST)
            except (TypeError, ValueError):
                reason = 'invalid_provider_received_at'
            if reason is None:
                provider_age = (now - received).total_seconds()
                if provider_age < -max_provider_clock_ahead_seconds:
                    reason = 'provider_clock_in_future'
                elif provider_age > max_provider_age_seconds:
                    reason = 'provider_refresh_required'
                else:
                    try:
                        arrival = received + timedelta(seconds=eta)
                    except (OverflowError, ValueError):
                        reason = 'invalid_arrival_time'
                    if reason is None:
                        if arrival < ready_at:
                            reason = 'arrives_before_ready'
                        else:
                            choices.append((arrival, row, service, received, provider_age))
        if reason is not None:
            excluded.append({'train_number': row.get('train_number'), 'reason': reason})
    base['excluded'] = excluded
    if not choices:
        return fail('no_boardable_prediction', 'no_vehicle_after_ready')
    arrival, row, service, received, provider_age = min(choices, key=lambda x: (x[0], x[1]['train_number']))
    direction = ({'direction_basis': 'route_label_and_neighbor_ids',
                  'provider_next_station_id': row.get('next_station_id'),
                  'provider_previous_station_id': row.get('previous_station_id'),
                  'route_label': row['route_label']}
                 if 'next_station_names' in service and 'route_label' in row else {})
    return {**base, **direction, 'status': 'predicted', 'train_number': row['train_number'],
            'next_station_id': service['path_station_ids'][1], 'terminal_station_id': row['terminal_station_id'],
            'train_status': row['train_status'], 'path_station_ids': deepcopy(service['path_station_ids']),
            'arrival_at': arrival.isoformat(), 'remaining_seconds': (arrival - now).total_seconds(),
            'wait_after_access_seconds': (arrival - ready_at).total_seconds(),
            'provider_received_at': row.get('received_at'),
            'provider_received_at_normalized': received.isoformat(), 'provider_age_seconds': provider_age,
            'eta_basis': 'provider_generation_time', 'claim': '접근 이후 일반열차 도착 예측; 실제 탑승 관측 아님'}
