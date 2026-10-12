# 앞단(e16d)의 「대상 절(tt)」 점수로 문제마다 상위 K개 힌트 목록을 만든다 — hints_<세트>.json = {"top": [[항목 번호 K개] …문제 순서]}.
#  앞단 점수가 없는(대상 절이 없는) 문제는 빈 목록. 로컬·서버 어디서든 돈다(pairs 파일 + 점수 파일만 읽는다).
# 사용: python build_hints.py [K=5] [세트,세트…]   (기본: heavy,mix4,mix5,mix6,mix7,mix8 — 로컬 fixtures/results 기준)
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
WANT = sys.argv[2].split(',') if len(sys.argv) > 2 else ['heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8']
FX = os.path.join(HERE, 'fixtures') if os.path.isdir(os.path.join(HERE, 'fixtures')) else HERE
RS = os.path.join(HERE, 'results') if os.path.isdir(os.path.join(HERE, 'results')) else HERE
J = lambda f: json.load(open(f, encoding='utf-8'))
for w in WANT:
    nq = len(J(os.path.join(FX, f'{w}.json'))['sets'][w]['qs'])
    if w in ('heavy', 'mix4'):
        pairs, sc = J(os.path.join(FX, 'pairs_experts.json')), J(os.path.join(RS, 'ft_e16d_scores.json'))['ft/emb_e16d']
    elif w == 'mix5':
        pairs, sc = J(os.path.join(FX, 'pairs_mix5.json')), J(os.path.join(RS, 'ft_e16d_mix5_scores.json'))['ft/emb_e16d']
    else:
        pairs, sc = J(os.path.join(FX, f'pairs_{w}.json')), J(os.path.join(RS, f'ft_e16d_{w}_scores.json'))['ft/emb_e16d']
    by = {}
    for p, v in zip(pairs, sc):
        if p['set'] == f'{w}_tt':
            by.setdefault(p['qi'], {})[p['item']] = v
    top = [sorted(by[i], key=by[i].get, reverse=True)[:K] if i in by else [] for i in range(nq)]
    json.dump({'top': top}, open(os.path.join(FX if FX != HERE else HERE, f'hints_{w}.json'), 'w'), ensure_ascii=False)
    print(w, '문제', nq, '· 힌트 있는 문제', sum(1 for t in top if t))
