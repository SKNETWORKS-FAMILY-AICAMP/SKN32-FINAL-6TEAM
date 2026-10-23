"""좌표 후보에서 고른 버스 원문 행을 시각·환승 판정까지 유지한다."""
from __future__ import annotations


IDENTITY_KEYS = ('route_id', 'from_sequence', 'to_sequence', 'from_stop_id', 'to_stop_id')


def has_identity(leg):
    return any(key in leg for key in IDENTITY_KEYS)


def bus_leg(route, board, alight):
    """선택한 행의 순번을 담는다. 이름은 표시용이며 다른 행을 찾는 힌트가 아니다."""
    leg = {'mode': 'bus', 'route': route.route_nm,
           'from': board['station_nm'], 'to': alight['station_nm'],
           'route_id': route.route_id, 'from_sequence': board['seq'], 'to_sequence': alight['seq']}
    for side, row in (('from', board), ('to', alight)):
        if row.get('station_id') is not None:
            leg[f'{side}_stop_id'] = str(row['station_id'])
    return leg


def route_for_leg(bus, leg):
    if has_identity(leg):
        # 표시 이름이 같은 다른 노선으로 바꾸지 않는다.
        return getattr(bus, 'by_id', {}).get(str(leg.get('route_id')))
    return bus.route(str(leg['route']))


def _sequence(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdecimal() and int(value) > 0:
        return int(value)
    return None


def segment_for_leg(bus, route, leg):
    """식별값이 어긋나면 None. 옛 이름만의 입력에 한해 기존 탐색을 사용한다."""
    if not has_identity(leg):
        return bus.segment(route.route_id, leg['from'], leg['to'])
    if str(leg.get('route_id')) != str(route.route_id) or str(leg['route']) != str(route.route_nm):
        return None
    start, end = _sequence(leg.get('from_sequence')), _sequence(leg.get('to_sequence'))
    if start is None or end is None or start >= end:
        return None
    rows = bus.stops.get(route.route_id, ())
    selected = []
    for side, seq in (('from', start), ('to', end)):
        matches = [row for row in rows if row.get('seq') == seq and row.get('station_nm') == leg[side]
                   and str(row.get('route_id')) == str(route.route_id)]
        if len(matches) != 1:
            return None
        row = matches[0]
        key = f'{side}_stop_id'
        if key in leg and (leg[key] is None or str(row.get('station_id')) != str(leg[key])):
            return None
        selected.append(row)
    return selected[0], selected[1], end - start
