# V1(앞단 e16d + E4B QAT) 의 틀린 문제를 원인별로 나눈다 — 규칙이 틀림 / 앞단이 확정했는데 틀림 / 앞단이 「없음」으로 닫음 / LLM 이 틀림.
# 사용: python diag_v1_errors.py → 표준출력
import io, contextlib, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
argv0 = sys.argv
sys.argv = ['x', 'e16d']
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, G, run, pipe, grid, dev, S, stage, LABELED, M = (G0[k] for k in ('SETS', 'G', 'run', 'pipe', 'grid', 'dev', 'S', 'stage', 'LABELED', 'M'))
best = max(grid, key=lambda g: (pipe('heavy', dev, *g, M)[0] - 2 * pipe('heavy', dev, *g, M)[1] - 0.05 * pipe('heavy', dev, *g, M)[2], -g[0]))
lo, hi = best
from collections import Counter
cnt = Counter()
rows = []
for w in LABELED:
    for i, x in enumerate(SETS[w]['qs']):
        if w == 'heavy' and x.get('split') != 'held':
            continue
        p, used = run(w, i, lo, hi, M)
        g = x['gold']
        if p == g:
            continue
        st = stage(w, i)
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        s1 = d[k]
        if st[0] == 'done':
            cause = '규칙/앞 대화 단계' + ('(LLM 호출)' if st[2] else '')
        elif used:
            cause = 'LLM 이 틀림(없음)' if p is None else 'LLM 이 틀림(엉뚱한 항목)'
        elif s1 >= hi:
            cause = '앞단 확정이 틀림'
        else:
            cause = '앞단이 없음으로 닫음'
        cnt[(cause, x['type'])] += 1
        items = {it['id']: it for it in SETS[w]['items']}
        rows.append((w, i, x['type'], cause, round(s1, 2), x['q'], items[g]['title'] if g else None, items[p]['title'] if p else None))
byc = Counter()
for (c, t), n in cnt.items():
    byc[c] += n
print('틀린 문제', sum(byc.values()), dict(byc))
tt = Counter()
for (c, t), n in cnt.items():
    tt[t] += n
print('유형별', dict(tt.most_common()))
for r in rows:
    print(r)
