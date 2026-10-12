"""승인된 GPU의 읽기 전용 관측을 새 파일에 저장한다."""
import subprocess, sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parent
machine=sys.argv[1]
alias=sys.argv[2]
reader=(root/'server/queues/check_backlog_20261008.py').read_text(encoding='utf-8')
run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3 - '+machine],input=reader,capture_output=True,text=True,encoding='utf-8',timeout=60)
if run.returncode:
    print(run.stderr)
    raise SystemExit(run.returncode)
data=json.loads(run.stdout)
target=root/'results/gpu_backlog_20261008'/f'{machine}_snapshot_1019.json'
with target.open('x',encoding='utf-8') as f:
    json.dump(data,f,ensure_ascii=False,indent=2)
print(json.dumps(data,ensure_ascii=False))
