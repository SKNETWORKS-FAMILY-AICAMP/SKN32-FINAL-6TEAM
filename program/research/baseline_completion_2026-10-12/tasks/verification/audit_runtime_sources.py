"""실행 시작 뒤 변경·추가·삭제된 소스를 빠짐없이 별도 집계한다."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
CS = HERE.parents[4]/'final_project_cs'
started = datetime.now(ZoneInfo('Asia/Seoul'))
current = {p.relative_to(CS).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for base in ('app','tests','eval','config','deploy','scripts')
           for p in (CS/base).rglob('*') if p.is_file()
           and p.suffix in ('.py','.json','.yaml','.yml','.sql','.sh')
           and not {'_backup','legacy','__pycache__'} & set(p.parts)}
comparisons = []
for run in sorted(p.name for p in (HERE/'runs').iterdir() if p.is_dir()):
    for path in sorted((HERE/'runs'/run).glob('*-source-before.json')):
        before = json.loads(path.read_text(encoding='utf-8'))
        comparisons.append({'run':run,'label':path.name.removesuffix('-source-before.json'),
                            'changed':[key for key in sorted(before.keys()&current.keys()) if before[key]!=current[key]],
                            'added':sorted(current.keys()-before.keys()),
                            'removed':sorted(before.keys()-current.keys())})
finished = datetime.now(ZoneInfo('Asia/Seoul'))
output = HERE/'runs/2026-10-12_clean_travel'/('source_drift_'+finished.strftime('%H%M%S')+'.json')
if output.exists(): raise SystemExit('이미 있는 집계입니다. 새 이름이 필요합니다.')
result = {'started_at_kst':started.isoformat(),'finished_at_kst':finished.isoformat(),
          'scope':'순차 파일 읽기 관측. 동시 편집을 잠그거나 기준선을 동결한 결과가 아님.',
          'current_sha256':current,'comparisons':comparisons}
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'output':str(output),'comparisons':[{k:v if k in ('run','label') else len(v) for k,v in row.items()} for row in comparisons]},ensure_ascii=False,indent=2))
