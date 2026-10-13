"""검증 산출물 링크·구문과 SQL 담당의 실행 해시를 읽기 전용으로 대조한다."""
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT/'final_project_cs'
stamp = datetime.now(ZoneInfo('Asia/Seoul'))
python_files = sorted(HERE.glob('*.py'))
syntax = []
for path in python_files:
    try:
        ast.parse(path.read_text(encoding='utf-8'))
        error = None
    except SyntaxError as exc:
        error = str(exc)
    syntax.append({'file':path.name,'valid':error is None,'error':error})
links = []
for path in (HERE/'report.md', HERE/'failure-handoff.md', HERE/'current-results.md'):
    if not path.exists():
        continue
    for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        if '://' in target: continue
        resolved = (path.parent/target.split('#',1)[0]).resolve()
        links.append({'document':path.name,'target':target,'exists':resolved.exists()})
sql_root = ROOT/'program/research/migration_safety_2026-10-12'
validation = json.loads((sql_root/'source-validation.json').read_text(encoding='utf-8'))
hashes = []
for rel, expected in validation['owned_source_sha256'].items():
    path = CS/rel.replace('\\','/')
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    hashes.append({'file':rel,'recorded_sha256':expected,'current_sha256':actual,'matches':actual==expected})
migration = json.loads((HERE/'runs/2026-10-12_035832/migration.json').read_text(encoding='utf-8'))
migration_drift = []
for name, expected in migration['sha256'].items():
    path = CS/'app/infrastructure/db'/(name if name.endswith('.py') else 'migrations/'+name)
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    if actual != expected: migration_drift.append({'name':name,'recorded_sha256':expected,'current_sha256':actual})
result = {'checked_at_kst':stamp.isoformat(),'python_syntax':syntax,'local_links':links,'sql_dependency_source_hashes':hashes,'isolated_db_initial_input_drift':migration_drift,'sql_report_summary':json.loads((sql_root/'summary.json').read_text(encoding='utf-8'))['final_runs']}
output = HERE/'runs/2026-10-12_035832'/('artifacts_'+stamp.strftime('%H%M%S')+'.json')
if output.exists(): raise SystemExit('이름 중복')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(output),'syntax':{'passed':sum(row['valid'] for row in syntax),'total':len(syntax)},'links':{'passed':sum(row['exists'] for row in links),'total':len(links),'missing':[row for row in links if not row['exists']]},'sql_source':{'matched':sum(row['matches'] for row in hashes),'total':len(hashes),'mismatch':[row for row in hashes if not row['matches']]},'db_input_drift':migration_drift},ensure_ascii=False,indent=2))
