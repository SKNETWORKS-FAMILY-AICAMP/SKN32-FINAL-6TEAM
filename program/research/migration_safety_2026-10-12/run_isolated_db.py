"""Run only migration tests in this task's independent, loopback-only cluster."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psycopg

here = Path(__file__).resolve().parent
workspace = here.parents[2]
runtime = here / '_runtime'
postgres = next((runtime/'postgres').rglob('postgres.exe'))
pgroot = postgres.parent.parent
for source in (runtime/'vector').rglob('*'):
    if source.is_file() and source.parts[-2] != 'server':
        relative = source.relative_to(runtime/'vector')
        if relative.parts[0] in ('lib', 'share'):
            dest = pgroot / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
cluster = runtime/'cluster'
assert cluster.resolve().is_relative_to(here)
flags = subprocess.CREATE_NO_WINDOW
if not cluster.exists():
    result = subprocess.run([str(postgres.parent/'initdb.exe'), '-D',str(cluster),'-U','migration_safety',
        '-A','trust','-E','UTF8','--no-locale'], capture_output=True, text=True, creationflags=flags)
    (runtime/'initdb.log').write_text(result.stdout+result.stderr, encoding='utf-8')
    result.check_returncode()
log = open(runtime/'postgres.log', 'w', encoding='utf-8')
process = subprocess.Popen([str(postgres),'-D',str(cluster),'-h','127.0.0.1','-p','15543'],
    stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
dsn = 'host=127.0.0.1 port=15543 user=migration_safety dbname=postgres'
try:
    for attempt in range(40):
        if process.poll() is not None:
            raise RuntimeError('isolated PostgreSQL exited; inspect private runtime log')
        try:
            conn = psycopg.connect(dsn, autocommit=True, connect_timeout=1)
            break
        except psycopg.OperationalError:
            time.sleep(.25)
    else:
        raise RuntimeError('isolated PostgreSQL startup timeout')
    version = conn.execute('SELECT version()').fetchone()[0]
    conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
    vector_version = conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]
    env = os.environ.copy()
    env['ACOP_DATABASE_URL'] = 'postgresql+psycopg://migration_safety@127.0.0.1:15543/postgres'
    env['PYTHONPATH'] = str(here/'_deps')
    env['TEMP'] = env['TMP'] = str(runtime)
    command = [sys.executable, '-m', 'pytest', 'tests/integration/db/test_migrations_rerun.py',
        '-q','-rs','--tb=short','--basetemp='+str(here/'tmp-db-v2'),
        '--junitxml='+str(here/'db-results-v2.xml')]
    result = subprocess.run(command, cwd=workspace/'final_project_cs', env=env,
        capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=flags)
    (here/'db-run-v2.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    remaining = conn.execute("SELECT datname FROM pg_database WHERE datname LIKE 'acop_migtest_%'").fetchall()
    (here/'db-runtime-result.json').write_text(json.dumps({'version':version, 'vector':vector_version,
        'scope':'independent task-owned cluster, synthetic travel data only',
        'test_exit_code':result.returncode, 'remaining_test_databases':remaining,
        'command':command},ensure_ascii=False,indent=2),encoding='utf-8')
    conn.close()
    print(result.stdout)
    exit_code = result.returncode
finally:
    stopped = subprocess.run([str(postgres.parent/'pg_ctl.exe'),'-D',str(cluster),'-m','fast','-w','stop'],
        capture_output=True, text=True, creationflags=flags, timeout=30)
    process.wait(timeout=30)
    log.close()
    (here/'cluster-stop.json').write_text(json.dumps({'exit_code':stopped.returncode,'process_stopped':process.poll() is not None}))
sys.exit(exit_code)
