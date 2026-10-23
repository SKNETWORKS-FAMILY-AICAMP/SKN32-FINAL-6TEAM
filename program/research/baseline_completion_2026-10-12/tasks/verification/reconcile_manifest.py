"""새 시험의 실행 목록만 보완하며 기존 분류는 변경하지 않는다."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
CS = HERE.parents[4]/'final_project_cs'
target = CS/'tests/test-suites.json'
original = target.read_bytes()
manifest = json.loads(original)
disk = {p.relative_to(CS).as_posix() for base in ('tests','eval/tests') for p in (CS/base).rglob('test_*.py') if not {'legacy','_backup','__pycache__'} & set(p.parts)}
registered = set(manifest['common'])|set(manifest['travel'])
missing = sorted(disk-registered)
common_new = {'tests/integration/db/test_unattended_operations.py','tests/security/test_unattended_operations.py','tests/unit/test_operations_diagnostics.py'}
for path in missing:
    group = 'common' if path.startswith('tests/unit/core/') or path in common_new else 'travel'
    manifest[group].append(path)
for group in ('common','travel'):
    manifest[group].sort()
stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
if missing:
    backup = CS/'tests/_backup'/(stamp+'_verification_manifest')
    backup.mkdir(parents=True)
    shutil.copy2(target,backup/target.name)
    if target.read_bytes()!=original:
        raise SystemExit('동시에 목록이 변경됐습니다. 다시 대조해야 합니다.')
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
result={'added':missing,'disk_files':len(disk),'registered_files':len(set(manifest['common'])|set(manifest['travel'])),'overlap':sorted(set(manifest['common'])&set(manifest['travel'])),'stale':sorted(registered-disk),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
output=HERE/'runs/2026-10-12_035832'/('manifest_'+stamp+'.json')
if output.exists(): raise SystemExit('같은 이름의 결과가 있습니다.')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
