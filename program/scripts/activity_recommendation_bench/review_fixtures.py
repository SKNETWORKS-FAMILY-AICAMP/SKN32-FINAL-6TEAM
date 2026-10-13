"""Independent recalculation and review record, separate from the fixture generator."""
import json
from pathlib import Path
from bench import CONFIG, ROOT, digest, evaluate, feasible, gold, public, rule_rank, utility

directory = ROOT / CONFIG['dataset_directory']
raw = directory / 'raw'
manifest = json.loads((raw / 'manifest-v2.json').read_text(encoding='utf-8'))
checks = []
for name in (CONFIG['evaluation_file'], CONFIG['smoke_file']):
    source = raw / name
    assert digest(source.read_bytes()) == manifest['files'][name]['sha256']
    for line in source.read_text(encoding='utf-8').splitlines():
        case = json.loads(line)
        assert len(case['candidates']) == 14
        assert len({c['id'] for c in case['candidates']}) == 14
        assert abs(sum(case['weights'].values()) - 1) < 1e-9
        expected = gold(case)
        assert len(expected) == 9
        assert abs(sum(p['importance'] for p in case['customer']['preferences']['likes']) - 1) < 1e-9
        for c in case['candidates']:
            traits = c['oracle_features']['traits']
            prefs = case['customer']['preferences']
            taste = max(0, min(1, sum(p['importance'] for p in prefs['likes'] if p['trait'] in traits) - sum(p['penalty'] for p in prefs['dislikes'] if p['trait'] in traits)))
            assert abs(taste - c['oracle_taste']) < 1e-9
            similarity = 1 if c['category'] == case['origin']['category'] else .5 if c['category'] == '복합문화' else 0
            assert similarity == c['oracle_similarity']
            assert feasible(case, c) == (not c['oracle_hard_reasons'])
        public_text = json.dumps(public(case), ensure_ascii=False)
        assert 'oracle_' not in public_text
        assert evaluate(case, [c['id'] for c in expected[:3]])['ndcg3'] == 1
        checks.append({'case_id': case['case_id'], 'feasible': len(expected), 'gold_top3': [c['id'] for c in expected[:3]],
                       'margin': utility(case, expected[0], expected[0]['oracle_taste'], expected[0]['oracle_similarity']) - utility(case, expected[1], expected[1]['oracle_taste'], expected[1]['oracle_similarity']),
                       'rule_metrics': evaluate(case, rule_rank(case))})
path = directory / 'root_fixture_review.json'
if path.exists():
    raise RuntimeError('existing_review_preserved')
out = {'reviewer': 'root agent, separate from authoring agent; not human review', 'cases_checked': len(checks), 'checks': checks,
       'semantic_review': 'Customer profiles and all 21 trait descriptor templates read. Structured preferences are authoritative. Trait overlap and fixed repeated phrasing limit this test to fixture-defined ranking, not real customer satisfaction.',
       'scope': 'Complete supplied candidate pool; upstream candidate retrieval quality and missing or stale facts not tested.'}
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'cases_checked': len(checks), 'assertions_passed': True, 'rule_top1_correct': sum(c['rule_metrics']['top1_correct'] for c in checks)}, ensure_ascii=False))
