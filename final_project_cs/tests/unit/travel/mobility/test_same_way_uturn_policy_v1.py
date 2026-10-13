"""되돌아가기 금지의 해석과 생성→실제 차량 탐색 연결을 검사한다."""
from copy import deepcopy
import hashlib
import json

import pytest

from scripts.mobility.build_car_turn_policy_v1 import build, unique_same_way_uturn
from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
from .test_graph_router import make_records, xy
from .test_car_turn_restrictions_v1 import arc, policy, reference, rule


def row():
    return {'relation_id': 12, 'members': [
        {'type': 'w', 'role': 'from', 'ref': 10}, {'type': 'w', 'role': 'to', 'ref': 10},
        {'type': 'n', 'role': 'via', 'ref': 100}], 'graph_audit': {
        'effective_motorcar_value_candidate': 'no_u_turn',
        'unsupported_or_unresolved_reasons': ['same_way_turn_requires_arc_geometry_semantics'],
        'conditional_tags': {}, 'except_modes': [], 'via_form': 'node',
        'incoming_arc_codes': [8], 'outgoing_arc_codes': [9]}}


@pytest.mark.parametrize('incoming', [8, 9])
def test_unambiguous_reverse_in_both_edge_orientations(incoming):
    r = row()
    r['graph_audit'].update(incoming_arc_codes=[incoming], outgoing_arc_codes=[incoming ^ 1])
    assert unique_same_way_uturn(r)


@pytest.mark.parametrize('change', ['two_directions', 'straight', 'conditional', 'exception',
    'other_reason', 'different_way', 'via_way', 'only_u_turn', 'boolean_arc'])
def test_unsupported_relations_remain_excluded(change):
    r = row()
    a = r['graph_audit']
    if change == 'two_directions': a.update(incoming_arc_codes=[8, 11], outgoing_arc_codes=[9, 10])
    elif change == 'straight': a['outgoing_arc_codes'] = [10]
    elif change == 'conditional': a['conditional_tags'] = {'restriction:conditional': 'no_u_turn @ (Mo-Fr)'}
    elif change == 'exception': a['except_modes'] = ['bus']
    elif change == 'other_reason': a['unsupported_or_unresolved_reasons'].append('missing_graph_ways')
    elif change == 'different_way': r['members'][1]['ref'] = 11
    elif change == 'via_way': r['members'][2]['type'] = 'w'
    elif change == 'only_u_turn': a['effective_motorcar_value_candidate'] = 'only_u_turn'
    elif change == 'boolean_arc': a.update(incoming_arc_codes=[True], outgoing_arc_codes=[0])
    assert not unique_same_way_uturn(r)


def fixture(tmp_path):
    audit, graph = tmp_path/'audit', tmp_path/'graph'
    audit.mkdir(); graph.mkdir()
    for name in ('nodes.jsonl.gz', 'edges.jsonl.gz'): (graph/name).write_bytes(b'bound-test-input')
    regular = row()
    regular.update(relation_id=1)
    regular['graph_audit'].update(candidate_for_static_simple_motorcar=True,
        unsupported_or_unresolved_reasons=[], effective_motorcar_value_candidate='no_left_turn')
    files = {'static-motorcar-candidates.jsonl': [regular], 'restrictions-graph-audit.jsonl': [regular, row()]}
    for name, rows in files.items():
        (audit/name).write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf8')
    def hashed(p): return {'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    (audit/'manifest.json').write_text(json.dumps({'inputs': [hashed(p) for p in graph.iterdir()],
        'outputs': [hashed(audit/name) for name in files], 'osm_data_at': 'controlled',
        'counts': {'graph_relevant_relations': 2}}), encoding='utf8')
    return audit, graph


def test_opt_in_preserves_existing_rules_and_adds_verified_reverse(tmp_path):
    audit, graph = fixture(tmp_path)
    before = build(audit, graph, tmp_path/'before.json')
    after = build(audit, graph, tmp_path/'after.json', include_same_way_uturn=True)
    assert before['applied_relations'] == 1 and after['applied_relations'] == 2
    assert before['rules'][0] in after['rules'] and after['same_way_uturn_relations'] == 1


def test_full_audit_tampering_cannot_publish_extended_rules(tmp_path):
    audit, graph = fixture(tmp_path)
    with (audit/'restrictions-graph-audit.jsonl').open('a') as out: out.write('\n{}')
    with pytest.raises(ValueError, match='전체 회전 원자료 해시'):
        build(audit, graph, tmp_path/'bad.json', include_same_way_uturn=True)
    assert not (tmp_path/'bad.json').exists()


@pytest.mark.parametrize('dijkstra', [False, True])
def test_added_uturn_prevents_resetting_a_forbidden_turn_with_an_immediate_reverse(dijkstra):
    records = make_records()
    corridor = [((0, 0), (0, 1)), ((0, 1), (0, 2)), ((0, 1), (1, 1)),
                ((0, 0), (1, 0)), ((1, 0), (2, 0)), ((2, 0), (2, 1)), ((2, 1), (1, 1))]
    allowed_edges = {arc(records, a, b) >> 1 for a, b in corridor}
    for idx, edge in enumerate(records['edges']):
        edge['car'] = int(idx in allowed_edges)
    # 오른쪽 이웃으로 돌아갔다 즉시 역행하면 진입 방향이 바뀌어 금지된 회전을 우회한다.
    left = rule(records, (0, 0), (0, 1), (1, 1), 'no_right_turn', 1)
    uturn = dict(relation_id=2, incoming=arc(records, (0, 1), (0, 2)),
                 outgoing=arc(records, (0, 2), (0, 1)), value='no_u_turn')
    before = GraphRouter(records=policy(deepcopy(records), [left]))
    after = GraphRouter(records=policy(records, [left, uturn]))
    before.force_dijkstra = after.force_dijkstra = dijkstra
    old = before.route(xy(0, 0), xy(1, 1))['paths'][0]
    got = after.route(xy(0, 0), xy(1, 1))['paths'][0]
    codes = got['turn_restrictions']['arc_codes']
    old_codes = old['turn_restrictions']['arc_codes']
    assert (uturn['incoming'], uturn['outgoing']) in list(zip(old_codes, old_codes[1:]))
    assert (uturn['incoming'], uturn['outgoing']) not in list(zip(codes, codes[1:]))
    assert got['distance'] == pytest.approx(reference(records, (0, 0), (1, 1)), abs=1.5)
    assert got['distance'] > old['distance']


@pytest.mark.parametrize('profile', ['bike', 'foot'])
def test_uturn_is_motorcar_only_and_free_departure_is_allowed(profile):
    records = make_records(v2=True)
    uturn = dict(relation_id=2, incoming=arc(records, (0, 0), (0, 1)),
                 outgoing=arc(records, (0, 1), (0, 0)), value='no_u_turn')
    old = GraphRouter(records=deepcopy(records)).route(xy(0, 1), xy(0, 0), profile=profile)
    rt = GraphRouter(records=policy(records, [uturn]))
    assert rt.route(xy(0, 1), xy(0, 0), profile=profile)['paths'][0]['distance'] == old['paths'][0]['distance']
    assert rt.route(xy(0, 1), xy(0, 0), profile='car')['paths'][0]['distance'] < 100
