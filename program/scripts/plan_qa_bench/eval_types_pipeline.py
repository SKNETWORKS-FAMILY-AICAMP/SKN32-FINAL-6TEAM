# 유형별 종단 채점 — 앞단(학습 임베딩) + 구조 + 넘김 모델 구성이 유형마다 Gemma 26B 직접 짚기와 비교해 어떤지.
#  eval_night.py 의 채점 코드를 그대로 쓴다(문턱 lo·hi 는 heavy 개발용 44 로 고름). 유형당 24문제(heavy 판정 8 + mix4 8 + mix5 8).
# 사용: python eval_types_pipeline.py [넘김 모델 이름 ...]   (기본: gemma4:e4b ftp_z2_gemma_e2b ftp_z2_trida4b gemma4:12b)
import contextlib, io, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
names = sys.argv[1:] or ['gemma4:e4b', 'ftp_z2_gemma_e2b', 'ftp_z2_trida4b', 'gemma4:12b']
src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
head = src[:src.index('rows = []')]
ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
argv_bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'eval_night_head', 'exec'), ns)
sys.argv = argv_bak
SETS, G, run, pipe, grid, dev, IDX = (ns[k] for k in ('SETS', 'G', 'run', 'pipe', 'grid', 'dev', 'IDX'))
types = list(dict.fromkeys(x['type'] for x in SETS['heavy']['qs']))
cols = ['직접:gemma4:26b'] + [f'종단:{n}' for n in names]
cnt = {c: defaultdict(int) for c in cols}
tot = defaultdict(int)
for j in SETS:
    qs = SETS[j]['qs']
    for i in IDX[j]:
        t = qs[i]['type']
        tot[t] += 1
        cnt[cols[0]][t] += G[j]['gemma4:26b'][i] == qs[i]['gold']
for n, c in zip(names, cols[1:]):
    best = max(grid, key=lambda g: (pipe('heavy', dev, *g, n)[0] - 2 * pipe('heavy', dev, *g, n)[1] - 0.05 * pipe('heavy', dev, *g, n)[2], -g[0]))
    for j in SETS:
        qs = SETS[j]['qs']
        for i in IDX[j]:
            p, _ = run(j, i, best[0], best[1], n)
            cnt[c][qs[i]['type']] += p == qs[i]['gold']
print('## 유형별 정답 수(유형당 %d문제) — 26B 직접 대 각 구성의 종단' % (max(tot.values())))
print('| 유형 | ' + ' | '.join(cols) + ' |')
print('|---|' + '---:|' * len(cols))
for t in types:
    print(f'| {t} | ' + ' | '.join(str(cnt[c][t]) for c in cols) + ' |')
print('| **합계** | ' + ' | '.join(f'**{sum(cnt[c].values())}**' for c in cols) + ' |')
