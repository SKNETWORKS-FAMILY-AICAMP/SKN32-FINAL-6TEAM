"""통합 담당의 전체 실행 원본과 후속 판정을 독립 대조한다."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT / 'final_project_cs'
OUT = HERE / 'runs/2026-10-12_followup_064826'
summary_path = ROOT / 'program/research/baseline_completion_2026-10-12/tasks/integration/checks/suite-review-2026-10-12_064405.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
current = {p.relative_to(CS).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
           for base in ('app', 'tests', 'eval', 'config', 'deploy', 'scripts')
           for p in (CS / base).rglob('*') if p.is_file()
           and p.suffix in ('.py', '.json', '.yaml', '.yml', '.sql', '.sh')
           and not {'_backup', 'legacy', '__pycache__'} & set(p.parts)}
runs, latest, collections = [], {}, {}
for expected in summary['runs']:
    folder = ROOT / expected['path']
    xml = folder / 'junit.xml'
    sha = hashlib.sha256(xml.read_bytes()).hexdigest()
    root = ET.parse(xml).getroot()
    counts, seen = Counter(), set()
    for case in root.iter('testcase'):
        state = next((tag for tag in ('error', 'failure', 'skipped') if case.find(tag) is not None), 'passed')
        state = 'failed' if state == 'failure' else state
        counts[state] += 1
        name = case.attrib['name']
        # 이 한 사례만 수집 시 UUID다. 다른 매개변수는 합치지 않는다.
        if case.attrib['classname'] == 'tests.security.test_personal_ai_oauth':
            name = re.sub(r'(test_access_record_must_match_its_grant_audience_owner_client_and_scope\[customer)-[0-9a-f-]{36}(\])', r'\1-<collection-uuid>\2', name)
        key = (case.attrib['classname'], name)
        assert key not in seen, key
        seen.add(key)
        latest[key] = {'state': state, 'run': expected['label']}
    before = json.loads((folder / 'source-before.json').read_text(encoding='utf-8'))
    after = json.loads((folder / 'source-after.json').read_text(encoding='utf-8'))
    result = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
    changed = sorted(k for k in before.keys() & current.keys() if before[k] != current[k])
    row = {'label': expected['label'], 'path': expected['path'], 'counts': dict(counts),
           'total': sum(counts.values()), 'junit_sha256': sha,
           'junit_hash_matches_summary': sha == expected['junit_sha256'],
           'counts_match_summary': dict(counts) == expected['counts'],
           'source_before_after_equal': before == after,
           'source_scope_files': len(before), 'current_matching_scope_files': len(before.keys() & current.keys()),
           'current_changed_files': changed, 'current_removed_files': sorted(before.keys() - current.keys()),
           'current_only_files_outside_recorded_scope': sorted(current.keys() - before.keys()),
           'exit': result['exit'], 'blocked_attempts': dict(Counter(result['network_blocks']))}
    runs.append(row)
    if expected['label'] in ('common', 'travel'):
        collections[expected['label']] = seen
remaining = [{'classname': k[0], 'name': k[1], **value} for k, value in latest.items() if value['state'] != 'passed']
out = {'at_kst': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
       'review_source': str(summary_path.relative_to(ROOT)), 'runs': runs,
       'all_original_counts_and_hashes_match': all(r['junit_hash_matches_summary'] and r['counts_match_summary'] for r in runs),
       'whole_common_travel_overlap': len(collections['common'] & collections['travel']),
       'unique_tests': len(latest), 'latest_per_test_counts': dict(Counter(v['state'] for v in latest.values())),
       'remaining': remaining, 'current_source_sha256': current,
       'scope': '원본 JUnit 직접 재집계·SHA256 비교. 고유 시험 후속 결과이며 단일 전체 재실행 통과가 아님. 1237파일 원 실행 범위와 독립 1410파일 범위 차이를 명시하며 제외 파일까지 검증됐다고 하지 않음.'}
target = OUT / 'integration-original-audit.json'
assert not target.exists()
target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in out.items() if k not in ('current_source_sha256', 'remaining', 'runs')}, ensure_ascii=False, indent=2))
print(json.dumps([{k:v for k,v in r.items() if k != 'current_only_files_outside_recorded_scope'} for r in runs], ensure_ascii=False, indent=2))
