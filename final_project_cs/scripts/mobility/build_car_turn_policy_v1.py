"""검증된 회전 원문에서 방향이 하나씩인 정적 차량 관계만 새 sidecar로 만든다."""
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_same_way_uturn(row):
    """동일 도로의 유일한 역방향 회전만 해석한다. 중간점 양방향은 고르지 않는다."""
    audit = row['graph_audit']
    roles = {role: [m for m in row['members'] if m['role'] == role]
             for role in ('from', 'to', 'via')}
    if (audit['effective_motorcar_value_candidate'] != 'no_u_turn'
            or audit['unsupported_or_unresolved_reasons'] != ['same_way_turn_requires_arc_geometry_semantics']
            or audit['conditional_tags'] or audit['except_modes'] or audit['via_form'] != 'node'
            or any(len(roles[role]) != 1 for role in roles)):
        return False
    before, after, via = (roles[role][0] for role in ('from', 'to', 'via'))
    if (before['type'] != 'w' or after['type'] != 'w' or via['type'] != 'n'
            or before['ref'] != after['ref']):
        return False
    inc, out = audit['incoming_arc_codes'], audit['outgoing_arc_codes']
    return (len(inc) == len(out) == 1
            and all(isinstance(a, int) and not isinstance(a, bool) and a >= 0 for a in inc + out)
            and out[0] == inc[0] ^ 1)


def passenger_car_exception(row):
    """버스·대형화물차만 예외인 단순 관계는 승용차·택시에 그대로 적용합니다."""
    audit = row['graph_audit']
    modes = set(audit['except_modes'])
    roles = {role: [m for m in row['members'] if m['role'] == role]
             for role in ('from', 'to', 'via')}
    if (not modes or not modes <= {'bus', 'hgv'} or audit['conditional_tags']
            or audit['via_form'] != 'node'
            or audit['unsupported_or_unresolved_reasons'] != ['except_requires_vehicle_classification']
            or audit['effective_motorcar_value_candidate'] not in {
                'no_left_turn', 'no_right_turn', 'no_straight_on', 'no_u_turn',
                'only_left_turn', 'only_right_turn', 'only_straight_on', 'only_u_turn'}
            or any(len(roles[role]) != 1 for role in roles)):
        return False
    if any(roles[role][0]['type'] != kind for role, kind in [('from', 'w'), ('to', 'w'), ('via', 'n')]):
        return False
    inc, out = audit['incoming_arc_codes'], audit['outgoing_arc_codes']
    return (len(inc) == len(out) == 1
            and all(isinstance(a, int) and not isinstance(a, bool) and a >= 0 for a in inc + out))


def build(audit_dir, graph_dir, output, *, include_same_way_uturn=False, include_car_exceptions=False):
    manifest = json.loads((audit_dir/'manifest.json').read_text(encoding='utf8'))
    nodes, edges = graph_dir/'nodes.jsonl.gz', graph_dir/'edges.jsonl.gz'
    bound = {path.name: digest(path) for path in (nodes, edges)}
    for name, value in bound.items():
        expected = next(row['sha256'] for row in manifest['inputs'] if Path(row['name']).name == name)
        if value != expected:
            raise ValueError('회전 추출의 그래프와 현재 그래프가 다릅니다')
    rows_path = audit_dir/'static-motorcar-candidates.jsonl'
    expected = next(row['sha256'] for row in manifest['outputs'] if row['name'] == rows_path.name)
    if digest(rows_path) != expected:
        raise ValueError('회전 후보 원자료 해시가 다릅니다')
    rows = [json.loads(line) for line in rows_path.read_text(encoding='utf8').splitlines()]
    rules, excluded = [], []
    for row in rows:
        audit = row['graph_audit']
        if len(audit['incoming_arc_codes']) != 1 or len(audit['outgoing_arc_codes']) != 1:
            excluded.append(row['relation_id'])
            continue
        if (not audit['candidate_for_static_simple_motorcar'] or audit['conditional_tags']
                or audit['except_modes'] or audit['via_form'] != 'node'
                or audit['unsupported_or_unresolved_reasons']):
            raise ValueError('미지원 관계가 초기 적용 대상에 섞였습니다')
        rules.append(dict(relation_id=row['relation_id'], incoming=audit['incoming_arc_codes'][0],
                          outgoing=audit['outgoing_arc_codes'][0],
                          value=audit['effective_motorcar_value_candidate']))
    extra, audit_hash = [], None
    exception_rules = []
    if include_same_way_uturn or include_car_exceptions:
        full_path = audit_dir/'restrictions-graph-audit.jsonl'
        expected = next(row['sha256'] for row in manifest['outputs'] if row['name'] == full_path.name)
        audit_hash = digest(full_path)
        if audit_hash != expected:
            raise ValueError('전체 회전 원자료 해시가 다릅니다')
        full_rows = [json.loads(line) for line in full_path.read_text(encoding='utf8').splitlines()]
        if len(full_rows) != manifest['counts']['graph_relevant_relations']:
            raise ValueError('전체 회전 원자료 분모가 다릅니다')
        extra = [dict(relation_id=row['relation_id'], incoming=row['graph_audit']['incoming_arc_codes'][0],
                      outgoing=row['graph_audit']['outgoing_arc_codes'][0], value='no_u_turn')
                 for row in full_rows if include_same_way_uturn and unique_same_way_uturn(row)]
        rules.extend(extra)
        if include_car_exceptions:
            exception_rules = [dict(relation_id=row['relation_id'], incoming=row['graph_audit']['incoming_arc_codes'][0],
                                   outgoing=row['graph_audit']['outgoing_arc_codes'][0],
                                   value=row['graph_audit']['effective_motorcar_value_candidate'])
                               for row in full_rows if passenger_car_exception(row)]
            rules.extend(exception_rules)
        if len({row['relation_id'] for row in rules}) != len(rules):
            raise ValueError('적용 회전 관계 ID가 중복됩니다')
        rules.sort(key=lambda row: row['relation_id'])
    result = dict(schema_version=1, created_at=datetime.now().astimezone().isoformat(),
                  license='ODbL 1.0 © OpenStreetMap contributors',
                  osm_data_at=manifest['osm_data_at'], graph_sha256=bound,
                  source_audit_sha256=digest(rows_path), source_relations=manifest['counts']['graph_relevant_relations'],
                  applied_relations=len(rules), excluded_candidate_relations=len(excluded),
                  excluded_candidate_ids=excluded, complete_road_rules=False, rules=rules)
    if include_same_way_uturn:
        result.update(same_way_uturn_relations=len(extra), full_audit_sha256=audit_hash)
    if include_car_exceptions:
        result.update(passenger_car_exception_relations=len(exception_rules),
                      vehicle_class='passenger_car', full_audit_sha256=audit_hash)
    with output.open('x', encoding='utf8') as out:
        json.dump(result, out, ensure_ascii=False, separators=(',', ':'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--include-same-way-uturn', action='store_true')
    parser.add_argument('--include-car-exceptions', action='store_true')
    args = parser.parse_args()
    data = build(args.audit, args.graph, args.out, include_same_way_uturn=args.include_same_way_uturn,
                 include_car_exceptions=args.include_car_exceptions)
    print(json.dumps({key: data[key] for key in ('applied_relations', 'source_relations', 'excluded_candidate_relations')}))
