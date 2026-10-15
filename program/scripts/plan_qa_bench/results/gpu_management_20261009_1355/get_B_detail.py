from pathlib import Path
import subprocess,json,sys
sys.stdout.reconfigure(encoding='utf-8')
here=Path(__file__).parent
code='''from pathlib import Path
import json,hashlib,os
tag='oos2r_finch_5e5_seed20261013_20261008'
w=Path('/root/daily_rag_repeat_20261008');a=Path('/root/adapters')/tag
assert (w/'finch_DONE').is_file()
files=list(a.iterdir())+[w/(tag+'_lora_f16.gguf')]+[w/n for n in ['train_finch.log','convert_finch.log','eval_finch.log','finch_DONE','qlora_train_finch.py','finch_schedule.py','prepared.json']]+list(Path('/root/work').glob('eval_'+tag+'_mix*.json'))
rows=[]
for p in files:
 if p.is_file():
  with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
  rows.append(dict(path=str(p),size=p.stat().st_size,sha256=h))
r=json.loads((a/'recipe_complete.json').read_text());assert r['status']=='completed' and r['optimizer_steps']==654 and r['seed']==20261013
print(json.dumps(dict(files=rows,recipe=r,free_bytes=os.statvfs('/root').f_bavail*os.statvfs('/root').f_frsize)))
'''
r=subprocess.run(['ssh','acopilot-gpu-b','python3 -'],input=code.encode(),capture_output=True,check=True)
data=json.loads(r.stdout)
with (here/'B_finch_seed13_detail.json').open('x',encoding='utf-8') as f:json.dump(data,f,indent=2)
print(json.dumps({'files':len(data['files']),'bytes':sum(x['size'] for x in data['files']),'steps':data['recipe']['optimizer_steps']}))
