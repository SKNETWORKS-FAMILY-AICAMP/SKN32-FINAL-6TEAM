"""같은 교차로에 들어오는 서로 다른 길을 독립 거리 계산과 대조한다."""
from copy import deepcopy
import gzip
import heapq
import json
import math

import pytest

from app.domains.travel_ops.instances.mobility.engine.car import RouterDown
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from app.domains.travel_ops.instances.mobility.engine.turn_restrictions import FILE_NAME, sha256
from .test_graph_router import make_records, xy, nid


def policy(records, rules=()):
    records['turn_restrictions'] = dict(schema_version=1, rules=list(rules), applied_relations=len(rules))
    return records


def arc(records, start, end):
    for idx, edge in enumerate(records['edges']):
        if (edge['u'], edge['v']) == (nid(*start), nid(*end)):
            return idx*2
        if (edge['v'], edge['u']) == (nid(*start), nid(*end)):
            return idx*2+1
    raise AssertionError('간선 미발견')


def rule(records, a, b, c, value='no_left_turn', relation_id=1):
    return dict(relation_id=relation_id, incoming=arc(records, a, b), outgoing=arc(records, b, c), value=value)


def reference(records, start, end):
    # 확장 유향 간선 그래프를 별도로 구성한다. 제품의 permitted/탐색 함수는 부르지 않는다.
    adjacency = {}
    for idx, edge in enumerate(records['edges']):
        if not edge['car']:
            continue
        for rev in (0, 1):
            if (rev == 0 and edge['ow'] < 0) or (rev == 1 and edge['ow'] > 0):
                continue
            u, v = (edge['v'], edge['u']) if rev else (edge['u'], edge['v'])
            adjacency.setdefault(u, []).append((v, idx*2+rev, edge['len']))
    dist, queue = {(nid(*start), -1): 0.0}, [(0.0, nid(*start), -1)]
    while queue:
        cost, node, incoming = heapq.heappop(queue)
        if cost != dist[(node, incoming)]:
            continue
        if node == nid(*end):
            return cost
        for target, outgoing, weight in adjacency.get(node, ()):
            violated = any(row['incoming'] == incoming and
                ((row['value'].startswith('no_') and row['outgoing'] == outgoing) or
                 (row['value'].startswith('only_') and row['outgoing'] != outgoing))
                for row in records['turn_restrictions']['rules'])
            if violated:
                continue
            candidate = cost+weight
            if candidate < dist.get((target, outgoing), math.inf):
                dist[(target, outgoing)] = candidate
                heapq.heappush(queue, (candidate, target, outgoing))


@pytest.mark.parametrize('dijkstra', [False, True])
def test_all_pairs_match_independent_turn_expanded_graph(dijkstra):
    records = make_records()
    rules = [rule(records, (0, 0), (0, 1), (0, 2)),
             rule(records, (1, 0), (1, 1), (2, 1), 'only_right_turn', 2)]
    policy(records, rules)
    router = GraphRouter(records=records)
    router.force_dijkstra = dijkstra
    for a in [(i, j) for i in range(4) for j in range(4)]:
        for b in [(i, j) for i in range(4) for j in range(4)]:
            if a == b:
                continue
            path = router.route(xy(*a), xy(*b), profile='car')['paths'][0]
            assert path['distance'] == pytest.approx(reference(records, a, b), abs=1.5)
            codes = path['turn_restrictions']['arc_codes']
            for inc, out in zip(codes, codes[1:]):
                assert not any(r['incoming'] == inc and ((r['value'].startswith('no_') and r['outgoing'] == out)
                    or (r['value'].startswith('only_') and r['outgoing'] != out)) for r in rules)


@pytest.mark.parametrize('value', ['no_left_turn', 'only_right_turn'])
def test_partial_departure_and_destination_cannot_bypass_turn(value):
    records = make_records()
    target = (1, 1) if value.startswith('only_') else (0, 2)
    policy(records, [rule(records, (0, 0), (0, 1), target, value)])
    router = GraphRouter(records=records)
    a = (xy(0, 0)[0]+0.0005, xy(0, 0)[1])
    b = (xy(0, 1)[0]+0.0005, xy(0, 1)[1])
    path = router.route(a, b, profile='car')['paths'][0]
    assert path['distance'] > 200


def test_free_start_at_junction_and_direct_same_edge_remain_valid():
    records = make_records()
    policy(records, [rule(records, (0, 0), (0, 1), (0, 2))])
    router = GraphRouter(records=records)
    assert router.route(xy(0, 1), xy(0, 2))['paths'][0]['distance'] < 100
    a = (xy(0, 0)[0]+0.0002, xy(0, 0)[1])
    b = (xy(0, 0)[0]+0.0007, xy(0, 0)[1])
    assert router.route(a, b)['paths'][0]['distance'] < 60


def test_sub_meter_partial_arc_keeps_incoming_and_final_turn(monkeypatch):
    records = make_records()
    row = rule(records, (0, 0), (0, 1), (0, 2))
    router = GraphRouter(records=policy(records, [row]))
    # Fix snap candidates to test partial arcs in isolation.
    original = router._snap_many
    def exact_edge(profile, lng, lat):
        expected = row['incoming'] >> 1 if lng < xy(0, 1)[0] else row['outgoing'] >> 1
        return [next(snap for snap in original(profile, lng, lat) if snap.e == expected)]
    monkeypatch.setattr(router, '_snap_many', exact_edge)
    a = (xy(0, 1)[0]-.000005, xy(0, 1)[1])
    b = (xy(0, 1)[0]+.000005, xy(0, 1)[1])
    assert router.route(a, b)['paths'][0]['distance'] > 200


@pytest.mark.parametrize('profile', ['bike', 'foot'])
def test_motorcar_restrictions_do_not_change_other_profiles(profile):
    records = make_records()
    normal = GraphRouter(records=deepcopy(records)).route(xy(0, 0), xy(0, 2), profile=profile)
    policy(records, [rule(records, (0, 0), (0, 1), (0, 2))])
    assert GraphRouter(records=records).route(xy(0, 0), xy(0, 2), profile=profile) == normal


@pytest.mark.parametrize('fault', ['conflict', 'out_of_range', 'wrong_node', 'invalid_value'])
def test_invalid_rules_fail_explicitly(fault):
    records = make_records()
    rows = [rule(records, (0, 0), (0, 1), (0, 2))]
    if fault == 'conflict':
        rows.append(dict(rows[0], relation_id=2, value='only_straight_on'))
    elif fault == 'out_of_range':
        rows[0]['outgoing'] = 9999
    elif fault == 'wrong_node':
        rows[0]['outgoing'] = arc(records, (3, 2), (3, 3))
    else:
        rows[0]['value'] = 'no_entry'
    with pytest.raises(RouterDown, match='turn_restrictions'):
        GraphRouter(records=policy(records, rows)).route(xy(0, 0), xy(0, 2))


def disk_graph(tmp_path):
    records = make_records()
    for name, rows in [('nodes', records['nodes']), ('edges', records['edges'])]:
        with gzip.open(tmp_path/(name+'.jsonl.gz'), 'wt', encoding='utf8') as out:
            for row in rows:
                out.write(json.dumps(row)+'\n')
    data = dict(schema_version=1, applied_relations=1,
        rules=[rule(records, (0, 0), (0, 1), (0, 2))],
        graph_sha256={name: sha256(tmp_path/name) for name in ('nodes.jsonl.gz', 'edges.jsonl.gz')})
    path = tmp_path/FILE_NAME
    path.write_text(json.dumps(data), encoding='utf8')
    return path, data


@pytest.mark.parametrize('fault', ['hash', 'corrupt', 'delete_after_load'])
def test_file_binding_and_removal_do_not_silently_restore_old_paths(tmp_path, fault):
    path, data = disk_graph(tmp_path)
    router = GraphRouter(tmp_path)
    if fault == 'hash':
        data['graph_sha256']['edges.jsonl.gz'] = 'wrong'
        path.write_text(json.dumps(data), encoding='utf8')
    elif fault == 'corrupt':
        path.write_text('{', encoding='utf8')
    else:
        router.route(xy(0, 0), xy(0, 2))
        path.unlink()
    with pytest.raises(RouterDown, match='turn_restrictions'):
        router.route(xy(0, 0), xy(0, 2))
