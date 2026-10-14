"""일반 비순환 첫 승차의 정적 경로를 공급자 ID와 연결한다. 넓은 역명 별칭은 추정하지 않는다."""
from __future__ import annotations

from app.domains.travel_ops.ports.subway_train_identity import valid_train_number
from app.domains.travel_ops.ports.subway_route_identity import matched_arrival_service

from .subway_identity import boarding_identity


def boarding_services(runtime, leg):
    identity = boarding_identity(runtime, [leg])
    if not identity or identity.get('status') != 'matched':
        return identity or {'status': 'unavailable', 'reason': 'station_identity_unmapped'}, []
    lo = runtime._v.lo
    line, origin, target = leg['line'], leg['from'], leg['to']
    if lo is None or line not in lo.doc['lines']:
        return {'status': 'unavailable', 'reason': 'line_order_missing'}, []
    if lo.is_loop(line):
        return {'status': 'unavailable', 'reason': 'loop_realtime_not_supported'}, []
    neighbor_names = {e['b'] if e['a'] == origin else e['a']
                      for e in lo.doc['lines'][line]['edges'] if origin in (e['a'], e['b'])}
    neighbor_rows = [runtime.subway_stations.lookup(line, name) for name in sorted(neighbor_names)]
    neighbors = ([r['station_id'] for r in neighbor_rows]
                 if len(neighbor_rows) >= 2 and all(r is not None for r in neighbor_rows) else [])
    services = {}
    for terminal in lo.stations(line):
        verdict = lo.passes(line, origin, terminal, target)
        if verdict.value is not True or not verdict.path or len(verdict.path) < 2:
            continue
        rows = [runtime.subway_stations.lookup(line, station) for station in verdict.path]
        if any(row is None for row in rows):
            continue
        ids = [row['station_id'] for row in rows]
        if len(ids) != len(set(ids)):
            continue
        key = (ids[1], ids[-1], '일반')
        candidate = {'train_status': '일반', 'path_station_ids': ids,
                     'path_stations': list(verdict.path), 'terminal': terminal,
                     'next_station_names': sorted({verdict.path[1], rows[1]['station'], rows[1]['query_station']}),
                     'terminal_station_names': sorted({terminal, rows[-1]['station'], rows[-1]['query_station']})}
        if neighbors:
            candidate['boarding_neighbor_ids'] = sorted(neighbors)
        # 같은 ID 조합이 서로 다른 경로라면 방향을 결정하지 않는다.
        if key in services and services[key] != candidate:
            return {'status': 'unavailable', 'reason': 'service_path_ambiguous'}, []
        services[key] = candidate
    if not services:
        return {'status': 'unavailable', 'reason': 'service_identity_unmapped'}, []
    return identity, list(services.values())


def matched_service(observation, identity, services):
    """콜백의 ID·열차 종류·경로를 조회에 사용한 정적 조합과 다시 대조한다."""
    if any(observation.get(k) != identity.get(k) for k in ('line_id', 'station_id', 'target_station_id')):
        return None
    train = observation.get('train_number')
    if (not valid_train_number(train) or observation.get('train_status') != '일반'
            or observation.get('eta_basis') != 'provider_generation_time'):
        return None
    matches = [s for s in services
               if observation.get('next_station_id') == s['path_station_ids'][1]
               and observation.get('terminal_station_id') == s['path_station_ids'][-1]
               and observation.get('path_station_ids') == s['path_station_ids']]
    if any(k in observation for k in ('direction_basis', 'provider_next_station_id',
                                      'provider_previous_station_id', 'route_label')):
        if (observation.get('direction_basis') != 'route_label_and_neighbor_ids'
                or not all(k in observation for k in ('provider_next_station_id',
                                                      'provider_previous_station_id', 'route_label'))):
            return None
        raw = dict(observation, next_station_id=observation.get('provider_next_station_id'),
                   previous_station_id=observation.get('provider_previous_station_id'))
        verified = matched_arrival_service(raw, services)
        return verified if len(matches) == 1 and verified == matches[0] else None
    return matches[0] if len(matches) == 1 else None
