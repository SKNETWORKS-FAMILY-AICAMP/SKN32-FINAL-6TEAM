"""임시 DB에서 시험 실행. 외부 통신·업무 DB 연결은 차단한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import os
import socket
import sys
import faulthandler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT/'final_project_cs'
parser = argparse.ArgumentParser()
parser.add_argument('run')
parser.add_argument('suite', choices=['migrate','bootstrap','common','travel'])
parser.add_argument('--label')
parser.add_argument('--resume-from')
parser.add_argument('--only-from')
args, rest = parser.parse_known_args()
if args.resume_from and args.only_from:
    parser.error('재개 제외와 이전 항목 재검증을 동시에 지정할 수 없습니다.')
label = args.label or args.suite
run = Path(args.run).resolve()
iso = json.loads((run/'isolation.json').read_text(encoding='utf-8'))
port = iso['port']
dbname = iso['database']
if not dbname.startswith('verification'):
    raise SystemExit('검증 전용 DB 이름이 필요합니다.')
dsn = f'postgresql://verification@127.0.0.1:{port}/{dbname}'
os.environ.update(ACOP_DATABASE_URL=dsn, ACOP_OPS_READ_DATABASE_URL=dsn,
    DINING_TEST_DSN=dsn, DINING_PG_PORT=str(port), DINING_DB_USER='verification',
    ACOP_OPENAI_API_KEY='verification-unused', ACOP_OPENAI_API_KEY_SERVER='',
    ACOP_OLLAMA_BASE_URL='', ACOP_LOCAL_FT_BASE_URL='', ACOP_LLM_FAILOVER_ENABLED='false',
    ACOP_DISCORD_WEBHOOK_URL='', ACOP_OPS_ALERT_WEBHOOK_URL='',
    ACOP_MOBILITY_DATA_DIR='', PGHOST='127.0.0.1', PGPORT=str(port),
    PGUSER='verification', PGDATABASE=dbname, PGCONNECT_TIMEOUT='5')
# libpq가 Python socket을 거치지 않으므로 DB 접속도 별도로 제한한다.
sys.path.insert(0,str(HERE/'.deps'))
import psycopg
from psycopg.conninfo import conninfo_to_dict
original_db = psycopg.connect
def guarded_db(conninfo='', **kwargs):
    details = conninfo_to_dict(conninfo, **{k:v for k,v in kwargs.items() if k in ('host','port','dbname','user')})
    if details.get('host', '127.0.0.1') not in ('127.0.0.1','localhost') or int(details.get('port',port)) != port:
        raise RuntimeError('verification guard: non-isolated DB connection blocked')
    return original_db(conninfo, **kwargs)
psycopg.connect = guarded_db
original_connect = socket.socket.connect
original_bind = socket.socket.bind
allowed_ports = {port}
network_blocks = []
def guarded_bind(sock, address):
    result=original_bind(sock,address)
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','localhost','::1'):
        allowed_ports.add(sock.getsockname()[1])
    return result
socket.socket.bind=guarded_bind
def guarded_connect(sock, address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','localhost','::1') and address[1] in allowed_ports:
        # 시험이 직접 확보한 루프백 포트만 허용. 기존 모델·프록시에는 접속하지 않는다.
        return original_connect(sock,address)
    network_blocks.append({'kind':'external_or_unclaimed_loopback','at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat()})
    raise RuntimeError('verification guard: external network connection blocked')
socket.socket.connect = guarded_connect
sys.path.insert(0,str(CS))
os.chdir(CS)
def write(name, value):
    target=run/name
    if target.exists():
        raise RuntimeError('Use a new evidence name')
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
if args.suite=='migrate':
    with original_db(dsn.rsplit('/',1)[0]+'/postgres',autocommit=True) as conn:
        if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(dbname,)).fetchone():
            conn.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(dbname)))
    from app.infrastructure.db.migrate import apply_all,safety_manifest
    with psycopg.connect(dsn) as conn:
        apply_all(conn)
    write('migration.json',safety_manifest())
elif args.suite=='bootstrap':
    from scripts.register_prompts import main
    code = main()
    with psycopg.connect(dsn) as conn:
        rows = conn.execute('SELECT prompt_key,count(*) FROM prompts WHERE active GROUP BY prompt_key ORDER BY prompt_key').fetchall()
    write('prompt-bootstrap.json',{'exit':code,'active_prompt_key_counts':rows,'network_blocks':network_blocks})
    raise SystemExit(code)
else:
    from scripts.run_test_suite import SuiteSelector
    import pytest
    faulthandler.dump_traceback_later(120,repeat=True)
    before={p.relative_to(CS).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for base in ('app','tests','eval','config','deploy','scripts')
            for p in (CS/base).rglob('*') if p.is_file()
            and p.suffix in ('.py','.json','.yaml','.yml','.sql','.sh')
            and not {'_backup','legacy','__pycache__'} & set(p.parts)}
    write(label+'-source-before.json',before)
    class Results:
        def __init__(self): self.rows=[]
        def pytest_runtest_logreport(self,report):
            row={'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'seconds':report.duration}
            if report.failed:
                row['failure'] = report.longreprtext
            self.rows.append(row)
            with (run/(label+'-progress.jsonl')).open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
        def pytest_sessionfinish(self,session,exitstatus):
            faulthandler.cancel_dump_traceback_later()
            write(label+'-outcomes.json', {'exit':int(exitstatus),'finished_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),'reports':self.rows,'network_blocks':network_blocks})
            after={p:hashlib.sha256((CS/p).read_bytes()).hexdigest() if (CS/p).exists() else None for p in before}
            write(label+'-source-after.json',after)
    manifest=json.loads((CS/'tests/test-suites.json').read_text(encoding='utf-8'))
    plugins=[SuiteSelector(args.suite,manifest,str(run/(label+'-collection.json'))),Results()]
    if args.resume_from or args.only_from:
        previous_path = args.resume_from or args.only_from
        previous=[json.loads(line) for line in Path(previous_path).read_text(encoding='utf-8').splitlines()]
        completed={row['nodeid'] for row in previous if row['when']=='call' or (row['when']=='setup' and row['outcome'] in ('skipped','failed'))}
        class Resume:
            @pytest.hookimpl(tryfirst=True)
            def pytest_collection_modifyitems(self,config,items):
                chosen=[item for item in items if (item.nodeid in completed) == bool(args.only_from)]
                excluded=[item for item in items if item not in chosen]
                write(label+'-resume.json',{'previous_progress':previous_path,'mode':'only_previous' if args.only_from else 'exclude_previous','previous_completed':len(completed),'selected_nodeids':[item.nodeid for item in chosen],'excluded_nodeids':[item.nodeid for item in excluded],'scope':'중단 전 판정과 재검증을 정확한 시험 식별자로 분리. 최종 해시 재대조 필요.'})
                config.hook.pytest_deselected(items=excluded)
                items[:]=chosen
        plugins.append(Resume())
    result=pytest.main(['-q','-ra','--tb=short','--junitxml='+str(run/(label+'.xml')),*rest],
        plugins=plugins)
    raise SystemExit(result)
