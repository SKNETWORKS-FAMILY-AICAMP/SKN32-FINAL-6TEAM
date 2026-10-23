import json, glob, re
B = 'C:/Users/playdata2/Documents/final_workspace/datasets/travel/plan_samples/korea/seoul/gold/'
O = B + 'pilot12_20261023/_AI라벨_사람라벨후열기/'
drafts = {}
for f in glob.glob(B + 'v1/draft_claude/batch_*.jsonl'):
    for l in open(f, encoding='utf-8'):
        if l.strip():
            d = json.loads(l); drafts[d['plan_id']] = d
key = json.load(open(B + 'pilot12_20261023/_층화키_라벨후열기.json', encoding='utf-8'))['items']
pid2plan = {k['pilot_id']: k['plan_id'] for k in key}
def norm(s): return re.sub(r'[\s\W_]+', '', (s or '').lower())
def pl(d): return [(day['day'], norm(it['place'])) for day in d.get('days', []) for it in day['items']]
def match(a, b):
    used = set(); m = 0
    for da, pa in a:
        for j, (db, pb) in enumerate(b):
            if j in used or da != db: continue
            if pa == pb or (len(pa) >= 2 and len(pb) >= 2 and (pa in pb or pb in pa)):
                used.add(j); m += 1; break
    return m
res = {}
for who in ('claude', 'codex'):
    tm = tc = td = 0; dt = 0; sc = 0; n = 0; same_ev = 0
    for pid, plan in pid2plan.items():
        L = json.load(open(O + 'ai_%s_%s.json' % (who, pid), encoding='utf-8'))
        dr = drafts[plan]
        a, b = pl(L), pl(dr)
        tm += match(a, b); tc += len(a); td += len(b)
        dt += L['doc_type'] == dr['doc_type']; sc += L['city_scope'] == dr['city_scope']; n += 1
    res[who] = {'새 라벨 항목': tc, '옛 Claude 초안 항목': td, '일차+장소로 맞춘 수': tm, 'doc_type 같음': '%d/%d' % (dt, n), 'city_scope 같음': '%d/%d' % (sc, n)}
print(json.dumps(res, ensure_ascii=False, indent=1))
