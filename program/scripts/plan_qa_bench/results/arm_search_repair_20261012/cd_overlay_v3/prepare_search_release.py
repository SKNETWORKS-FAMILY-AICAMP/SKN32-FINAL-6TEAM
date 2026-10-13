"""검증된 최소 ARM 수정 보존. 변경된 develop 파일을 조용히 덮어쓰지 않는다."""
from pathlib import Path
import base64,hashlib,json,os,sys
def prepare(src,manifest):
 data=json.loads(Path(manifest).read_text());src=Path(src)
 for name,row in data.items():
  p=src/name;new=base64.b64decode(row['data']);observed=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
  if row['expected']=='preserve-if-present':
   if p.exists():
    if p.read_bytes()!=new:raise RuntimeError('knowledge changed; review overlay: '+name)
   continue
  if observed not in (row['expected'],hashlib.sha256(new).hexdigest()):raise RuntimeError('source changed; review overlay: '+name)
 for name,row in data.items():
  p=src/name;p.parent.mkdir(parents=True,exist_ok=True);new=base64.b64decode(row['data'])
  if not p.exists() or p.read_bytes()!=new:
   tmp=p.with_name(p.name+'.overlay');tmp.write_bytes(new);os.replace(tmp,p)
  if p.suffix=='.py':compile(p.read_text(encoding='utf-8'),str(p),'exec')
 docker=src/'deploy/Dockerfile.api';text=docker.read_text()
 for line in ['COPY knowledge/ingest.py ./knowledge/ingest.py','COPY knowledge/travel ./knowledge/travel','COPY knowledge/service ./knowledge/service','COPY knowledge/current-travel ./knowledge/current-travel']:
  if line not in text:text+='\n'+line+'\n'
 docker.write_text(text)
 return {'files':len(data),'source_guard':True,'knowledge_in_image':True}
if __name__=='__main__':print(json.dumps(prepare(sys.argv[1],Path(__file__).with_name('search-overlay.json'))))
