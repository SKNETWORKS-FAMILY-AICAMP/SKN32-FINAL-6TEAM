import json, sys
from datetime import date
SP = sys.argv[1]
sys.path.insert(0, SP)
from recog_v2 import Recognizer, RecognizerV3, RecognizerV4, emb
cats = json.load(open(SP + '/kakao_cats.json', encoding='utf-8'))
ov = json.load(open(SP + '/tour_overview.json', encoding='utf-8'))
cx = json.load(open(SP + '/codex_qset.json', encoding='utf-8'))
q2 = json.load(open(SP + '/codex_qset2.json', encoding='utf-8'))['questions']
today = date.fromisoformat(cx['today'])
sets = [('새 질문 40', q2), ('시험용 50(재확인)', [x for n, x in enumerate(cx['questions']) if n % 2 == 1])]
Rs = [('v2', Recognizer(cx['itinerary'], cats, today)), ('v3', RecognizerV3(cx['itinerary'], cats, today, SP + '/alias_cache.json')),
      ('v4', RecognizerV4(cx['itinerary'], cats, today, SP + '/alias_cache.json', ov))]
from collections import Counter
for name, QS in sets:
    QV = emb([x['q'] for x in QS])
    for lab, R in Rs:
        for tau in (0.50, 0.55):
            out = [R.pick(x['q'], qv, tau) for x, qv in zip(QS, QV)]
            ok = sum(o == x['gold'] for o, x in zip(out, QS))
            wrong = sum(o is not None and x['gold'] is not None and o != x['gold'] for o, x in zip(out, QS))
            fp = sum(o is not None and x['gold'] is None for o, x in zip(out, QS))
            nn = sum(x['gold'] is None for x in QS)
            miss = sum(o is None and x['gold'] is not None for o, x in zip(out, QS))
            by = Counter(); tot = Counter()
            for o, x in zip(out, QS):
                tot[x['type']] += 1; by[x['type']] += (o == x['gold'])
            print(f"[{name}] {lab} τ={tau}: 맞음 {ok}/{len(QS)}={ok/len(QS):.0%} · 틀린 항목 {wrong} · 없는 질문 오짚음 {fp}/{nn} · 못 찾음 {miss}")
            if name == '새 질문 40' and tau == 0.55:
                print('      종류별', {t: f'{by[t]}/{tot[t]}' for t in tot})
