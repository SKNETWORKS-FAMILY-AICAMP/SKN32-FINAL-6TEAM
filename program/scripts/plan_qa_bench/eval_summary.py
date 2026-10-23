# 종합 표 — 넘김 모델 후보 전부를 한 표로(직접 짚기·종단 정답·엉뚱한 답·넘김 호출·26B 직접과의 짝지은 차이와 95% 구간).
#  종단 = 학습 임베딩 앞단 + 구조 + 넘김 모델. 문턱 lo·hi 는 eval_night.py 와 같이 넘김 모델마다 heavy 개발용 44 로만 고른다.
#  상주 용량은 올라마 표시 크기(또는 HF 가중치 크기)이며 KV 캐시·앞단(약 1.2GB)은 뺀 값이다 — 아래 SIZE 에 직접 적은 값(외부 표기).
# 사용: python eval_summary.py [--md 출력파일]
import contextlib, io, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
md = sys.argv[sys.argv.index('--md') + 1] if '--md' in sys.argv else None
src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
head = src[:src.index('rows = []')]
ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'eval_night_head', 'exec'), ns)
sys.argv = bak
G, SETS, IDX, run, pipe, grid, dev, models = (ns[k] for k in ('G', 'SETS', 'IDX', 'run', 'pipe', 'grid', 'dev', 'models'))
SIZE = {'gemma4:26b': '18', 'gemma4:26b-a4b-it-qat': '14', 'var_gemma4:26b-a4b-it-q4_K_M|sfx': '18', 'gemma4:12b': '7.6', 'gemma4:12b-it-qat': '7.2',
        'gemma4:e4b': '9.6', 'hint_gemma4:e4b': '9.6', 'gemma4:e4b-it-qat': '6.1', 'var_gemma4:e4b-it-qat|sfx': '6.1', 'var_gemma4:e4b-it-qat|sfx|nofmt': '6.1',
        'gemma4:e4b-it-q8_0': '12', 'gemma4:e2b': '4.6', 'gemma4:e2b-it-qat': '4.3', 'gemma4:e2b-it-bf16': '10', 'var_gemma4:e2b|sfx': '4.6', 'var_gemma4:e2b|sfx|nofmt': '4.6',
        'hint_gemma4:e2b': '4.6', 'restrict_gemma4:e4b': '9.6', 'gepa_e4b': '9.6', 'ftp_z2_gemma_e2b': '약 10', 'ftp_z_gemma_e2b': '약 10', 'ftp_zh_gemma_e2b': '약 10',
        'ftp_f_gemma_e2b': '약 10', 'ftp_g_e2b_lo': '약 10', 'ftp_z2_trida4b': '약 9.6', 'ftp_z_trida4b': '약 9.6', 'ftp_zh_trida4b': '약 9.6', 'ftp_f_trida4b': '약 9.6',
        'ftp_q2b': '약 4', 'ftp_z_lfm26b': '약 5', 'ftp_z_granite42_3b': '약 7'}
J = lambda m: m
base = 'gemma4:26b'
rows = []
for m in models:
    best = max(grid, key=lambda g: (pipe('heavy', dev, *g, m)[0] - 2 * pipe('heavy', dev, *g, m)[1] - 0.05 * pipe('heavy', dev, *g, m)[2], -g[0]))
    d = sum(sum(G[j][m][i] == SETS[j]['qs'][i]['gold'] for i in IDX[j]) for j in SETS)
    p = [pipe(j, IDX[j], *best, m) for j in SETS]
    ok, bad = sum(x[0] for x in p), sum(x[1] for x in p)
    a = b = 0
    for j in SETS:
        qs = SETS[j]['qs']
        for i in IDX[j]:
            pa = run(j, i, best[0], best[1], m)[0] == qs[i]['gold']
            pb = G[j][base][i] == qs[i]['gold']
            a += pa and not pb
            b += pb and not pa
    diffs = [1] * a + [-1] * b + [0] * (264 - a - b)
    rnd = random.Random(20261001)
    bs = sorted(sum(rnd.choice(diffs) for _ in range(264)) / 264 * 100 for _ in range(2000))
    rows.append((m, SIZE.get(m, '?'), d, ok, bad, a, b, (a - b) / 264 * 100, bs[49], bs[1949]))
rows.sort(key=lambda r: -r[3])
out = ['## 종합 표 — 앞단(학습 임베딩 0.6B) + 구조 + 넘김 모델, 세 세트 264문제, 문턱은 heavy 개발용 44 로 선택(넘김 모델마다)',
       '| 넘김 모델 | 상주 GB(앞단 +1.2 별도) | 직접 합 264 | 종단 정답 | 엉뚱한 답 | 종단 − 26B 직접(247): A만:B만 | 차이 %p [95% 구간] |', '|---|---:|---:|---:|---:|---|---|']
for m, sz, d, ok, bad, a, b, df, lo, hi in rows:
    out.append(f'| {m} | {sz} | {d} | **{ok}** | {bad} | {a}:{b} | {df:+.1f} [{lo:+.1f}, {hi:+.1f}] |')
print('\n'.join(out))
if md:
    open(md, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
