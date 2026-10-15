"""위키 인계 원본과 현재 도구를 독립 검토한다. 제품 인수는 판정하지 않는다."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[5]
OWN = Path(__file__).resolve().parent
WIKI = OWN.parent / 'wiki'
NOW = datetime.now(timezone(timedelta(hours=9)))
OUT = OWN / 'checks' / (NOW.strftime('%Y-%m-%d_%H%M%S_%f') + '_wiki_handoff')
OUT.mkdir(parents=True, exist_ok=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def junit(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': digest(path),
            'total': len(cases),
            'failed': sum(c.find('failure') is not None for c in cases),
            'errors': sum(c.find('error') is not None for c in cases),
            'skipped': sum(c.find('skipped') is not None for c in cases)}


def run(name, args):
    started = datetime.now(timezone(timedelta(hours=9))).isoformat()
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    result = subprocess.run([sys.executable, '-B', *args], cwd=ROOT, env=env,
                            capture_output=True, encoding='utf-8', errors='replace')
    (OUT / (name + '.log')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    return {'command': [sys.executable, '-B', *args], 'cwd': 'workspace root',
            'started_at_kst': started, 'finished_at_kst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
            'returncode': result.returncode, 'log': (OUT / (name + '.log')).relative_to(ROOT).as_posix()}


changes = read(WIKI / 'changed-files.json')
before = [{'path': row['path'], 'handoff_sha256': row['sha256'], 'current_sha256': digest(ROOT / row['path'])}
          for row in changes]
save('source-before.json', before)
original_junit = [junit(WIKI / n) for n in ('governance-tests-final.xml', 'cs-tests.xml')]
preserve = read(WIKI / 'findings-preservation.json')
old = read(ROOT / preserve['backup'])['findings']
current = read(ROOT / 'program/research/wiki_review_2026-10-11/findings-v2.json')['findings']
selection_equal = ({x['id']: (x.get('selected'), x.get('decision')) for x in old} ==
                   {x['id']: (x.get('selected'), x.get('decision')) for x in current})
commands = [run('governance', ['-m', 'pytest', 'program/scripts/tests/test_wiki_governance.py', '-q',
                            '-p', 'no:cacheprovider', '--basetemp=' + str(OUT / 'pytest-temp'),
                            '--junitxml=' + str(OUT / 'governance.xml'), '--tb=short']),
            run('wiki', ['program/scripts/check_wiki.py', '--include-records', '--json-output', str(OUT / 'wiki.json')]),
            run('catalog', ['program/scripts/build_wiki_catalogs.py', '--check'])]
after = [{'path': row['path'], 'current_sha256': digest(ROOT / row['path'])} for row in changes]
save('source-after.json', after)
check = read(OUT / 'wiki.json')
inventory = read(ROOT / 'wiki/governance/implementation-inventory.generated.json')
summary = {
    'reviewed_at_kst': NOW.isoformat(),
    'scope': '위키 도구·규격 인계 검토. 제품 기능·배포 인수 판정 아님',
    'handoff_hashes': {'matched': sum(x['handoff_sha256'] == x['current_sha256'] for x in before), 'total': len(before),
                       'changed_since_handoff': [x['path'] for x in before if x['handoff_sha256'] != x['current_sha256']]},
    'changed_during_review': [a['path'] for a, b in zip(before, after) if a['current_sha256'] != b['current_sha256']],
    'selection_and_decision_preserved': selection_equal,
    'original_junit': original_junit, 'commands': commands, 'independent_governance_junit': junit(OUT / 'governance.xml'),
    'current_wiki': {'scope': check['scope'], 'total_violations': check['total_violations'],
                     'problems': {k: v for k, v in check['problems'].items() if v}},
    'state_inventory': {'total': len(inventory['documents']), 'missing_any': sum(bool(x['missing_fields']) for x in inventory['documents'])},
    'acceptance': {'W16': '검토 범위의 문서·경로·구조 근거 확인; 인명 추가 배정 없음',
                   'W20': '도구 구현 확인; 기능별 90개 상태 적용은 담당 근거 수령 뒤 검토',
                   'W22': '범위 구분·회귀 확인; 전체 wiki 위반은 미해결',
                   'W23': '정의 행 집계·중복 거부·생성물 일치 확인; 등록 수는 통과 수 아님',
                   'W25': '현재 규칙/보존 기록 분리 확인; 기능 계약 전체 의미 검토는 미완료'},
    'deployment': 'not_deployed', 'product_acceptance': 'pending'
}
save('summary.json', summary)
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), **summary}, ensure_ascii=False, indent=2))
