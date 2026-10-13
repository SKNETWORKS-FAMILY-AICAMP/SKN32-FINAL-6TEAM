"""자동 목록과 현재 문서 출력의 재현 증거를 저장한다."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).parent
now = datetime.now(timezone(timedelta(hours=9)))
spec = importlib.util.spec_from_file_location('reproduce_catalogs', ROOT/'program/scripts/build_wiki_catalogs.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
one, two = build.render(), build.render()
equal = one == two
results = []
for command in [
    ['python','program/scripts/build_wiki_catalogs.py','--check'],
    ['python','C:/Users/playdata2/.agents/skills/diagram-design/scripts/self_check.py',str((OUT/'state-recording.html').relative_to(ROOT))],
]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    results.append({'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
docs = [ROOT/'wiki/governance/review-policy.md', ROOT/'wiki/governance/evidence-grades.md']
before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in docs]
command = ['python', str((OUT/'apply_documents.py').relative_to(ROOT))]
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in docs]
results.append({'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
data = {'started_at_kst':now.isoformat(),'finished_at_kst':datetime.now(timezone(timedelta(hours=9))).isoformat(),
    'catalog_render_equal_twice':equal,'document_output_equal':before==after,'commands':results,
    'generated_files':[p.relative_to(ROOT).as_posix() for p in one],
    'passed':equal and before==after and all(r['returncode']==0 for r in results)}
p = OUT/'reproducibility.json'
if p.exists():
    import shutil
    backup = OUT/'_backup'/now.strftime('%Y-%m-%d_%H%M%S_%f_reproduce')/p.name
    backup.parent.mkdir(parents=True)
    shutil.copy2(p, backup)
p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('생성·문서 출력 재현:',data['passed'])
raise SystemExit(int(not data['passed']))
