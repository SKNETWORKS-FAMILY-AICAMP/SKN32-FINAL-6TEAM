"""검증된 회전 원문에서 방향이 하나씩인 정적 차량 관계만 새 sidecar로 만든다."""
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(audit_dir, graph_dir, output):
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
    result = dict(schema_version=1, created_at=datetime.now().astimezone().isoformat(),
                  license='ODbL 1.0 © OpenStreetMap contributors',
                  osm_data_at=manifest['osm_data_at'], graph_sha256=bound,
                  source_audit_sha256=digest(rows_path), source_relations=manifest['counts']['graph_relevant_relations'],
                  applied_relations=len(rules), excluded_candidate_relations=len(excluded),
                  excluded_candidate_ids=excluded, complete_road_rules=False, rules=rules)
    with output.open('x', encoding='utf8') as out:
        json.dump(result, out, ensure_ascii=False, separators=(',', ':'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--graph', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = build(args.audit, args.graph, args.out)
    print(json.dumps({key: data[key] for key in ('applied_relations', 'source_relations', 'excluded_candidate_relations')}))
