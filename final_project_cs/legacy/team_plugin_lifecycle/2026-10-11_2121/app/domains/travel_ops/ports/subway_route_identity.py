"""공식 방면 이름과 정적 인접역ID의 순수 대조. 상하행 이름으로 방향을 추정하지 않는다."""
from __future__ import annotations

import re


def _id(value):
    return isinstance(value, str) and value.isascii() and value.isdigit() and any(c != '0' for c in value)


def valid_service_direction(service):
    """새 이름 증거는 두 종류를 함께 받는다. 부재한 이전 입력은 직접ID 대조만 한다."""
    fields = ('next_station_names', 'terminal_station_names')
    if not any(k in service for k in (*fields, 'boarding_neighbor_ids')):
        return True
    for key in fields:
        names = service.get(key)
        if (not isinstance(names, list) or not names
                or any(not isinstance(x, str) or not x or x != x.strip() for x in names)
                or len(names) != len(set(names))):
            return False
    if 'boarding_neighbor_ids' in service:
        ids = service['boarding_neighbor_ids']
        path = service['path_station_ids']
        if (not isinstance(ids, list) or len(ids) < 2 or not all(_id(x) for x in ids)
                or len(ids) != len(set(ids)) or path[0] in ids or path[1] not in ids):
            return False
    return True


def matched_arrival_service(row, services):
    """종착·종류·정확 방면과 인접 간선을 함께 만족하는 경로 하나를 반환한다."""
    matches = []
    for service in services:
        path = service['path_station_ids']
        if row.get('terminal_station_id') != path[-1] or row.get('train_status') != service['train_status']:
            continue
        if 'next_station_names' not in service or 'route_label' not in row:
            # 이전 통제 입력에서 증거를 만들어 확대하지 않는다.
            if row.get('next_station_id') == path[1]:
                matches.append(service)
            continue
        label = row['route_label']
        parsed = re.fullmatch(r'([^\r\n]+?)행 - ([^\r\n]+?)방면(?: \((급행|ITX|일반|특급)\))?', label) if isinstance(label, str) else None
        if (parsed is None or parsed[1] not in service['terminal_station_names']
                or parsed[2] not in service['next_station_names']
                or (parsed[3] is not None and parsed[3] != row.get('train_status'))):
            continue
        if row.get('next_station_id') == path[1]:
            matches.append(service)
            continue
        ids = (row.get('previous_station_id'), row.get('next_station_id'))
        neighbors = service.get('boarding_neighbor_ids', [])
        if (ids[0] == path[1] and all(_id(x) for x in ids) and ids[0] != ids[1]
                and all(x in neighbors for x in ids)):
            matches.append(service)
    return matches[0] if len(matches) == 1 else None
