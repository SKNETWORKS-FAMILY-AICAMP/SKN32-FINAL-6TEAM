"""외부 통신·업무 DB를 막고 운영 재전송·보관 통합 시험을 실행한다."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import socket
import sys

ROOT = Path(__file__).resolve().parents[5]
OWN = Path(__file__).resolve().parent
stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S_%f')
OUT = OWN / 'checks' / (stamp + '_diagnostic_callback')
OUT.mkdir(parents=True, exist_ok=False)
os.environ['ACOP_DIAGNOSTIC_SPOOL'] = str(OUT / 'private-spool/pending.sqlite3')
os.environ.update(ACOP_MOBILITY_DATA_DIR='', ACOP_OPENAI_API_KEY='', ACOP_OPENAI_API_KEY_SERVER='',
                  ACOP_OLLAMA_BASE_URL='', ACOP_LOCAL_FT_BASE_URL='', ACOP_LLM_FAILOVER_ENABLED='false',
                  ACOP_DISCORD_WEBHOOK_URL='', ACOP_OPS_ALERT_WEBHOOK_URL='')
allowed_ports = set()
blocked = []
original_bind, original_connect = socket.socket.bind, socket.socket.connect


def bind(sock, address):
    if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('integration check: non-loopback bind blocked')
    result = original_bind(sock, address)
    allowed_ports.add(sock.getsockname()[1])
    return result


def connect(sock, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', 'localhost', '::1') and address[1] in allowed_ports:
        return original_connect(sock, address)
    blocked.append('external_or_unclaimed_loopback')
    raise RuntimeError('integration check: external or existing service connection blocked')


socket.socket.bind, socket.socket.connect = bind, connect
import psycopg


def no_db(*args, **kwargs):
    blocked.append('database')
    raise RuntimeError('integration check: DB connection blocked')


psycopg.connect = no_db
os.chdir(ROOT / 'final_project_cs')
sys.path.insert(0, str(ROOT / 'final_project_cs'))
paths = [ROOT / 'final_project_cs' / p for p in ['app/application/controller.py', 'app/application/operations_diagnostics.py', 'app/composition.py', 'scripts/run_sweepers.py', 'app/domains/travel_ops/components/watch/batch_executor.py', 'app/domains/travel_ops/components/watch/trip_watch_batch.py', 'app/domains/travel_ops/components/watch/trip_watch_cases.py', 'tests/unit/test_operations_diagnostics.py', 'tests/unit/core/test_controller_resume_recovery.py', 'tests/unit/travel/test_classification_execution_plan.py', 'tests/unit/travel/test_plugin_worker_availability.py', 'tests/architecture/test_basement_is_domain_free.py', 'tests/architecture/test_basement_layers.py']]



def snapshot():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


before = snapshot()
started = datetime.now(timezone(timedelta(hours=9))).isoformat()
import pytest
args = ['tests/unit/test_operations_diagnostics.py',
        'tests/unit/core/test_controller_resume_recovery.py',
        'tests/unit/travel/test_classification_execution_plan.py',
        'tests/architecture/test_basement_is_domain_free.py',
        'tests/architecture/test_basement_layers.py',
        'tests/unit/travel/test_plugin_worker_availability.py',
        '-q', '-p', 'no:cacheprovider', '--basetemp=' + str(OUT / 'tmp'),
        '--junitxml=' + str(OUT / 'junit.xml'), '-o', 'faulthandler_timeout=30', '--tb=short']
code = pytest.main(args)
after = snapshot()
(OUT / 'run.json').write_text(json.dumps({'started_at_kst': started,
    'finished_at_kst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
    'command': [sys.executable, '-B', str(Path(__file__).resolve())], 'pytest_args': args,
    'returncode': code, 'source_before': before, 'source_after': after,
    'changed_during_run': [p for p in before if before[p] != after[p]], 'blocked_connections': blocked,
    'scope': 'DB denied; only self-bound loopback ports allowed; temporary SQLite and transaction doubles; no HTTP or model; no PostgreSQL'},
    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'returncode': code,
                  'changed_during_run': [p for p in before if before[p] != after[p]]}, ensure_ascii=False))
raise SystemExit(code)
