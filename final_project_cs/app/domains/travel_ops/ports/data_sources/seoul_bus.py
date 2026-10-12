"""서울 버스 실시간 도착정보. 노선 ID와 정류소 순번으로 방향을 고정한다.

출처: https://www.data.go.kr/data/15000314/openapi.do
공식 traTime은 분 단위 여행시간이며 도착 초로 바꾸지 않는다. 제공 메시지에
명시된 분·초만 ETA로 읽고 출발대기·운행종료를 0초로 만들지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import math
import re
from typing import Any
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo

from .base import TravelSource

BASE = 'http://ws.bus.go.kr/api/rest/arrive/getArrInfoByRouteAll'
KST = ZoneInfo('Asia/Seoul')


def nonnegative_int(value):
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def message_eta_seconds(message):
    """도착 메시지의 명시적 시간만 읽는다. 정류소 개수·종료 상태는 시간이 아니다."""
    text = str(message or '').strip()
    match = re.fullmatch(r'(?:(\d+)분\s*)?(?:(\d+)초\s*)?(?:후)?(?:\s*(?:\([^)]*\)|\[[^\]]*\]))?', text)
    if match and (match[1] is not None or match[2] is not None):
        return int(match[1] or 0) * 60 + int(match[2] or 0)
    return None


class SeoulBusArrival(TravelSource):
    name = 'seoul_bus_arrival'

    def __init__(self, *, service_key: str, now=None, cache_ttl_seconds: float = 30, **kwargs: Any):
        super().__init__(**kwargs)
        self._key = unquote(service_key)
        self._now = now or (lambda: datetime.now(KST))
        self.cache_ttl_seconds = cache_ttl_seconds

    def _miss(self, reason: str, detail: str = '') -> None:
        if self._key:
            detail = detail.replace(self._key, '***').replace(quote(self._key, safe=''), '***')
        super()._miss(reason, detail)

    @staticmethod
    def _body_error(payload):
        header = payload.get('msgHeader')
        if isinstance(header, dict):
            code = str(header.get('headerCd', ''))
            if code != '0':
                return f"{code} {header.get('headerMsg', '')}".strip()
        else:
            return TravelSource._body_error(payload) or 'missing_msg_header'
        return TravelSource._body_error(payload)

    def boardable_arrival(self, route_id: str, *, stop_id: str, stop_sequence: int,
                         now: datetime, ready_at: datetime, max_age_seconds: float,
                         max_provider_age_seconds: float,
                         max_provider_clock_ahead_seconds: float) -> dict[str, Any]:
        """정확 승차 위치 조회와 접근 이후 차량 선택. 실패·오래됨도 상태로 전달한다."""
        policy = dict(stop_id=stop_id, stop_sequence=stop_sequence, now=now, ready_at=ready_at,
                      max_age_seconds=max_age_seconds, max_provider_age_seconds=max_provider_age_seconds,
                      max_provider_clock_ahead_seconds=max_provider_clock_ahead_seconds)
        error = _selection_input_error(**policy)
        if error:
            return {'status': 'unavailable', 'reason': error, 'source': self.name,
                    'route_id': str(route_id), 'stop_id': str(stop_id), 'stop_sequence': stop_sequence}
        snapshot = self.arrivals(route_id, stop_id=stop_id, stop_sequence=stop_sequence)
        evaluated = self._now()
        if not isinstance(evaluated, datetime) or evaluated.utcoffset() is None or evaluated < now:
            return {'status': 'unavailable', 'reason': 'invalid_evaluation_clock', 'source': self.name,
                    'route_id': str(route_id), 'stop_id': str(stop_id), 'stop_sequence': stop_sequence,
                    'evaluated_at': str(evaluated)}
        # 응답을 기다리는 동안 아직 출발하지 않았다. 분 올림 뒤 접근 시간을 온전히 유지한다.
        def departure_minute(at):
            floor = at.replace(second=0, microsecond=0)
            return floor + timedelta(minutes=1) if at > floor else floor
        ready = ready_at + (departure_minute(evaluated) - departure_minute(now))
        policy.update(now=evaluated, ready_at=ready)
        result = select_boardable_arrival(snapshot, route_id=route_id, **policy)
        return {**result, 'evaluated_at': evaluated.isoformat(), 'ready_at': ready.isoformat()}

    def arrivals(self, route_id: str, *, stop_id: str | None = None,
                 stop_sequence: int | None = None) -> dict[str, Any] | None:
        if not self._key:
            self._miss('no_service_key')
            return None
        if not str(route_id).isdigit() or stop_sequence is not None and stop_sequence < 1:
            self._miss('invalid_route_or_sequence')
            return None
        payload = self._fetch_json(BASE, {'serviceKey': self._key, 'busRouteId': str(route_id), 'resultType': 'json'})
        if payload is None:
            return None
        body = payload.get('msgBody') or {}
        if not isinstance(body, dict):
            self._miss('unexpected_shape', 'msgBody')
            return None
        rows = body.get('itemList') or []
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            self._miss('unexpected_shape', 'itemList')
            return None
        checked = self._now()
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=KST)
        stops = []
        for row in rows:
            if not isinstance(row, dict) or str(row.get('busRouteId')) != str(route_id):
                continue
            sequence = nonnegative_int(row.get('staOrd'))
            if stop_id is not None and str(row.get('stId')) != str(stop_id):
                continue
            if stop_sequence is not None and sequence != stop_sequence:
                continue
            age = None
            try:
                at = datetime.fromisoformat(str(row.get('mkTm')))
                if at.tzinfo is None:
                    at = at.replace(tzinfo=KST)
                age = int((checked - at).total_seconds())
            except (ValueError, TypeError):
                pass
            buses = []
            for i in (1, 2):
                message = row.get(f'arrmsg{i}')
                eta = message_eta_seconds(message)
                buses.append({
                    'order': i, 'message': message, 'eta_seconds': eta,
                    'eta_basis': 'provider_message' if eta is not None else None,
                    'is_last': {'0': False, '1': True}.get(str(row.get(f'isLast{i}'))),
                    'full': {'0': False, '1': True}.get(str(row.get(f'full{i}'))),
                    'travel_time_minutes': nonnegative_int(row.get(f'traTime{i}')),
                })
            stops.append({'stop_id': str(row.get('stId')), 'stop_name': row.get('stNm'),
                          'stop_sequence': sequence, 'direction': str(row.get('dir') or '').strip(),
                          'route_name': row.get('rtNm'), 'received_at': row.get('mkTm'),
                          'received_age_seconds': age, 'source_clock_ahead': age < 0 if age is not None else None,
                          'buses': buses})
        # 같은 정류소를 두 번 지나는 순환노선은 순번 없이 하나로 고르지 않는다.
        return self.stamp({'kind': 'bus_arrival', 'route_id': str(route_id), 'stops': stops,
                           'ambiguous_stop': stop_id is not None and stop_sequence is None and len(stops) > 1},
                          source=self.name)


def _selection_input_error(*, stop_id, stop_sequence, now, ready_at, max_age_seconds,
                           max_provider_age_seconds, max_provider_clock_ahead_seconds):
    """조회 전에 공통 입력을 검사한다. 잘못된 정책으로 외부 호출 한도를 쓰지 않는다."""
    if (stop_id is None or not str(stop_id) or isinstance(stop_sequence, bool)
            or not isinstance(stop_sequence, int) or stop_sequence < 1):
        return 'invalid_stop_identity'
    if (not isinstance(now, datetime) or now.utcoffset() is None
            or not isinstance(ready_at, datetime) or ready_at.utcoffset() is None):
        return 'timezone_required'
    if (isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, (int, float))
            or not math.isfinite(max_age_seconds) or max_age_seconds <= 0):
        return 'invalid_age_limit'
    if (isinstance(max_provider_age_seconds, bool)
            or not isinstance(max_provider_age_seconds, (int, float))
            or not math.isfinite(max_provider_age_seconds) or max_provider_age_seconds <= 0):
        return 'invalid_provider_age_limit'
    if (isinstance(max_provider_clock_ahead_seconds, bool)
            or not isinstance(max_provider_clock_ahead_seconds, (int, float))
            or not math.isfinite(max_provider_clock_ahead_seconds)
            or max_provider_clock_ahead_seconds < 0):
        return 'invalid_provider_clock_limit'
    if ready_at < now:
        return 'invalid_ready_at'
    return None


def select_boardable_arrival(snapshot, *, route_id, stop_id, stop_sequence, now, ready_at,
                            max_age_seconds, max_provider_age_seconds,
                            max_provider_clock_ahead_seconds):
    """정류장 접근 이후 탈 수 있는 예상 차량. 확인값의 나이와 실제 도착 오차는 다르다."""
    base = {'source': snapshot.get('source') if isinstance(snapshot, dict) else None,
            'route_id': str(route_id), 'stop_id': str(stop_id), 'stop_sequence': stop_sequence}

    def fail(status, reason):
        return {**base, 'status': status, 'reason': reason}

    if not isinstance(snapshot, dict) or snapshot.get('kind') != 'bus_arrival':
        return fail('unavailable', 'invalid_snapshot')
    if not base['source'] or str(snapshot.get('route_id')) != str(route_id):
        return fail('unavailable', 'source_or_route_mismatch')
    error = _selection_input_error(
        stop_id=stop_id, stop_sequence=stop_sequence, now=now, ready_at=ready_at,
        max_age_seconds=max_age_seconds, max_provider_age_seconds=max_provider_age_seconds,
        max_provider_clock_ahead_seconds=max_provider_clock_ahead_seconds)
    if error:
        return fail('unavailable', error)
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
    stops = snapshot.get('stops')
    if not isinstance(stops, list):
        return fail('unavailable', 'invalid_stops')
    matches = [st for st in stops if isinstance(st, dict) and str(st.get('stop_id')) == str(stop_id)
               and st.get('stop_sequence') == stop_sequence]
    if len(matches) != 1:
        return fail('unavailable', 'stop_not_unique')
    stop = matches[0]
    base.update(provider_received_at=stop.get('received_at'), direction=stop.get('direction'))
    try:
        provider_at = datetime.fromisoformat(str(stop.get('received_at')))
        # 서울 API mkTm은 시간대 없는 KST 문자열이다. 원 문자열은 위 칸에 보존한다.
        if provider_at.utcoffset() is None:
            provider_at = provider_at.replace(tzinfo=KST)
    except (TypeError, ValueError):
        return fail('unavailable', 'invalid_provider_received_at')
    provider_age = (now - provider_at).total_seconds()
    base.update(provider_received_at_normalized=provider_at.isoformat(),
                provider_age_seconds=provider_age,
                max_provider_age_seconds=max_provider_age_seconds,
                max_provider_clock_ahead_seconds=max_provider_clock_ahead_seconds)
    if provider_age < -max_provider_clock_ahead_seconds:
        return fail('unavailable', 'provider_clock_in_future')
    if provider_age > max_provider_age_seconds:
        return fail('stale', 'provider_refresh_required')
    # 공급 자료의 나이는 신선도만 판정한다. ETA 기준으로 검증되지 않은 mkTm을
    # confirmed_at의 cache경과와 함께 차감하면 같은 시간이 두 번 빠질 수 있다.
    buses = stop.get('buses')
    if not isinstance(buses, list):
        return fail('unavailable', 'invalid_buses')
    ready_seconds = max(0.0, (ready_at - now).total_seconds())
    choices = []
    excluded = []
    for bus in buses:
        if not isinstance(bus, dict):
            continue
        eta = bus.get('eta_seconds')
        reason = None
        if (isinstance(eta, bool) or not isinstance(eta, (int, float))
                or not math.isfinite(eta) or eta < 0):
            reason = 'no_numeric_eta'
        elif bus.get('eta_basis') != 'provider_message':
            reason = 'unverified_eta_basis'
        elif bus.get('full') is True:
            reason = 'full'
        else:
            remaining = eta - elapsed
            if remaining < ready_seconds:
                reason = 'arrives_before_ready'
            else:
                choices.append((remaining, bus))
        if reason:
            excluded.append({'order': bus.get('order'), 'reason': reason})
    base['excluded'] = excluded
    if not choices:
        return fail('no_boardable_prediction', 'no_vehicle_after_ready')
    remaining, bus = min(choices, key=lambda choice: choice[0])
    return {**base, 'status': 'predicted', 'bus_order': bus.get('order'),
            'arrival_at': (now + timedelta(seconds=remaining)).isoformat(),
            'remaining_seconds': remaining, 'wait_after_access_seconds': remaining - ready_seconds,
            'capacity_known': bus.get('full') is False, 'is_last': bus.get('is_last')}
