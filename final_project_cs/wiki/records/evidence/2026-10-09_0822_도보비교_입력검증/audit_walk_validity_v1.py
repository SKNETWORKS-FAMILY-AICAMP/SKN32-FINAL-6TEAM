from pathlib import Path
import hashlib
import importlib.util
import json
import sys

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
sys.path.insert(0, str(cs))
scratch = Path(__file__).parent
state = json.loads((scratch / 'walk-validity-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
spec = importlib.util.spec_from_file_location('comparison_before', root / state['backups'][0]['backup'])
before = importlib.util.module_from_spec(spec)
spec.loader.exec_module(before)
from scripts.mobility import compare_kakao_golden as after

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inputs = [root / 'datasets/mobility/raw/kakao_golden/compare_resume_200_v5.json',
          root / 'datasets/mobility/raw/kakao_golden/2026-10-09_0725_도보평가_제품분모_G04_product_v2.json']
audits = []
for p in inputs:
    rows = json.loads(p.read_text(encoding='utf8'))['rows']
    old, new = before.summarise(rows), after.summarise(rows)
    same = all(new[k] == v if k != 'coverage' else all(new[k][x] == y for x, y in v.items())
               for k, v in old.items())
    assert same
    assert new['coverage']['walk_reference_invalid'] == 0
    assert new['coverage']['walk_product_invalid'] == 0
    audits.append({'input': p.relative_to(root).as_posix(), 'sha256': sha(p), 'rows': len(rows),
                   'prior_metrics_equal': same, 'coverage': new['coverage']})
synthetic = {'ours_walk_product': {'m': 300, 'min': True},
             'kakao': {'walk': {'shortest': {'km': .3, 'min': 5}}}}
old, new = before.summarise([synthetic]), after.summarise([synthetic])
assert old['coverage']['walk_product_offered'] == old['coverage']['walk_product_comparisons'] == 1
assert new['coverage']['walk_product_offered'] == new['coverage']['walk_product_comparisons'] == 0
got = {'scope': 'reaggregation of two preserved files; G04 is also in the 200 pairs; no new web or route computation',
       'audits': audits, 'controlled_boolean_reproduction': {'before': old['coverage'], 'after': new['coverage']},
       'web_attempts': {'browser_inventory': 'success', 'google_existing_tab_read': 'timeout; kernel reset',
                        'web_route_page_reads': {'google': 'inaccessible', 'naver': 'inaccessible', 'kakao': 'inaccessible'},
                        'new_routes': 0}, 'map_developer_api_calls': 0}
with (ev / 'existing-data-audit-v1.json').open('x', encoding='utf8') as f:
    json.dump(got, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({'files': len(audits), 'rows_by_file': [a['rows'] for a in audits],
                  'prior_metrics_equal': all(a['prior_metrics_equal'] for a in audits)}, ensure_ascii=False))
