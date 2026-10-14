"""선택한 승하차 식별값을 정류장·역 경유선으로 옮긴다. 도로·선로 형상은 추정하지 않는다."""
from __future__ import annotations

import math


def _point(row):
    if not isinstance(row, dict):
        return None
    lng, lat = row.get('lng'), row.get('lat')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in (lng, lat)):
        return None
    try:
        if not math.isfinite(lng) or not math.isfinite(lat) or not -180 <= lng <= 180 or not -90 <= lat <= 90:
            return None
        return [float(lng), float(lat)]
    except OverflowError:
        return None


def selected_option(context, planned):
    """None은 옛 문맥 부재, 그 밖의 손상 문맥은 오류다. 다른 옵션으로 대신하지 않는다."""
    if context is None:
        return None, None
    options = context.get('options') if isinstance(context, dict) else None
    option = options.get(planned) if isinstance(options, dict) else None
    if (not isinstance(context, dict) or type(context.get('schema_version')) is not int or context['schema_version'] != 1
            or not isinstance(option, dict) or option.get('option_id') != planned
            or not isinstance(option.get('legs'), list) or not option['legs']
            or any(not isinstance(leg, dict) for leg in option['legs'])):
        return None, '저장된 선택 경로 문맥이 불일치하여 직선으로 잇는다'
    return option, None


def bus_segment(bus, leg):
    """서울 가공자료의 연속 순번·승하차ID가 모두 일치할 때만 전체 정류장을 잇는다."""
    from .engine.bus_identity import IDENTITY_KEYS, route_for_leg, segment_for_leg
    if bus is None or any(key not in leg for key in IDENTITY_KEYS) or any(not leg.get(k) for k in ('route', 'from', 'to')):
        return None, '버스 정류장 식별정보 또는 자료가 불일치한다'
    route = route_for_leg(bus, leg)
    segment = segment_for_leg(bus, route, leg) if route is not None else None
    if segment is None:
        return None, '버스 노선·승하차 정류장 식별정보가 불일치한다'
    start, end, count = segment
    rows = [row for row in bus.stops.get(route.route_id, ())
            if isinstance(row.get('seq'), int) and not isinstance(row['seq'], bool)
            and start['seq'] <= row['seq'] <= end['seq']]
    rows.sort(key=lambda row: row['seq'])
    if (len(rows) != count + 1 or any(row['seq'] != start['seq'] + i
            or str(row.get('route_id')) != str(route.route_id) for i, row in enumerate(rows))):
        return None, '버스 정류장 순번 자료가 누락 또는 중복되어 완전한 경유선을 못 만든다'
    coords = [_point(row) for row in rows]
    if any(point is None for point in coords) or any(row.get('station_id') is None for row in rows):
        return None, '버스 정류장 좌표가 누락 또는 유효하지 않아 완전한 경유선을 못 만든다'
    ride = {'mode': 'bus', 'line': route.route_nm, 'route_id': route.route_id,
            'from': leg['from'], 'to': leg['to'], 'from_sequence': start['seq'], 'to_sequence': end['seq'],
            'from_stop_id': str(start['station_id']), 'to_stop_id': str(end['station_id']),
            'direction': start.get('direction'), 'stations': [row['station_nm'] for row in rows],
            'stop_ids': [str(row.get('station_id')) for row in rows],
            'sequences': [row['seq'] for row in rows], 'count': len(rows), 'filled': len(rows) > 2,
            'source_id': start.get('source_id'), 'fetched_at': start.get('fetched_at')}
    return (coords, ride, '선택 노선의 정류장을 순서대로 잇는 근사선이며 실제 도로 형상이 아님'), None


def rail_segment(sc, lo, leg, saved_path, ride_names, saved_service=None):
    from .wiring import engine_line
    from .engine.options import line_name
    if sc is None or any(not isinstance(leg.get(key), str) or not leg[key] for key in ('line', 'from', 'to')):
        return None, '지하철 승하차 역 문맥이 불일치한다'
    line, start, end = line_name(leg['line']), leg['from'], leg['to']
    path = saved_path if saved_path is not None else leg.get('station_path')
    if path is not None:
        if (not isinstance(path, list) or len(path) < 2 or path[0] != start or path[-1] != end
                or any(not isinstance(name, str) or not name for name in path)):
            return None, '저장된 지하철 경유 방향과 승하차 역이 불일치한다'
        note = '선택한 편성의 경유 방향을 보존한 역 근사선(실제 선로 곡선이 아님)'
    else:
        try:
            loop = lo is not None and lo.is_loop(engine_line(line))
        except (AttributeError, KeyError, TypeError):
            loop = True
        if loop:
            path = [start, end]
            note = '선택 편성의 순환 방향 근거가 없어 승하차 역만 잇는다(실제 선로 곡선이 아님)'
        else:
            path, _warning = ride_names(lo, line, start, end)
            note = '탄 역 사이의 역 순서를 잇는 근사선(실제 선로 곡선이 아님)'
    coords = [_point(sc.get(engine_line(line), name)) for name in path]
    if any(point is None for point in coords):
        return None, '선택 경로의 지하철 역 좌표가 누락 또는 유효하지 않다'
    ride = {'mode': 'subway', 'line': line, 'from': start, 'to': end,
            'stations': list(path), 'count': len(path), 'filled': len(path) > 2,
            'direction_preserved': saved_path is not None or leg.get('station_path') is not None}
    if saved_service in ('express', 'local'):
        ride['service'] = saved_service
    return (coords, ride, note), None


def segments(option, *, bus, sc, lo, ride_names):
    paths = option.get('station_paths')
    if paths is not None and (not isinstance(paths, list) or len(paths) != len(option['legs'])):
        return None, '저장된 지하철 경유 방향 문맥의 개수가 불일치한다'
    services = option.get('station_services')
    if services is not None and (not isinstance(services, list) or len(services) != len(option['legs'])
                                 or any(service not in (None, 'local', 'express') for service in services)):
        return None, '저장된 지하철 일반·급행 문맥이 불일치한다'
    out = []
    for index, leg in enumerate(option['legs']):
        mode = leg.get('mode', 'subway')
        if mode == 'bus':
            segment, why = bus_segment(bus, leg)
        elif mode == 'subway':
            segment, why = rail_segment(sc, lo, leg, paths[index] if paths else None, ride_names,
                                       services[index] if services else None)
        else:
            return None, '저장된 경로에 지원하지 않는 구간이 있어 직선으로 잇는다'
        if segment is None:
            return None, why
        out.append(segment)
    return out, None
