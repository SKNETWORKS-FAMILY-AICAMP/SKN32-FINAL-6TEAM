from pathlib import Path
import subprocess,json,hashlib,tarfile,io,shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
here=Path(__file__).parent;root=Path.cwd();detail=json.loads((here/'B_finch_seed13_detail.json').read_text())
assert shutil.disk_usage(root).free>sum(x['size'] for x in detail['files'])*3+2**30
code='''import io,json,tarfile,sys,hashlib
from pathlib import Path
files='''+repr(detail['files'])+'''
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w:gz') as t:
 for row in files:
  p=Path(row['path']);data=p.read_bytes()
  assert len(data)==row['size'] and hashlib.sha256(data).hexdigest()==row['sha256']
  e=tarfile.TarInfo(p.name);e.size=len(data);t.addfile(e,io.BytesIO(data))
sys.stdout.buffer.write(b.getvalue())
'''
r=subprocess.run(['ssh','acopilot-gpu-b','python3 -'],input=code.encode(),capture_output=True,check=True)
with (here/'B_finch_seed13.tar.gz').open('xb') as f:f.write(r.stdout)
out=here/'B_finch_seed13';out.mkdir()
with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
 for m in t.getmembers():
  assert m.isfile() and (out/m.name).resolve().is_relative_to(out.resolve())
  with (out/m.name).open('xb') as f:f.write(t.extractfile(m).read())
weights=root/'datasets/travel/train_oos/oos2r_finch_5e5_seed20261013_20261009';weights.mkdir(exist_ok=False)
rows=[]
for meta in detail['files']:
 p=out/Path(meta['path']).name
 assert p.stat().st_size==meta['size'] and hashlib.sha256(p.read_bytes()).hexdigest()==meta['sha256']
 if '/root/adapters/' in meta['path'] or p.suffix=='.gguf':shutil.copy2(p,weights/p.name)
 rows.append(dict(local=str(p.relative_to(root)).replace('\\','/'),**meta))
with (here/'B_verification.json').open('x') as f:json.dump({'files':[len(rows),len(rows)],'rows':rows,'recipe':detail['recipe']},f,indent=2)
gguf=next(weights.glob('*.gguf'));sha=hashlib.sha256(gguf.read_bytes()).hexdigest()
remote='/tmp/tripilot-trained-adapters-20261008/finch_s20261013_lora_f16.gguf'
check="from pathlib import Path;import os; p=Path('"+remote+"');assert not p.exists();assert os.statvfs('/tmp').f_bavail*os.statvfs('/tmp').f_frsize>3*2**30+"+str(gguf.stat().st_size+100*2**20)
subprocess.run(['ssh','acopilot-gpu','python3 -'],input=check.encode(),check=True)
subprocess.run(['scp','-q',str(gguf),'acopilot-gpu:'+remote],check=True)
with (here/'adapter_transfer.json').open('x') as f:json.dump({'adapter':str(gguf.relative_to(root)).replace('\\','/'),'remote':remote,'sha256':sha,'bytes':gguf.stat().st_size},f,indent=2)
print(json.dumps({'files':len(rows),'gguf_sha256':sha,'bytes':gguf.stat().st_size}))
