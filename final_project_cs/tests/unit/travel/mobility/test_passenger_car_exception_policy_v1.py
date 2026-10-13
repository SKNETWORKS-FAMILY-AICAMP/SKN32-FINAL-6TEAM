"""승용차와 예외 차량을 구분하고 승용차 경로에 확인된 원문만 적용합니다."""
import json
from pathlib import Path

import pytest

from scripts.mobility.build_car_turn_policy_v1 import build, passenger_car_exception
from .test_same_way_uturn_policy_v1 import row, fixture


def exception_row(mode):
    r = row()
    r['relation_id'] = 13
    r['graph_audit'].update(effective_motorcar_value_candidate='no_left_turn',
        unsupported_or_unresolved_reasons=['except_requires_vehicle_classification'], except_modes=[mode])
    return r


@pytest.mark.parametrize('mode', ['bus', 'hgv'])
def test_bus_or_heavy_goods_exception_does_not_exempt_passenger_cars(mode):
    assert passenger_car_exception(exception_row(mode))


@pytest.mark.parametrize('mode', ['taxi', 'psv', 'motorcar', 'motor_vehicle', 'unknown'])
def test_potential_taxi_exception_or_unknown_class_is_never_generalized(mode):
    assert not passenger_car_exception(exception_row(mode))


@pytest.mark.parametrize('fault', ['conditional', 'ambiguous', 'via_way', 'missing_way', 'bool_arc'])
def test_exception_does_not_hide_other_unsupported_conditions(fault):
    r = exception_row('bus'); a = r['graph_audit']
    if fault == 'conditional': a['conditional_tags'] = {'restriction:conditional': 'no_left_turn @ (Mo-Fr)'}
    if fault == 'ambiguous': a['incoming_arc_codes'] = [8, 10]
    if fault == 'via_way': r['members'][2]['type'] = 'w'
    if fault == 'missing_way': a['unsupported_or_unresolved_reasons'].append('missing_graph_ways')
    if fault == 'bool_arc': a['incoming_arc_codes'] = [True]
    assert not passenger_car_exception(r)


def test_opt_in_adds_exceptions_preserving_existing_uturn_rules(tmp_path):
    import hashlib
    audit, graph = fixture(tmp_path)
    full = audit/'restrictions-graph-audit.jsonl'
    with full.open('a', encoding='utf8') as out: out.write('\n'+json.dumps(exception_row('bus')))
    manifest = audit/'manifest.json'; doc = json.loads(manifest.read_text())
    doc['counts']['graph_relevant_relations'] = 3
    for item in doc['outputs']:
        if item['name'] == full.name: item['sha256'] = hashlib.sha256(full.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(doc))
    old = build(audit, graph, tmp_path/'old.json', include_same_way_uturn=True)
    new = build(audit, graph, tmp_path/'new.json', include_same_way_uturn=True, include_car_exceptions=True)
    assert len(new['rules']) == 3
    assert all(r in new['rules'] for r in old['rules'])
    assert new['passenger_car_exception_relations'] == 1


@pytest.mark.mobility_full
def test_public_graph_has_all_three_unambiguous_non_passenger_exceptions():
    root = Path(__file__).resolve().parents[5]
    base = root/'datasets/mobility/processed/mobility'
    path = base/'road_graph_v2/turn_restrictions_v1.json'
    data = json.loads(path.read_text(encoding='utf8'))
    applied = {r['relation_id'] for r in data['rules']}
    assert {6213359, 6213360, 20125787} <= applied
    from app.domains.travel_ops.instances.mobility.engine.graph_router import GraphRouter
    from app.domains.travel_ops.instances.mobility.engine.turn_restrictions import load, permitted
    router = GraphRouter(base/'road_graph_v2')
    router._load()
    policy = load(router)
    assert policy[2]['applied_relations'] == len(applied)
    for rule in data['rules']:
        if rule['relation_id'] in {6213359, 6213360, 20125787}:
            expected = rule['value'].startswith('only_')
            assert permitted(policy, rule['incoming'], rule['outgoing']) is expected
