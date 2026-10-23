"""승인된 별칭을 인자로 받아 읽기 전용 관측을 중복 없는 파일로 보관한다."""
import json, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding='utf-8')
machine, alias, stamp=sys.argv[1:4]
root=Path(__file__).resolve().parent
reader=(root/'server/queues/check_backlog_20261008.py').read_text(encoding='utf-8')
run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3 - '+machine],input=reader,capture_output=True,text=True,encoding='utf-8',timeout=60)
if run.returncode: raise RuntimeError(run.stderr)
data=json.loads(run.stdout)
data['observed_at_utc']=datetime.now(timezone.utc).isoformat()
target=root/'results/gpu_backlog_20261008'/f'{machine}_snapshot_{stamp}.json'
with target.open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
summary={'machine':machine,'snapshot':str(target),'gpu':data['gpu_snapshot']}
if machine=='A':
    summary.update({'state':data['state'],'answers':data['answers'],'worker_process_present':str(data['worker_pid']) in data['processes']})
else:
    active_log=data.get('active_training_log')
    summary.update({'processes':data['processes'],'active_training_variants':data.get('active_training_variants',[]),
                    'training_log':active_log,'training_tail':data['logs'].get(active_log,'').splitlines()[-4:]})
print(json.dumps(summary,ensure_ascii=False))
