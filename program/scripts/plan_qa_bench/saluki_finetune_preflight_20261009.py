"""Read-only official release metadata and existing GPU resources; no weight download."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import os

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results' / ('saluki_finetune_preflight_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
OUT.mkdir(parents=True, exist_ok=False)
REPOS = ['ConwayResearch/Underdog-Saluki-27B-1.0', 'ConwayResearch/Underdog-27B-1.0', 'Qwen/Qwen3.8-27B', 'ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF']
REMOTE = r'''import json,os,pathlib,subprocess,time
r={'observed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gpu':subprocess.getoutput('nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader'),'mounts':subprocess.getoutput('df -B1 / /workspace /dev/shm'),'processes':subprocess.getoutput('ps -eo pid,ppid,etimes,args | grep -E "run_B54|run_B56|run_B57|run_B58|qlora_train|gpu_eval_queue|valen_native|llama-server"')}
r['meminfo']=pathlib.Path('/proc/meminfo').read_text()
for f in ['/sys/fs/cgroup/memory/memory.limit_in_bytes','/sys/fs/cgroup/memory/memory.usage_in_bytes','/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.current']:
 if pathlib.Path(f).exists():r[f]=pathlib.Path(f).read_text().strip()
r['local_model_dirs']=subprocess.getoutput('find /root /workspace /tmp -maxdepth 4 -type f \\( -name config.json -o -name model.safetensors.index.json -o -iname "*Saluki*" \\) 2>/dev/null')
print(json.dumps(r))'''

def release(repo):
    url='https://huggingface.co/api/models/'+repo+'?blobs=true'
    raw=urllib.request.urlopen(url,timeout=40).read()
    info=json.loads(raw)
    target=OUT/repo.replace('/','--')
    target.mkdir()
    (target/'api.json').write_bytes(raw)
    files=[]
    for name in ['README.md','LICENSE','NOTICE','config.json','model.safetensors.index.json']:
        if any(s['rfilename']==name for s in info['siblings']):
            data=urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+info['sha']+'/'+name,timeout=40).read()
            (target/name).write_bytes(data)
            files.append({'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    return {'repo':repo,'revision':info['sha'],'createdAt':info.get('createdAt'),'lastModified':info.get('lastModified'),'siblings':info['siblings'],'small_files':files,'gated':info.get('gated'),'private':info.get('private')}

def machine(which,alias):
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3','-'],input=REMOTE,text=True,encoding='utf-8',capture_output=True,timeout=60)
    if p.returncode: raise RuntimeError(which+':'+p.stderr)
    data=json.loads(p.stdout)
    (OUT/(which+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
    return {'machine':which,'gpu':data['gpu'],'mounts':data['mounts'],'observed_utc':data['observed_utc']}

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    todo=[pool.submit(release,r) for r in REPOS]
    for label in ('A', 'B'):
        alias = os.environ.get('TRIPILOT_GPU_' + label + '_SSH')
        if alias:
            todo.append(pool.submit(machine, label, alias))
    results=[]
    for f in todo:
        try: results.append(f.result())
        except Exception as e: results.append({'error':repr(e)})
(OUT/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'out':str(OUT),'results':results},ensure_ascii=False))
