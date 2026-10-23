import json, os, re, sys
BASE = 'C:/Users/playdata2/Documents/final_workspace/datasets/travel/plan_samples/korea/seoul/gold/pilot12_20261023/'
RUN = 'C:/Users/PLAYDA~1/AppData/Local/Temp/claude/C--Users-playdata2-Documents-final-workspace/393ad054-3d33-4557-ac71-4cd1cf6e6401/scratchpad/ai_run/'
OUT = BASE + '_AI라벨_사람라벨후열기/'
os.makedirs(OUT, exist_ok=True)
posts = {}
for l in open(BASE + 'pilot12_inputs.jsonl', encoding='utf-8'):
    if l.strip():
        p = json.loads(l); posts[p['pilot_id']] = p
IDS = sorted(posts)
TIME = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')
BASIS = {'explicit', 'slot:breakfast', 'slot:morning', 'slot:lunch', 'slot:afternoon', 'slot:dinner', 'slot:evening', 'slot:night', 'none'}
KINDS = {'식사', '활동', '숙소', '이동', '기타', None}
DOC = {'plan', 'review', 'mixed', 'not_itinerary'}
SCOPE = {'seoul', 'seoul+other', 'other'}

def norm(s):
    return re.sub(r'[\s\W_]+', '', (s or '').lower())

def extract_json(txt):
    t = txt.strip()
    t = re.sub(r'^```(?:json)?\s*', '', t)
    t = re.sub(r'\s*```\s*$', '', t)
    a, b = t.find('{'), t.rfind('}')
    if a < 0 or b < 0:
        raise ValueError('no json object')
    return json.loads(t[a:b + 1])

def validate(pid, d):
    errs = []
    if d.get('pilot_id') != pid: errs.append('pilot_id 불일치 %r' % d.get('pilot_id'))
    if d.get('doc_type') not in DOC: errs.append('doc_type %r' % d.get('doc_type'))
    if d.get('city_scope') not in SCOPE: errs.append('city_scope %r' % d.get('city_scope'))
    td = d.get('trip_days')
    if not (td is None or (isinstance(td, int) and td >= 1)): errs.append('trip_days %r' % td)
    if 'ambiguities' not in d: errs.append('ambiguities 없음')
    days = d.get('days')
    if not isinstance(days, list): errs.append('days 가 목록이 아님'); return errs
    for di, day in enumerate(days):
        if not isinstance(day.get('day'), int): errs.append('days[%d].day' % di)
        items = day.get('items')
        if not isinstance(items, list): errs.append('days[%d].items' % di); continue
        for ii, it in enumerate(items):
            w = 'd%s#%d' % (day.get('day'), ii + 1)
            if it.get('order') != ii + 1: errs.append(w + ' order 연속 아님(%r)' % it.get('order'))
            if not (it.get('place') or '').strip(): errs.append(w + ' place 비어 있음')
            if not (it.get('evidence') or '').strip(): errs.append(w + ' evidence 비어 있음')
            for k in ('time_start', 'time_end'):
                v = it.get(k)
                if v is not None and not TIME.match(str(v)): errs.append(w + ' %s 형식 %r' % (k, v))
            if it.get('time_basis') not in BASIS: errs.append(w + ' time_basis %r' % it.get('time_basis'))
            if it.get('time_start') and it.get('time_basis') != 'explicit': errs.append(w + ' 시각이 있는데 explicit 아님')
            if it.get('time_basis') == 'explicit' and not it.get('time_start'): errs.append(w + ' explicit 인데 시작 시각 없음')
            if it.get('kind') not in KINDS: errs.append(w + ' kind %r' % it.get('kind'))
    return errs

def fabricated_places(pid, d):
    txt = norm(posts[pid]['text'] + ' ' + posts[pid]['title'])
    bad = []
    for day in d.get('days', []):
        for it in day.get('items', []):
            n = norm(it.get('place'))
            if n and n not in txt: bad.append(it.get('place'))
    return bad

report = {'labelers': {}}
labels = {}
for who, folder, ext in (('claude', 'claude_out', '.json'), ('codex', 'codex_out', '.txt')):
    ok, fail = 0, []
    labels[who] = {}
    for pid in IDS:
        path = RUN + folder + '/' + pid + ext
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            fail.append((pid, '출력 파일 없음')); continue
        try:
            d = extract_json(open(path, encoding='utf-8').read())
        except Exception as e:
            fail.append((pid, '파싱 실패: %s' % e)); continue
        errs = validate(pid, d)
        fab = fabricated_places(pid, d)
        meta = {'labeler': 'claude (subagent, Claude Code, 모델 별칭 상속)' if who == 'claude' else 'codex (본계정 CLI, gpt-6-sol)',
                'labeler_type': 'ai', 'mode': 'blind', 'ai_draft_seen': False, 'elapsed_sec': None}
        d['meta'] = meta
        d['_check'] = {'schema_errors': errs, 'places_not_in_source_text': fab}
        open(OUT + 'ai_%s_%s.json' % (who, pid), 'w', encoding='utf-8', newline='\n').write(json.dumps(d, ensure_ascii=False, indent=1))
        labels[who][pid] = d
        ok += 1
    report['labelers'][who] = {'saved': ok, 'failed': fail,
        'schema_error_posts': {pid: d['_check']['schema_errors'] for pid, d in labels[who].items() if d['_check']['schema_errors']},
        'posts_with_places_not_in_text': {pid: d['_check']['places_not_in_source_text'] for pid, d in labels[who].items() if d['_check']['places_not_in_source_text']}}

# 집계만(개별 글 라벨은 사람 라벨 전에 공개하지 않는다)
both = [p for p in IDS if p in labels.get('claude', {}) and p in labels.get('codex', {})]
def agree(f):
    return sum(1 for p in both if labels['claude'][p].get(f) == labels['codex'][p].get(f))
def places(d):
    return [(day['day'], norm(it['place'])) for day in d['days'] for it in day['items']]
def matched(a, b):
    used = set(); m = 0
    for (da, pa) in a:
        for j, (db, pb) in enumerate(b):
            if j in used or da != db: continue
            if pa == pb or (len(pa) >= 2 and len(pb) >= 2 and (pa in pb or pb in pa)):
                used.add(j); m += 1; break
    return m
tot_c = tot_x = tot_m = 0
for p in both:
    a, b = places(labels['claude'][p]), places(labels['codex'][p])
    tot_c += len(a); tot_x += len(b); tot_m += matched(a, b)
report['claude_vs_codex_aggregate'] = {
    'posts_both': len(both),
    'doc_type_same': '%d/%d' % (agree('doc_type'), len(both)),
    'city_scope_same': '%d/%d' % (agree('city_scope'), len(both)),
    'trip_days_same': '%d/%d' % (agree('trip_days'), len(both)),
    'items_claude': tot_c, 'items_codex': tot_x, 'items_matched_by_place_and_day(v0 규칙)': tot_m}
open(OUT + '_검증요약.json', 'w', encoding='utf-8', newline='\n').write(json.dumps(report, ensure_ascii=False, indent=1))
print(json.dumps(report, ensure_ascii=False, indent=1))
