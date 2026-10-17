# 증류 파일럿 학습 자료 변환·검증 — Claude 하위 작업이 낸 JSON(gen_pXX.json)을 fixtures/distill/distill_pXX.json 으로 바꾸고 검증 보고를 낸다.
#  검증: 형식 · 정답 키 존재 · 유형별 개수 · 문장 중복 · 정답 null 비율 · 요청 둘 gold_set(둘 다 일정에 있고 첫 항목 = gold) · 평가 세트(heavy~mix12)와 문장 겹침 · 장소 겹침.
#  평가와 겹치는 문제는 제외하지 않고 보고만 한다(어느 문제인지 남김) — 제외는 build 단계가 아니라 학습 자료 조립 단계에서 한다.
# 사용: python build_distill.py <gen 폴더> p01 p02 ...   → fixtures/distill/distill_<id>.json · results/distill_build_report.json
import glob, json, os, re, sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
GEN = sys.argv[1]
PIDS = sys.argv[2:]
OUT = os.path.join(HERE, 'fixtures', 'distill')
os.makedirs(OUT, exist_ok=True)
EVAL = ['heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9', 'mix10', 'mix11', 'mix12']
ev_q, ev_place = set(), set()
for w in EVAL:
    f = fixture(f'{w}.json')
    if os.path.exists(f):
        s = json.load(open(f, encoding='utf-8'))['sets'][w]
        ev_q |= {re.sub(r'\s+', '', q['q']) for q in s['qs']}
        ev_place |= {i['place'].replace(' ', '') for i in s['items']}
TYPES = ['context_pronoun', 'duplicate_place', 'confusable_name', 'compound_intent', 'negation', 'typo_slang', 'out_of_scope', 'nameless_description', 'ordinal_relative', 'change_request', 'absent_but_plausible']
report = {}
for pid in PIDS:
    raw = open(os.path.join(GEN, f'gen_{pid}.json'), encoding='utf-8').read()
    d = json.loads(re.search(r'\{.*\}', raw, re.S).group(0))
    dates = d['dates']
    RAW = sorted(d['itinerary'], key=lambda r: (r['day'], r['start']))
    ID = {r['key']: n + 1 for n, r in enumerate(RAW)}
    problems = []
    if len(ID) != len(RAW):
        problems.append('일정 키 중복')
    if len(dates) != 7:
        problems.append('날짜 7개 아님')
    items = [{'id': ID[r['key']], 'date': dates[r['day']], 'start': r['start'], 'kind': r['kind'], 'title': r['title'], 'place': r['place']} for r in RAW]
    qs, seen, bad = [], set(), []
    for x in d['questions']:
        if x['q'] in seen:
            bad.append((x['q'], '문장 중복'))
            continue
        if x['gold'] is not None and x['gold'] not in ID:
            bad.append((x['q'], f"정답 키 없음 {x['gold']}"))
            continue
        gs = None
        if x['type'] == 'compound_intent':
            gl = x.get('gold_set')
            if not gl or any(k not in ID for k in gl) or len(set(gl)) < 2 or gl[0] != x['gold']:
                bad.append((x['q'], f'gold_set 이상 {gl}'))
                continue
            gs = [ID[k] for k in gl]
        seen.add(x['q'])
        h = x.get('history') or []
        qs.append({'q': x['q'], 'gold': ID[x['gold']] if x['gold'] else None, 'gold_set': gs, 'type': x['type'], 'split': 'train',
                   'history': [{'role': 'customer' if k % 2 == 0 else 'service', 'text': t} for k, t in enumerate(h)]})
    cnt = Counter(q['type'] for q in qs)
    q_overlap = [q['q'] for q in qs if re.sub(r'\s+', '', q['q']) in ev_q]
    p_overlap = sorted({i['place'] for i in items if i['place'].replace(' ', '') in ev_place})
    name = f'distill_{pid}'
    json.dump({'sets': {name: {'today': d['today'], 'items': items, 'qs': qs}}}, open(os.path.join(OUT, f'{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    nnull = sum(q['gold'] is None for q in qs)
    report[pid] = {'items': len(items), 'questions': len(qs), 'null_ratio': round(nnull / max(1, len(qs)), 3), 'by_type': dict(cnt), 'type_bad': {t: n for t, n in cnt.items() if n != 16},
                   'missing_types': [t for t in TYPES if t not in cnt], 'dropped': bad, 'problems': problems, 'eval_question_overlap': q_overlap, 'eval_place_overlap': p_overlap}
    print(pid, '항목', len(items), '· 문제', len(qs), '· null', f'{100 * nnull / max(1, len(qs)):.0f}%', '· 버림', len(bad), '· 평가 문장 겹침', len(q_overlap), '· 평가 장소 겹침', len(p_overlap), '· 유형 이상', report[pid]['type_bad'] or '없음')
json.dump(report, open(os.path.join(HERE, 'results', 'distill_build_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
tot = sum(r['questions'] for r in report.values())
print('합계', tot, '문제 ·', len(report), '여행자')
