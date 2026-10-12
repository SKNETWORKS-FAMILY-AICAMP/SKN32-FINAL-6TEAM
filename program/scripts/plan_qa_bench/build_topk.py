# 앞단(e16d) 점수로 질문마다 상위 K개 후보 목록을 만든다 — Jev 대체(작은 LLM 이 후보마다 「맞다」 확률을 내는 판정기)의 입력.
#  규칙·앞 대화 단계가 정하는 문제는 제외한다(앞단 자리 문제만). 출력 fixtures/topk_<세트>.json = {문제번호: [항목 번호 K개]}
# 사용: python build_topk.py [K=5] [세트,세트…]   (기본 세트: heavy,mix4,mix5,mix6,mix7,mix8 — mix9 는 앞단 점수가 서버에서 나온 뒤)
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
want = sys.argv[2].split(',') if len(sys.argv) > 2 else ['heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8']
argv0 = sys.argv
sys.argv = ['x', 'e16d'] + (['--final', want[-1]] if want[-1] in ('mix8', 'mix9') and False else [])
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
SETS, S, stage = G0['SETS'], G0['S'], G0['stage']
J = G0['J']
for w in want:
    if w not in SETS:                      # mix8·mix9 는 eval_router 가 기본으로 싣지 않는다 — 점수 파일에서 직접 주입
        SETS[w] = J(os.path.join(HERE, 'fixtures', f'{w}.json'))['sets'][w]
        for p, v in zip(J(os.path.join(HERE, 'fixtures', f'pairs_{w}.json')), J(G0['R'](f'ft_e16d_{w}_scores.json'))['ft/emb_e16d']):
            S[(p['set'], p['qi'])][p['item']] = v
        G0['G'][w] = {M: [None] * len(SETS[w]['qs']) for M in (G0['M'],)}
    out = {}
    for i in range(len(SETS[w]['qs'])):
        if w in G0['LABELED'] or True:
            try:
                st = stage(w, i)
            except KeyError:
                st = ('front',)
        if st[0] != 'front':
            continue
        d = S[(f'{w}_tt', i)]
        out[str(i)] = sorted(d, key=d.get, reverse=True)[:K]
    json.dump(out, open(os.path.join(HERE, 'fixtures', f'topk_{w}.json'), 'w'), ensure_ascii=False)
    gold_in = sum(1 for k, v in out.items() if SETS[w]['qs'][int(k)]['gold'] in v)
    has_gold = sum(1 for k in out if SETS[w]['qs'][int(k)]['gold'] is not None)
    print(w, '앞단 자리 문제', len(out), '· 정답이 있는 것', has_gold, '· 그중 상위', K, '안에 정답', gold_in)
