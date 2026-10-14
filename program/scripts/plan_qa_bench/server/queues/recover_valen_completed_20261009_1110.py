"""완료 Valen D3/E 원본과 실제 대기열을 읽기 전용으로 회수한다."""
from pathlib import Path
import hashlib, io, json, os, subprocess, sys, tarfile
from datetime import datetime, timezone

q=Path('/tmp/tripilot-a-backlog-20261008')
state=json.loads((q/'state.json').read_text())
manifest=json.loads((q/'manifest.json').read_text())
jobs=state['jobs']; worker=int((q/'queue.pid').read_text())
assert Path(f'/proc/{worker}').is_dir()
ids=['valen_08b_original_d3_a1','valen_08b_original_mx_a1']
assert all(jobs[i]['status'].startswith('completed') for i in ids)
ready=[]; blocked=[]
for j in manifest['jobs']:
    if jobs.get(j['id'],{}).get('status') in ['completed','completed_with_errors','failed','running']:continue
    checks={k:Path(j[k]).is_file() for k in ['model','prompts','script']}
    if j.get('lora'):checks['lora']=Path(j['lora']).is_file()
    (ready if all(checks.values()) else blocked).append({'id':j['id'],'checks':checks})
s=os.statvfs('/tmp')
snapshot={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'worker_pid':worker,
          'worker_cmdline':Path(f'/proc/{worker}/cmdline').read_bytes().replace(b'\0',b' ').decode(),
          'GPU':subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader']).decode(),
          'available_bytes':s.f_bavail*s.f_frsize,'ready':ready,'blocked':blocked,'state':state,
          'manifest_sha256':hashlib.sha256((q/'manifest.json').read_bytes()).hexdigest()}
buf=io.BytesIO(); proof={}
with tarfile.open(fileobj=buf,mode='w:gz') as t:
    def add(name,data):
        entry=tarfile.TarInfo(name);entry.size=len(data);t.addfile(entry,io.BytesIO(data))
        proof[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    for i in ids:
        for f in sorted((q/i).iterdir()):
            if f.is_file():add(i+'/'+f.name,f.read_bytes())
    add('snapshot.json',json.dumps(snapshot,ensure_ascii=False,indent=2).encode())
    add('manifest.json',(q/'manifest.json').read_bytes())
    raw=json.dumps(proof,ensure_ascii=False,indent=2).encode()
    ent=tarfile.TarInfo('ARCHIVE_SHA.json');ent.size=len(raw);t.addfile(ent,io.BytesIO(raw))
sys.stdout.buffer.write(buf.getvalue())
