"""이 작업 전용 PostgreSQL에서만 실행하고 외부 호출을 차단한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import socket
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT / 'final_project_cs'
PG = Path.home() / 'anaconda3/envs/pgv/Library/bin'
STAMP = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
RUN = HERE / 'runs' / STAMP
RUN.mkdir(parents=True, exist_ok=False)
env = os.environ.copy()
env['PATH'] = str(PG) + os.pathsep + env['PATH']
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
data = RUN / 'pgdata'

def call(args, name):
    # PostgreSQL 자식이 파이프를 물고 남아 기다리지 않도록 일반 로그 파일을 쓴다.
    with (RUN / name).open('wb') as log:
        completed = subprocess.run([str(PG / args[0]), *map(str, args[1:])],
                                   env=env, stdout=log, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError(name)

call(['initdb.exe', '-D', data, '-U', 'orchestration', '-A', 'trust',
      '--encoding=UTF8', '--locale=C'], 'initdb.log')
call(['pg_ctl.exe', '-D', data, '-l', RUN / 'postgres.log', '-o',
      f'-h 127.0.0.1 -p {port}', '-w', 'start'], 'start.log')
dsn = f'postgresql://orchestration@127.0.0.1:{port}/orchestration'
os.environ.update(ACOP_DATABASE_URL=dsn, ACOP_OPS_READ_DATABASE_URL=dsn,
    ACOP_OPENAI_API_KEY='isolated-unused', ACOP_OPENAI_API_KEY_SERVER='',
    ACOP_OLLAMA_BASE_URL='', ACOP_LOCAL_FT_BASE_URL='', ACOP_LLM_FAILOVER_ENABLED='false',
    ACOP_DISCORD_WEBHOOK_URL='', ACOP_OPS_ALERT_WEBHOOK_URL='', ACOP_MOBILITY_DATA_DIR='',
    PGHOST='127.0.0.1', PGPORT=str(port), PGUSER='orchestration', PGDATABASE='orchestration')
sys.path.insert(0, str(CS))
sys.path.insert(0, str(HERE.parent / 'verification' / '.deps'))
os.chdir(CS)
import psycopg
from psycopg.conninfo import conninfo_to_dict
db_connect = psycopg.connect
network_blocks = []

def isolated_db(conninfo='', **kwargs):
    details = conninfo_to_dict(conninfo, **{k:v for k,v in kwargs.items()
                               if k in ('host','port','dbname','user')})
    if (details.get('host', '127.0.0.1') not in ('127.0.0.1','localhost')
        or int(details.get('port', port)) != port
        or details.get('dbname', 'orchestration') not in ('orchestration','postgres')):
        raise RuntimeError('isolated DB guard')
    return db_connect(conninfo, **kwargs)
psycopg.connect = isolated_db
connect = socket.socket.connect
bind = socket.socket.bind
ports = {port}

def local_bind(sock, address):
    result = bind(sock, address)
    if isinstance(address, tuple) and address[0] in ('127.0.0.1','localhost','::1'):
        ports.add(sock.getsockname()[1])
    return result

def local_connect(sock, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1','localhost','::1') and address[1] in ports:
        return connect(sock, address)
    network_blocks.append('external_or_unclaimed_loopback')
    raise RuntimeError('external network blocked')
socket.socket.bind = local_bind
socket.socket.connect = local_connect

def sources():
    return {str(p.relative_to(CS)): hashlib.sha256(p.read_bytes()).hexdigest()
            for base in ('app','tests','config') for p in (CS/base).rglob('*')
            if p.is_file() and p.suffix in ('.py','.yaml','.json','.sql')
            and not {'_backup','__pycache__','legacy'} & set(p.parts)}

def save(name, value):
    (RUN/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

print(RUN, flush=True)
try:
    with isolated_db(dsn.rsplit('/',1)[0]+'/postgres', autocommit=True) as conn:
        conn.execute('CREATE DATABASE orchestration')
    from app.infrastructure.db.migrate import apply_all, safety_manifest
    with isolated_db(dsn) as conn:
        apply_all(conn)
    save('migration.json', safety_manifest())
    save('source-before.json', sources())
    import pytest
    class Results:
        rows = []
        def pytest_runtest_logreport(self, report):
            self.rows.append({'nodeid':report.nodeid,'when':report.when,
                              'outcome':report.outcome,'seconds':report.duration})
    results = Results()
    code = pytest.main(['-q','--tb=short','-p','no:langsmith',
                       '--junitxml='+str(RUN/'checks.xml'), *sys.argv[1:]], plugins=[results])
    save('results.json', {'exit':int(code), 'reports':results.rows,
                          'network_blocks':network_blocks,
                          'finished_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()})
    save('source-after.json', sources())
    raise SystemExit(code)
finally:
    call(['pg_ctl.exe','-D',data,'-m','fast','-w','stop'], 'stop.log')
