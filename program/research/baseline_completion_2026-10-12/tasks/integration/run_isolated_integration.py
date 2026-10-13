"""업무 DB·외부 통신을 차단하고 현재 SQL의 새 전용 PostgreSQL에서 선택 시험을 실행한다."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import socket
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT / 'final_project_cs'
PG = Path.home() / 'anaconda3/envs/pgv/Library/bin'
STAMP = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S_%f')
RUN = HERE / 'checks' / (STAMP + '_isolated_integration')
RUN.mkdir(parents=True, exist_ok=False)
data = RUN / 'pgdata'
assert data.resolve().is_relative_to(HERE.resolve())
reuse = os.environ.get('ACOP_INTEGRATION_REUSE_OWN_CLUSTER')
database_name = 'integration_test'
if reuse:
    # 이 작업이 만든 정확한 중지 클러스터만 재사용한다. 이전 DB와 증거는 보존한다.
    previous = HERE / 'checks/2026-10-12_092645_945781_isolated_integration'
    assert Path(reuse).resolve() == (previous/'pgdata').resolve()
    assert json.loads((previous/'cleanup.json').read_text())['own_cluster_stopped'] is True
    data = Path(reuse).resolve()
    database_name = 'integration_local_' + STAMP.replace('-','').replace('_','')
env = os.environ.copy()
env['PATH'] = str(PG) + os.pathsep + env['PATH']
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]


def save(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def pg_call(args, name, *, check=True):
    with (RUN / name).open('wb') as log:
        result = subprocess.run([str(PG / args[0]), *map(str, args[1:])], env=env,
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
    if check and result.returncode:
        raise RuntimeError(name)
    return result.returncode


started = False
print(RUN.relative_to(ROOT).as_posix(), flush=True)
try:
    if reuse:
        assert pg_call(['pg_ctl.exe', '-D', data, 'status'], 'reuse-status.log', check=False) != 0
        save('reuse.json', {'task_owned_cluster':str(data.relative_to(ROOT)), 'new_database':database_name,
                            'previous_database_preserved':True})
    else:
        pg_call(['initdb.exe', '-D', data, '-U', 'integration_test', '-A', 'trust', '--encoding=UTF8', '--locale=C'], 'initdb.log')
    pg_call(['pg_ctl.exe', '-D', data, '-l', RUN / 'postgres.log', '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'], 'start.log')
    started = True
    dsn = f'postgresql://integration_test@127.0.0.1:{port}/{database_name}'
    os.environ.update(ACOP_DATABASE_URL=dsn, ACOP_OPS_READ_DATABASE_URL=dsn, DINING_TEST_DSN=dsn,
        ACOP_OPENAI_API_KEY='isolated-unused', ACOP_OPENAI_API_KEY_SERVER='', ACOP_MOBILITY_DATA_DIR='',
        ACOP_OLLAMA_BASE_URL='', ACOP_LOCAL_FT_BASE_URL='', ACOP_LLM_FAILOVER_ENABLED='false',
        ACOP_DISCORD_WEBHOOK_URL='', ACOP_OPS_ALERT_WEBHOOK_URL='', ACOP_DEPLOYMENT_VERSION='isolated-integration',
        ACOP_DIAGNOSTIC_SPOOL=str(RUN / 'private-spool/pending.sqlite3'),
            PGHOST='127.0.0.1', PGPORT=str(port), PGUSER='integration_test', PGDATABASE=database_name)
    os.environ['ACOP_INTEGRATION_POSTGRES_TEST_DSN'] = dsn
    sys.path.insert(0, str(CS))
    sys.path.insert(0, str(HERE.parent / 'verification/.deps'))
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    connect_db = psycopg.connect
    blocks = []

    def guarded_db(conninfo='', **kwargs):
        details = conninfo_to_dict(conninfo, **{k: v for k, v in kwargs.items() if k in ('host', 'port', 'dbname', 'user')})
        # 같은 새 전용 클러스터에서 아래 두 시험이 생성한 DB만 추가 허용한다.
        # 호스트·동적 포트 제한은 그대로이며 기존 업무 DB 이름은 허용하지 않는다.
        import re
        database = details.get('dbname', 'integration_test')
        allowed_database = (database in (database_name, 'postgres')
            or re.fullmatch(r'acop_(?:migtest|improve)_[0-9a-f]{10}', database) is not None)
        if (details.get('host') not in ('127.0.0.1', 'localhost')
            or str(details.get('port', '')) != str(port)
            or not allowed_database):
            blocks.append('non_isolated_database')
            raise RuntimeError('isolated_database_required')
        return connect_db(conninfo, **kwargs)

    psycopg.connect = guarded_db
    socket_connect, socket_bind = socket.socket.connect, socket.socket.bind
    ports = {port}

    def guarded_bind(sock, address):
        if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise RuntimeError('loopback_bind_required')
        value = socket_bind(sock, address)
        ports.add(sock.getsockname()[1])
        return value

    def guarded_connect(sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', 'localhost', '::1') and address[1] in ports:
            return socket_connect(sock, address)
        blocks.append('external_or_existing_service')
        raise RuntimeError('external_network_blocked')

    socket.socket.bind, socket.socket.connect = guarded_bind, guarded_connect
    os.chdir(CS)
    with guarded_db(dsn.rsplit('/', 1)[0] + '/postgres', autocommit=True) as conn:
        from psycopg import sql
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(database_name)))
    from app.infrastructure.db.migrate import apply_all, safety_manifest
    with guarded_db(dsn) as conn:
        apply_all(conn)
    save('migration.json', safety_manifest())
    from scripts.register_prompts import main as register_prompts
    assert register_prompts() == 0

    if os.environ.get('ACOP_INTEGRATION_PREPARE_DATA') == '1':
        sys.path.insert(0, str(HERE))
        from prepare_isolated_data import prepare
        prepare(ROOT, RUN, guarded_db, dsn, save)

    def sources():
        return {p.relative_to(CS).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for base in ('app', 'tests', 'config', 'scripts', 'deploy') for p in (CS / base).rglob('*')
            if p.is_file() and p.suffix in ('.py', '.json', '.yaml', '.yml', '.sql', '.sh')
            and not {'_backup', '__pycache__', 'legacy', 'node_modules'} & set(p.parts)}

    before = sources()
    save('source-before.json', before)
    import pytest
    args = [*sys.argv[1:], '-q', '--tb=short', '-p', 'no:cacheprovider', '-p', 'no:langsmith',
            '--basetemp=' + str(RUN / 'tmp'), '--junitxml=' + str(RUN / 'junit.xml')]
    code = pytest.main(args)
    after = sources()
    save('source-after.json', after)
    save('result.json', {'at_kst': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(), 'exit': int(code),
        'args': args, 'network_blocks': blocks, 'source_changed': sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k)),
        'scope': 'new separate test database in task-owned PostgreSQL; current safe SQL runner; external and business DB blocked'})
    raise SystemExit(code)
finally:
    if 'prepare_isolated_data' in sys.modules:
        try:
            sys.modules['prepare_isolated_data'].finish_rag(save)
        except Exception as error:
            save('rag-cleanup-error.json', {'error_type':type(error).__name__})
    if started or (data.exists() and pg_call(['pg_ctl.exe', '-D', data, 'status'], 'status.log', check=False) == 0):
        stopped = pg_call(['pg_ctl.exe', '-D', data, '-m', 'fast', '-w', 'stop'], 'stop.log', check=False)
        save('cleanup.json', {'own_cluster_stopped': stopped == 0, 'exit': stopped})
