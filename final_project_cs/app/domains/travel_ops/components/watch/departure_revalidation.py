"""현재 방문 장소를 이동 팀의 출발 재검증에 전달한다. 팀 구현·외부 HTTP를 알지 않는다."""
from __future__ import annotations

import logging
import math

from app.domains.travel_ops.components.team_hooks import legs
from app.domains.travel_ops.components.itinerary.itinerary_checks import origin_of


def _place(item):
    place = item.place
    if not isinstance(place, dict):
        return None
    try:
        lat, lon = place['latitude'], place['longitude']
        if isinstance(lat, bool) or isinstance(lon, bool):
            return None
        lat, lon = float(lat), float(lon)
        if not math.isfinite(lat) or not math.isfinite(lon):
            return None
        return {'key': str(place.get('place_id') or item.place_id), 'name': place.get('name'),
                'lat': lat, 'lon': lon}
    except (KeyError, TypeError, ValueError):
        return None


def build_observer(*, bus_arrival, subway_arrival=None, basis_validator=None):
    """TripReminders가 호출하는 공통 콜백을 만든다. 만들 때는 조회하지 않는다."""
    def observed(move, items, *, planned, now, events, trip=None):
        ordered = sorted(items, key=lambda item: item.seq)
        before = [item for item in ordered if item.seq < move.seq and item.kind != 'mobility']
        after = [item for item in ordered if item.seq > move.seq and item.kind != 'mobility']
        if not before or not after:
            return {'status': 'needs_replan', 'reason': 'adjacent_visit_missing'}
        # `[2026-10-13]` 아침 「숙소 → 첫 일정」 이동은 그날 묵는 숙소에서 출발한다(순서상 앞은 전날 마지막 일정)
        start = origin_of(ordered, move) if (move.detail or {}).get("from_stay") else before[-1]
        origin, destination = (_place(start) if start is not None else None), _place(after[0])
        if origin is None or destination is None:
            return {'status': 'needs_replan', 'reason': 'current_place_missing'}
        try:
            result = legs.observe_departure(move.detail.get('departure_context'), planned.get('id'),
                now=now, deadline=after[0].starts_at, origin=origin, destination=destination,
                bus_arrival=bus_arrival, subway_arrival=subway_arrival, events=events, trip=trip)
        except Exception as exc:  # noqa: BLE001 — 치명 상태를 보고하고 낡은 안내는 발행하지 않는다
            logging.getLogger(__name__).error('출발 재검증 실패: %s', type(exc).__name__)
            return {'status': 'fatal', 'reason': 'departure_revalidation_failed',
                    'exception_type': type(exc).__name__}
        return result if isinstance(result, dict) else {'status': 'fatal', 'reason': 'mobility_observer_unregistered'}
    if basis_validator is not None:
        if not callable(basis_validator):
            raise ValueError('출발 입력 판 검사 콜백이 함수가 아니다')
        observed.validate_basis = basis_validator
    return observed
