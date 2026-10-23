"""완료 연결검사와 실행 중 답안의 고정 시점 사본만 회수한다."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
base = Path(__file__).parent
archive = base / 'runtime_20261009_0232'
archive.mkdir(exist_ok=False)
remote = r'''
import base64,hashlib,json,time
from pathlib import Path
root=Path('/tmp/tripilot-a-backlog-20261008')
paths=list((root/'saluki_original_smoke12_a1').glob('*'))
d3=root/'saluki_original_d3_a1'
paths += [d3/n for n in ['saluki_contract.json','context_lengths.json','started.json','saluki_resources.jsonl','d_test_saluki_original_d3_a1.jsonl','saluki_summary.json']]
paths += [Path('/tmp/tripilot-saluki-20261009/SMOKE_PASS.json')]
files=[]
for p in paths:
 if p.is_file() and p.stat().st_size<20*1024**2:
  b=p.read_bytes()
  files.append(dict(relative=(p.parent.name+'/'+p.name),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),data=base64.b64encode(b).decode()))
print(json.dumps(dict(timestamp=time.time(),files=files)))
'''
result = subprocess.run(['ssh','acopilot-gpu','python3 -'],input=remote,text=True,encoding='utf-8',capture_output=True,check=True)
bundle=json.loads(result.stdout)
manifest=[]
for item in bundle['files']:
    blob=base64.b64decode(item.pop('data'))
    assert hashlib.sha256(blob).hexdigest()==item['sha256']
    path=archive/item['relative']
    path.parent.mkdir(exist_ok=True)
    with path.open('xb') as out:
        out.write(blob)
    manifest.append(item)
with (archive/'capture_manifest.json').open('x',encoding='utf-8') as out:
    json.dump(dict(observed_at_utc=datetime.fromtimestamp(bundle['timestamp'],timezone.utc).isoformat(),files=manifest,remote_local_sha_match=[len(manifest),len(manifest)],D3_partial_snapshot=True),out,indent=2)
remote_b = r'''
import json,time,os
from pathlib import Path
root=Path('/root/saluki_original_20261009')
p=root/'preservation_state.json'
print(json.dumps(dict(timestamp=time.time(),state=json.loads(p.read_text()) if p.exists() else None,files=[dict(name=q.name,bytes=q.stat().st_size) for q in root.glob('*.gguf*')],memory_usage=Path('/sys/fs/cgroup/memory/memory.usage_in_bytes').read_text().strip())))
'''
b=subprocess.run(['ssh','acopilot-gpu-b','python3 -'],input=remote_b,text=True,encoding='utf-8',capture_output=True,check=True)
with (archive/'B_preservation_capture.json').open('x',encoding='utf-8') as out:
    out.write(b.stdout)
smoke=archive/'saluki_original_smoke12_a1'
summary=json.loads((smoke/'saluki_summary.json').read_text())
print(json.dumps(dict(archive=str(archive),files=len(manifest),smoke=summary,B_preservation=json.loads(b.stdout)),ensure_ascii=False,indent=2))
