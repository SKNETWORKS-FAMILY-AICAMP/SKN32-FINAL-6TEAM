"""운영기관 구간별 추가운임. 일반 거리 운임과 분리하며 구간을 중복 부과하지 않는다."""


def surcharge(v, legs):
    policy = v.R.get('fare', {}).get('subway', {}).get('special_lines', {})
    totals = 0
    used = {}
    for leg in legs:
        line = leg.get('line')
        if line == '신분당선' and line not in policy:
            return None
        if line not in policy:
            continue
        config = policy[line]
        stations = config['stations']
        try:
            start, end = sorted((stations.index(leg['from']), stations.index(leg['to'])))
        except (ValueError, KeyError):
            return None
        if start == end:
            continue
        zones = used.setdefault(line, set())
        covered = set()
        for zone in config['zones']:
            a, b = stations.index(zone['from']), stations.index(zone['to'])
            intersection = set(range(start, end)) & set(range(a, b))
            if intersection:
                zones.add(zone['id'])
                covered.update(intersection)
        if covered != set(range(start, end)):
            return None
    for line, zones in used.items():
        value = policy[line]['surcharges'].get('+'.join(sorted(zones)))
        if value is None:
            return None
        totals += value
    return totals


def confirmed_distances(v):
    return {(line, row['a'], row['b']): row['distance_m']
            for line, config in v.R.get('fare', {}).get('subway', {}).get('special_lines', {}).items()
            for row in config['confirmed_edges']}


def published_od_fare(v, legs, early):
    """일반열차만 연결한 단방향 여정의 공식 성인 카드 OD 운임.

    구간을 나눈 입력에도 처음·마지막 역 한 쌍만 부과한다. 표 밖 역,
    역주행·불연속·다른 노선과의 혼합은 표의 단일 여정으로 간주하지 않는다.
    조조 경계의 태그 시각을 모르면 확정액을 만들지 않는다.
    """
    if not legs or early is None:
        return None
    policy = v.R.get('fare', {}).get('subway', {}).get('published_od_fares', {})
    line = legs[0].get('line')
    config = policy.get(line)
    if config is None:
        return None
    stations = config['stations']
    previous = None
    direction = None
    for leg in legs:
        if (leg.get('line') != line or leg.get('mode', 'subway') != 'subway'
                or leg.get('express') or leg.get('service_type') in ('express', '직통')):
            return None
        try:
            start, end = stations.index(leg['from']), stations.index(leg['to'])
        except (KeyError, ValueError):
            return None
        step = 1 if end > start else -1
        if start == end or (previous is not None and previous != start):
            return None
        if direction is not None and step != direction:
            return None
        direction, previous = step, end
    a, b = legs[0]['from'], legs[-1]['to']
    for row in config['fares']:
        if {row['a'], row['b']} == {a, b}:
            return row['won'] - (config['early_bird_discount_won'] if early else 0)
    return None
