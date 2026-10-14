from pathlib import Path
from datetime import datetime
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
state=json.loads((Path(__file__).parent/'published-boarding-state-v1.json').read_text(encoding='utf8'))
RAW=ROOT/state['raw'];EV=ROOT/state['evidence'];BASE=ROOT/'datasets/mobility/processed/mobility'
facts=json.loads((RAW/'published-minutes-v1.json').read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out=BASE/'published_boarding_timetable_v1.json'
doc={'schema_version':'1.0','timetable_sha256':sha(BASE/'timetable_v1.jsonl.gz'),'groups':[
 {'line':facts['line'],'station_nm':facts['station'],'day_type':g['day_type'],'dir':g['dir'],
  'minutes':sorted(int(h)*60+m for h,ms in g['hours'].items() for m in ms),
  'complete':True,'source_url':facts['source_url'],'observed_at':state['prepared_at']}
 for g in facts['groups']]}
assert len(doc['groups'])==4 and sum(len(g['minutes']) for g in doc['groups'])==682
with out.open('x',encoding='utf8') as f:json.dump(doc,f,ensure_ascii=False,indent=2)
manifest=BASE/'MANIFEST_git_v1.json';old=json.loads(manifest.read_text(encoding='utf8'))
assert not any(e['path']==out.name for e in old['files'])
old['files'].append({'path':out.name,'class':'A(공표 승차 대조)','bytes':out.stat().st_size,'sha256':sha(out),
 'source_url':facts['source_url'],'source_checked_at':state['prepared_at'],
 'scope':'홍대입구 일반열차 평일·휴일 양방향4그룹682분; 실제 ETA 자료 아님'})
old['totals']['dst_bytes']+=out.stat().st_size
old['published_boarding_added_at']=datetime.now().astimezone().isoformat()
manifest.write_text(json.dumps(old,ensure_ascii=False,indent=1)+'\n',encoding='utf8')
with (EV/'data-build-v1.json').open('x',encoding='utf8') as f:json.dump({'file':out.relative_to(ROOT).as_posix(),'sha256':sha(out),'groups':4,'minutes':682,'base_sha256':doc['timetable_sha256'],'base_unchanged':True},f,ensure_ascii=False,indent=2)
