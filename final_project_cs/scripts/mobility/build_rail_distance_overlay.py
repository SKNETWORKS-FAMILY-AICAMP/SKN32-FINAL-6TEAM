"""CSV 방향을 운영기관·선명별로 대조한다. 관측이 부족하거나 방향을 가를 수 없으면 채우지 않는다."""
import json,csv,re,gzip,collections,statistics,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];sys.stdout.reconfigure(encoding='utf8')
p=root/'datasets/mobility/raw/official_distance_20261008';m=root/'datasets/mobility/processed/mobility'
doc=json.loads((m/'line_station_order_v1.json').read_text(encoding='utf8'))
def norm(s):
 s=re.split(r'[（(]',s)[0].strip();return s[:-1] if s.endswith('역') else s
def ln(s):
 s=s.strip();mt=re.search(r'^([1-9])호선',s)
 return f'0{mt[1]}호선' if mt else {'경의중앙':'경의선','수인':'수인분당선','수인분당':'수인분당선','분당':'수인분당선','신분당':'신분당선','경춘':'경춘선','경강':'경강선','우이신설':'우이신설경전철','서해':'서해선','공항':'공항철도','에버라인':'용인경전철','의정부':'의정부경전철','인천1호선':'인천선'}.get(s,s)
def key(line,a,b):return line,frozenset([norm(a),norm(b)])
edges={key(line,e['a'],e['b']):e for line,d in doc['lines'].items() for e in d['edges']}
track={key(r['line'],r['a'],r['b']):r['track_m'] for r in map(json.loads,gzip.open(m/'rail_edge_track_v2.jsonl.gz','rt',encoding='utf8')) if r.get('track_m')}
votes=collections.defaultdict(list);groups_out=[]
for src in json.loads((p/'manifest-v2.json').read_text(encoding='utf8'))['sources']:
 data=(p/(src['id']+'.csv')).read_bytes();text=data.decode('utf-8-sig') if data.startswith(b'\xef\xbb\xbf') else data.decode('cp949')
 rows=list(csv.DictReader(text.splitlines()));cols=list(rows[0]);dist=next(c for c in cols if '역간거리' in c and '후행' not in c)
 groups=collections.defaultdict(list)
 for a,b in zip(rows,rows[1:]):
  line=ln(a['선명']);k=key(line,a['역명'],b['역명'])
  if k not in edges or a['선명']!=b['선명'] or a['철도운영기관명']!=b['철도운영기관명']:continue
  vals={}
  for side,row in [('left',a),('right',b)]:
   try:val=round(float(row[dist])*1000)
   except ValueError:continue
   if val>0:vals[side]=val
  groups[(a['철도운영기관명'],a['선명'])].append((k,vals))
 for group,pairs in groups.items():
  stats={}
  for side in ['left','right']:
   anchor=[abs(vals[side]-edges[k]['distance_m'])/edges[k]['distance_m'] for k,vals in pairs if side in vals and edges[k].get('distance_m')]
   geo=[abs(vals[side]-track[k])/track[k] for k,vals in pairs if side in vals and k in track]
   stats[side]={'anchor_n':len(anchor),'anchor_mae':statistics.mean(anchor) if anchor else None,'track_n':len(geo),'track_mae':statistics.mean(geo) if geo else None}
  pick=None;kind=None
  for field,count,limit,margin in [('anchor_mae','anchor_n',.05,.10),('track_mae','track_n',.12,.10)]:
   good=[s for s in stats if stats[s][count]>=3 and stats[s][field] is not None]
   if len(good)!=2:continue
   best=min(good,key=lambda s:stats[s][field]);other='right' if best=='left' else 'left'
   if stats[best][field]<=limit and stats[other][field]-stats[best][field]>=margin:
    pick=best;kind=field;break
  groups_out.append({'source_id':src['id'],'group':group,'pick':pick,'basis':kind,'stats':stats})
  if pick:
   for k,vals in pairs:
    if pick in vals:votes[k].append({'m':vals[pick],'source_id':src['id'],'orientation':pick,'basis':kind})
allowed={f'0{i}호선' for i in range(1,10)}|{'경의선','수인분당선','경춘선','경강선','서해선'}
out=[];conflicts=[]
for k,vs in votes.items():
 if k[0] not in allowed:continue
 e=edges[k]
 if e.get('distance_m'):continue
 values={v['m'] for v in vs}
 if len(values)!=1:conflicts.append({'line':k[0],'a':e['a'],'b':e['b'],'votes':vs});continue
 # 방향이 추정인 공표값은 확정 거리로 승격하지 않는다. 기존 추정망의 오차 규칙을 그대로 적용한다.
 out.append({'line':k[0],'a':e['a'],'b':e['b'],'distance_m':values.pop(),'grade':'공표값·대응방향 추정','sources':vs})
result={'created_at':__import__('datetime').datetime.now().astimezone().isoformat(),'purpose':'공표 거리의 대응 방향을 기존 거리·선로와 대조한 보강. 확정 운임거리가 아님','sources_sha256':{s['id']:s['sha256'] for s in json.loads((p/'manifest-v2.json').read_text(encoding='utf8'))['sources']},'edges':out,'conflicts':conflicts,'groups':groups_out}
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
if not args.out.resolve().is_relative_to((root/'datasets/mobility').resolve()):parser.error('출력은 datasets/mobility 아래 새 파일이어야 합니다')
with args.out.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print('보강',len(out),'충돌',len(conflicts),'방향 미확정',sum(g['pick'] is None for g in groups_out),'그룹',len(groups_out))
print(dict(collections.Counter(r['line'] for r in out)))
