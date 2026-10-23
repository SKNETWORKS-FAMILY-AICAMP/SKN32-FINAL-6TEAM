"""대기 작업의 입력·공간 조건을 읽기만 하고 관측마다 새 파일로 보관한다."""
from pathlib import Path
from datetime import datetime, timezone
import json, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')
machine,alias,stamp=sys.argv[1:4]
remote='''
import os,json,pathlib,sys
m=sys.argv[1]
def space(path):
    s=os.statvfs(path)
    return {'path':path,'available_bytes':s.f_bavail*s.f_frsize,'filesystem_free_is_not_account_quota':True}
r={'root_space':space('/root'),'temp_space':space('/tmp')}
if m=='A':
    p=pathlib.Path('/tmp/tripilot-a-backlog-20261008')
    manifest=json.loads((p/'manifest.json').read_text())
    state=json.loads((p/'state.json').read_text())['jobs']
    ready=[]; blocked=[]
    for j in manifest['jobs']:
        if state.get(j['id'],{}).get('status') in ['completed','completed_with_errors','failed','running']:continue
        checks={k:pathlib.Path(j[k]).is_file() for k in ['model','prompts','script']}
        if j.get('lora'):checks['lora']=pathlib.Path(j['lora']).is_file()
        (ready if all(checks.values()) else blocked).append({'id':j['id'],'input_checks':checks})
    r.update({'ready':ready,'blocked':blocked,'worker_pid':int((p/'queue.pid').read_text())})
else:
    r['existing_base_config']=pathlib.Path('/root/hf_models/gemma-4-E4B-it/config.json').is_file()
    r['existing_train']=pathlib.Path('/root/work/train_oos2.jsonl').is_file()
    p=pathlib.Path('/root/daily_rag_20261008')
    r['b56_markers']={k:(p/k).exists() for k in ['SMOKE_DONE','cosine_DONE','finch_DONE','ALLDONE']}
    p=pathlib.Path('/root/daily_rag_repeat_20261008')
    r['b57_markers']={k:(p/k).exists() for k in ['prepared.json','finch_DONE','cosine_DONE','ALLDONE']}
    if (p/'prepared.json').is_file():r['b57_prepared']=json.loads((p/'prepared.json').read_text())
    r['b57_pid']=int((p/'queue.pid').read_text()) if (p/'queue.pid').is_file() else None
    p=pathlib.Path('/root/daily_rag_seed3_20261009')
    r['b58_markers']={k:(p/k).exists() for k in ['prepared.json','finch_DONE','cosine_DONE','ALLDONE']}
    if (p/'prepared.json').is_file():r['b58_prepared']=json.loads((p/'prepared.json').read_text())
    r['b58_pid']=int((p/'queue.pid').read_text()) if (p/'queue.pid').is_file() else None
    r['download_paths_present']={k:pathlib.Path('/root/hf_models/'+k+'/config.json').is_file() for k in ['spark_s1_4b','jevify_e4b']}
    r['rounded_available_GB']=os.popen('df -BG --output=avail /root').read().splitlines()[-1].strip()
print(json.dumps(r))
'''
run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3 - '+machine],input=remote,capture_output=True,text=True,encoding='utf-8',timeout=60)
if run.returncode:raise RuntimeError(run.stderr)
data=json.loads(run.stdout);data['observed_at_utc']=datetime.now(timezone.utc).isoformat()
target=Path(__file__).resolve().parent/'results/gpu_backlog_20261008'/f'{machine}_conditions_{stamp}.json'
with target.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
print(json.dumps(data,ensure_ascii=False))
