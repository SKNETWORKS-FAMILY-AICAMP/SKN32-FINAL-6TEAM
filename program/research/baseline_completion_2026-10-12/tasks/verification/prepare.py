"""검증 전용 실행 목록·해시·임시 PostgreSQL 준비. 업무 DB를 사용하지 않는다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import shutil
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
CS = ROOT / 'final_project_cs'
STAMP = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
RUN = HERE / 'runs' / STAMP
RUN.mkdir(parents=True, exist_ok=False)

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

manifest = CS / 'tests/test-suites.json'
m = json.loads(manifest.read_text(encoding='utf-8'))
actual = {p.relative_to(CS).as_posix() for base in ('tests', 'eval/tests')
          for p in (CS/base).rglob('test_*.py')
          if not {'_backup', 'legacy', '__pycache__'} & set(p.parts)}
declared = set(m['common'] + m['travel'])
missing = sorted(actual-declared)
if missing:
    backup = manifest.parent / '_backup' / (STAMP+'_verification_manifest')
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(manifest, backup/manifest.name)
    for p in missing:
        m['common' if p.startswith('tests/unit/core/') else 'travel'].append(p)
    for group in ('common', 'travel'):
        m[group].sort()
    save(manifest, m)
save(RUN/'manifest-audit.json', {'added':missing,'stale':sorted(declared-actual),
     'overlap':sorted(set(m['common']) & set(m['travel'])),
     'counts':{k:len(m[k]) for k in ('common','travel')},
     'backup':str(backup.relative_to(ROOT)) if missing else None})
files = [p for base in ('app','tests','eval','config','deploy','scripts')
         for p in (CS/base).rglob('*') if p.is_file()
         and p.suffix in ('.py','.json','.yaml','.yml','.sql','.sh')
         and not {'_backup','legacy','__pycache__'} & set(p.parts)]
save(RUN/'source-before.json', {p.relative_to(CS).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
pg = Path.home()/'anaconda3/envs/pgv/Library/bin'
env = os.environ.copy()
env['PATH'] = str(pg)+os.pathsep+env['PATH']
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
data = RUN/'pgdata'
def call(args, name):
    r = subprocess.run([str(pg/args[0]), *map(str,args[1:])],env=env,capture_output=True)
    (RUN/name).write_bytes(r.stdout+r.stderr)
    if r.returncode:
        raise RuntimeError(f'{name}: exit {r.returncode}')
call(['initdb.exe','-D',data,'-U','verification','-A','trust','--encoding=UTF8','--locale=C'],'initdb.log')
call(['pg_ctl.exe','-D',data,'-l',RUN/'postgres.log','-o',f'-h 127.0.0.1 -p {port}','-w','start'],'start.log')
save(RUN/'isolation.json', {'port':port,'database':'verification','user':'verification',
    'pg_bin':str(pg),'data':str(data),'run':str(RUN),'created_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
    'scope':'새 로컬 PostgreSQL 클러스터. 실제 업무 DB와 분리. 외부 호출은 실행 가드로 차단.'})
print(RUN)
