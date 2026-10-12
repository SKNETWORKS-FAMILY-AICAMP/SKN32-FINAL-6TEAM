import subprocess,json,pathlib,sys
sys.stdout.reconfigure(encoding='utf-8')
code=r'''
import json,os,time,hashlib
from pathlib import Path
r=Path('/root/daily_rag_20261008');a=Path('/root/adapters/oos2r_finch_5e5_20261008');s=Path('/root/saluki_original_20261009')
files=list(a.glob('*'))+list(r.glob('*finch*'))+list(Path('/root/work').glob('*oos2r_finch_5e5_20261008*'))
print(json.dumps(dict(timestamp=time.time(),finch_files=[dict(path=str(p),size=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()) for p in files if p.is_file()],recipe=json.loads((a/'recipe_complete.json').read_text()),saluki_state=json.loads((s/'preservation_state.json').read_text()),saluki_files=[dict(name=p.name,size=p.stat().st_size) for p in s.glob('*.gguf*')],receiver_alive=Path('/proc/2799499').exists())))
'''
r=subprocess.run(['ssh','acopilot-gpu-b','python3 -'],input=code,text=True,encoding='utf-8',capture_output=True,check=True)
d=json.loads(r.stdout)
p=pathlib.Path(__file__).parent/'B_completion_detail_hb0754_20261009.json'
with p.open('x',encoding='utf-8') as f:json.dump(d,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in d.items() if k!='recipe'},ensure_ascii=False,indent=2))
