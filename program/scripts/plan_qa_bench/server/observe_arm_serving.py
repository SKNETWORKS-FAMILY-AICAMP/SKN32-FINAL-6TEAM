"""ARM 실행 증거를 읽기만 한다. SSH 접속 정보는 호출자가 개인 설정에서 준다."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

root = Path.home()/'bench/continuous-travel-20261008'
manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
state = json.loads((root/'state.json').read_text())
active = json.loads((root/'active.json').read_text()) if (root/'active.json').exists() else None
samples = [json.loads(x) for x in (root/'resources.jsonl').read_text().splitlines()]
recent = samples[-60:]
duration = sum(x['window_s'] for x in recent)
weighted = lambda key: sum(x[key]*x['window_s'] for x in recent)/duration
steady = []
if active and active.get('engine_pid'):
    # 현재 active.at은 답안 저장마다 바뀐다. 연속 목표 이상 표본의 길이를 별도로 센다.
    # 모델 해시·준비 구간은 최초 실행기 로그와 함께 해석한다.
    for row in samples:
        if row['workload_cpu_pct_of_two_cores'] >= manifest['cpu_target_percent_of_two_cores']:
            steady.append(row)
        elif steady:
            steady = []
contiguous = sum(x['window_s'] for x in steady)
coverage = {}
for folder in root.iterdir():
    path = folder/'answers.jsonl' if folder.is_dir() else None
    if path and path.exists():
        rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        coverage[folder.name] = dict(saved=len(rows), unique_ids=len({r['i'] for r in rows}),
                                    correct=sum(r['correct'] for r in rows),
                                    errors_or_unparsed=sum(not r.get('parsed', False) for r in rows),
                                    last_row=rows[-1] if rows else None)
service = subprocess.check_output(['systemctl','show','tripilot-arm-serving.service',
            '-p','ActiveState','-p','MainPID','-p','MemoryCurrent','-p','MemoryMax','-p','CPUQuotaPerSecUSec','-p','AllowedCPUs','-p','NRestarts'], text=True)
locks = json.loads(subprocess.check_output(['lslocks','--json','--output','PID,COMMAND,TYPE,PATH'], text=True))
held = [a for a in locks['locks'] if 'continuous-travel' in a.get('path', '')]
import urllib.request
with urllib.request.urlopen(f"http://127.0.0.1:{manifest['port']}/health", timeout=3) as res:
    health = json.load(res)
with urllib.request.urlopen(f"http://127.0.0.1:{manifest['port']}/slots", timeout=3) as res:
    slots = json.load(res)
report = dict(held_locks=held, health=health, slots=slots, observed_at=datetime.now(timezone.utc).isoformat(), manifest=manifest, state=state,
              active=active, coverage=coverage, service=service,
              enabled=subprocess.check_output(['systemctl','is-enabled','tripilot-arm-serving.service'],text=True).strip(),
              resources_recent=recent, resource_summary=dict(window_s=duration,
                  cpu_pct_two_cores=weighted('workload_cpu_pct_of_two_cores'),
                  host_cpu_busy_pct=weighted('host_cpu_busy_pct'), host_steal_pct=weighted('host_steal_pct'),
                  memory_current_bytes=recent[-1]['workload_memory_bytes'],
                  above_20_contiguous_seconds=contiguous, five_minute_target_verified=duration>=295 and weighted('workload_cpu_pct_of_two_cores')>=20),
              free_bytes=__import__('shutil').disk_usage(root).free)
print(json.dumps(report, ensure_ascii=True))
