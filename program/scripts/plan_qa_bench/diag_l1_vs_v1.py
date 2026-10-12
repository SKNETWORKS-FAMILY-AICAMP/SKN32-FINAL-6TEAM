# mix8 에서 「규칙 → E4B QAT(앞단 없음, L1)」과 「앞단 e16d + E4B QAT(V1)」가 다르게 맞힌 문제를 원인과 함께 본다(사후 진단 — 방식을 바꾸지 않는다).
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
argv0 = sys.argv
sys.argv = ['x', 'e16d', '--final', 'mix8']
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, G, S, run, pipe, grid, dev, stage, M = (G0[k] for k in ('SETS', 'G', 'S', 'run', 'pipe', 'grid', 'dev', 'stage', 'M'))
best = max(grid, key=lambda g: (pipe('heavy', dev, *g, M)[0] - 2 * pipe('heavy', dev, *g, M)[1] - 0.05 * pipe('heavy', dev, *g, M)[2], -g[0]))
lo, hi = best
w = 'mix8'
items = {i['id']: i for i in SETS[w]['items']}
t = lambda k: items[k]['title'] if k else None
front_none = front_acc = rule = 0
rows = []
for i, x in enumerate(SETS[w]['qs']):
    g = x['gold']
    st = stage(w, i)
    l1 = st[1] if st[0] == 'done' else G[w][M][i]
    v1, used = run(w, i, lo, hi, M)
    if st[0] == 'front':
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        how = '앞단 확정' if d[k] >= hi else ('앞단 없음으로 닫음' if d[k] < lo else 'LLM 넘김')
        s1 = round(d[k], 2)
    else:
        how, s1 = '규칙·앞 대화', None
    if (l1 == g) != (v1 == g):
        rows.append(('L1만 맞음' if l1 == g else 'V1만 맞음', x['type'], how, s1, x['q'], t(g), t(l1), t(v1)))
from collections import Counter
print(Counter((r[0], r[2]) for r in rows))
for r in rows:
    print(r)
