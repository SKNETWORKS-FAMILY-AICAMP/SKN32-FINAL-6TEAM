"""배포하지 않고 실제 작업 셸의 두 회차와 영속 볼륨 연결을 확인한다."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[5]
OWN = Path(__file__).resolve().parent
stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S_%f')
OUT = OWN / 'checks' / (stamp + '_replay_worker')
OUT.mkdir(parents=True, exist_ok=False)
source = ROOT / 'final_project_cs/deploy/worker.sh'
body = source.read_text(encoding='utf-8')
assert body.count('while true; do') == body.count('  sleep 60') == 1
# 실행 명령은 그대로 두고 반복 횟수·대기만 시험용으로 한정한다.
prefix = '''diagnostic_attempt=0
python() {
  printf 'CALL %s\\n' "$*"
  case "$*" in
    *replay_operations_diagnostics*)
      diagnostic_attempt=$((diagnostic_attempt + 1))
      if [ "$diagnostic_attempt" = 1 ]; then return 1; fi ;;
  esac
  return 0
}
date() {
  case "$1" in
    +%H%M) printf '0000\\n' ;;
    +%F) printf '2026-10-12\\n' ;;
    *) printf '2026-10-12T00:00:00+09:00\\n' ;;
  esac
}
'''
script = OUT / 'two-rounds.sh'
script.write_text(prefix + body.replace('while true; do', 'for round in 1 2; do').replace('  sleep 60', '  :'), encoding='utf-8')
bash = Path('C:/Program Files/Git/bin/bash.exe')
run = subprocess.run([str(bash), str(script)], capture_output=True, text=True, timeout=20)
(OUT / 'stdout.log').write_text(run.stdout, encoding='utf-8')
(OUT / 'stderr.log').write_text(run.stderr, encoding='utf-8')
calls = run.stdout.splitlines()
try:
    failure = json.loads(run.stderr)
except ValueError:
    failure = {}
checks = {
    'two_rounds_complete': run.returncode == 0,
    'diagnostics_retry_next_round': sum('replay_operations_diagnostics --prune' in line for line in calls) == 2,
    'independent_work_continues': sum('run_sweepers --once' in line for line in calls) == 2 and sum('run_outbox_worker --once --drain' in line for line in calls) == 2,
    'failed_round_visible': len(run.stderr.splitlines()) == 1 and failure.get('job') == 'diagnostics' and failure.get('exit') == 1,
}
paths = ['deploy/worker.sh', 'deploy/docker-compose.yml', 'deploy/docker-compose.admin.yml', 'deploy/arm/compose.yml']
main = yaml.safe_load((ROOT / 'final_project_cs/deploy/docker-compose.yml').read_text(encoding='utf-8'))
admin = yaml.safe_load((ROOT / 'final_project_cs/deploy/docker-compose.admin.yml').read_text(encoding='utf-8'))
arm = yaml.safe_load((ROOT / 'final_project_cs/deploy/arm/compose.yml').read_text(encoding='utf-8'))
for label, spec, services, volume in [
    ('public', main, ['tripilot-api', 'tripilot-worker'], 'tripilot_diagnostics'),
    ('admin', admin, ['tripilot-admin'], 'tripilot_diagnostics'),
    ('arm', arm, ['api', 'worker'], 'diagnostics')]:
    checks[label + '_persistent_private_spool_wired'] = all(
        volume + ':/srv/var/operations-diagnostics' in spec['services'][name]['volumes']
        and spec['services'][name]['environment']['ACOP_DIAGNOSTIC_SPOOL'] == '/srv/var/operations-diagnostics/pending.sqlite3'
        and 'ACOP_DEPLOYMENT_VERSION' in spec['services'][name]['environment'] for name in services)
checks['volumes_defined'] = 'tripilot_diagnostics' in main['volumes'] and 'diagnostics' in arm['volumes']
result = {'at_kst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
          'scope': 'actual shell job commands; injected Python function; no Docker, DB, outbox, provider or model execution',
          'checks': checks, 'passed': sum(checks.values()), 'total': len(checks),
          'shell_returncode': run.returncode,
          'sources': {p: hashlib.sha256((ROOT / 'final_project_cs' / p).read_bytes()).hexdigest() for p in paths}}
(OUT / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'output': OUT.relative_to(ROOT).as_posix(), 'passed': result['passed'], 'total': result['total']}))
raise SystemExit(0 if all(checks.values()) else 1)
