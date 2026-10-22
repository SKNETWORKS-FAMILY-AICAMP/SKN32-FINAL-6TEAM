import json,glob,random,re,sys,os
SEED=20261023
base='C:/Users/playdata2/Documents/final_workspace/datasets/travel/plan_samples/korea/seoul/gold/v1/'
rows={}
for l in open(base+'sample.jsonl',encoding='utf-8'):
    if l.strip():
        r=json.loads(l); rows[r['plan_id']]=r
drafts={}
for f in sorted(glob.glob(base+'draft_claude/batch_*.jsonl')):
    for l in open(f,encoding='utf-8'):
        if l.strip():
            d=json.loads(l); drafts[d['plan_id']]=d
tre=re.compile(r'(\d{1,2}\s*[:：]\s*\d{2})|((오전|오후|am|pm|AM|PM)\s*\d{1,2}\s*(시|am|pm)?)|(\b\d{1,2}\s*(am|pm|AM|PM)\b)|(\d{1,2}\s*시(\s*\d{1,2}\s*분|\s*반)?)')
def cell(r,d):
    t=r['text']; src='reddit' if r['source']=='reddit' else ('blog' if r['source']=='naver_blog' else None)
    many='many' if len(tre.findall(t))>=3 else 'few'
    return (src,d['doc_type'],many)
elig={}
for pid,r in rows.items():
    d=drafts[pid]
    if d['city_scope'] not in ('seoul','seoul+other'): continue
    if r.get('text_truncated') in (True,'True') or len(r['text'])>5000 or len(r['text'])<300: continue
    c=cell(r,d)
    if c[0] is None: continue
    elig.setdefault(c,[]).append(pid)
plan=[(('reddit','plan','many'),2),(('reddit','plan','few'),2),(('blog','plan','many'),2),(('blog','plan','few'),1),
      (('blog','review','many'),1),(('blog','review','few'),1),(('reddit','review','few'),1),
      (('reddit','not_itinerary','few'),1),(('blog','not_itinerary','many'),1)]
rng=random.Random(SEED)
chosen=[]
for c,n in plan:
    pool=sorted(elig.get(c,[]))
    print(c,'eligible',len(pool),file=sys.stderr)
    if len(pool)<n: raise SystemExit('not enough '+str(c))
    for pid in rng.sample(pool,n): chosen.append((pid,c))
rng.shuffle(chosen)
print(len(chosen),file=sys.stderr)
relabel=sorted(rng.sample(range(len(chosen)),3))
out=os.environ['OUT']; os.makedirs(out,exist_ok=True)
inputs=[];key=[]
for i,(pid,c) in enumerate(chosen,1):
    r=rows[pid]; d=drafts[pid]; pidn=f'P{i:02d}'
    inputs.append({'pilot_id':pidn,'plan_id':pid,'title':r['title'],'text':r['text']})
    key.append({'pilot_id':pidn,'plan_id':pid,'source':c[0],'draft_doc_type_claude_v1':c[1],'time_density_rule':c[2],'draft_city_scope_claude_v1':d['city_scope'],'chars':len(r['text']),'source_url':r['source_url'],'relabel_after_24h':(i-1) in relabel})
with open(out+'/pilot12_inputs.jsonl','w',encoding='utf-8',newline='\n') as f:
    for x in inputs: f.write(json.dumps(x,ensure_ascii=False)+'\n')
json.dump({'seed':SEED,'pool':'gold/v1/sample.jsonl 196건 중 Claude 초안 기준 서울·서울+다른지역, 5000자 이하, 잘림 없음','note':'라벨 전에 열지 말 것(층·초안 글 종류가 보임)','items':key},open(out+'/_층화키_라벨후열기.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
import csv
with open(out+'/표본목록.csv','w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f); w.writerow(['pilot_id','plan_id','출처','글자수','원문주소','제목'])
    for k,x in zip(key,inputs): w.writerow([k['pilot_id'],k['plan_id'],k['source'],k['chars'],k['source_url'],x['title']])
print('done',[ (k['pilot_id'],k['source'],k['chars']) for k in key],file=sys.stderr)
print('relabel',[key[i]['pilot_id'] for i in relabel],file=sys.stderr)
