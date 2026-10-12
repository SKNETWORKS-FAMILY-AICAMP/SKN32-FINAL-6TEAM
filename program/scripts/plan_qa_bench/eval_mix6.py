# mix6(작성자 Codex 독립 세트) 판정 — 사전 등록(연구 문서 §32)대로: 앞단 ft/emb_e16c · 문턱 lo 0.25 / hi 0.6 고정 · 넘김 = 올라마 E4B QAT · 기준선 = 26B q4_K_M 직접.
#  주 판정 = 종단(E4B QAT) 대 26B 직접의 짝지은 정확도 차이 점추정·95% 구간(복원추출 2000, 시드 20261001). 통과 = 점추정 ≥ −3%p 이고 하한 ≥ −5%p.
#  보조 = 다른 넘김 모델·유형별·기존 264문제와 합친 396문제. 결과를 본 뒤 코드·문턱을 고치지 않는다.
# 사용: python eval_mix6.py [--md 출력파일]
import contextlib, io, json, math, os, random, sys
from collections import defaultdict
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
S, G, SETS, run = ns['S'], ns['G'], ns['SETS'], ns['run']
R = lambda *a: os.path.join(HERE, 'results', *a)
J = lambda f: json.load(open(f, encoding='utf-8'))
LO, HI = 0.25, 0.6
SETS['mix6'] = J(os.path.join(HERE, 'fixtures', 'mix6.json'))['sets']['mix6']
for p, v in zip(J(os.path.join(HERE, 'fixtures', 'pairs_mix6.json')), J(R('ft_e16c_mix6_scores.json'))['ft/emb_e16c']):
    S[(p['set'], p['qi'])][p['item']] = v
G['mix6'] = {}
for m, v in J(R('llm_mix6_out.json')).items():
    if not m.startswith('_') and '#' not in m and isinstance(v, dict) and 'picks' in v:
        G['mix6'][m] = v['picks']
qs = SETS['mix6']['qs']
N = len(qs)
BASE = 'gemma4:26b-a4b-it-q4_K_M'
MAIN = 'gemma4:e4b-it-qat'
cands = [m for m in ['gemma4:e4b-it-qat', 'gemma4:e4b', 'gemma4:e4b-it-q8_0', 'gemma4:12b', 'gemma4:12b-it-qat', BASE, 'gemma4:e2b', 'gemma4:e2b-it-qat'] if m in G['mix6']]


def ci(a, b, n):
    d = [1] * a + [-1] * b + [0] * (n - a - b)
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in range(n)) / n * 100 for _ in range(2000))
    return (a - b) / n * 100, bs[49], bs[1949]


def pexact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


gold = [x['gold'] for x in qs]
base_ok = [G['mix6'][BASE][i] == gold[i] for i in range(N)]
out = [f'## mix6 판정 — {N}문제(정답 null {sum(g is None for g in gold)}), 앞단 + 구조 + 넘김, 문턱 {LO}/{HI} 고정, 기준선 26B q4_K_M 직접 {sum(base_ok)}/{N}']
out += ['| 넘김 모델 | 직접 정답 | 종단 정답 | 엉뚱한 답 | 넘김 호출 | 종단 − 26B 직접: A만:B만 | 차이 %p [95% 구간] | p |', '|---|---:|---:|---:|---:|---|---|---:|']
res = {}
for m in cands:
    preds = []
    calls = 0
    for i in range(N):
        p, used = run('mix6', i, LO, HI, m)
        preds.append(p)
        calls += used
    ok = [preds[i] == gold[i] for i in range(N)]
    bad = sum(preds[i] is not None and preds[i] != gold[i] for i in range(N))
    a = sum(ok[i] and not base_ok[i] for i in range(N))
    b = sum(base_ok[i] and not ok[i] for i in range(N))
    df, lo, hi = ci(a, b, N)
    dd = sum(G['mix6'][m][i] == gold[i] for i in range(N))
    res[m] = (preds, ok, df, lo, hi)
    out.append(f'| {m} | {dd} | **{sum(ok)}** | {bad} | {calls} | {a}:{b} | {df:+.1f} [{lo:+.1f}, {hi:+.1f}] | {pexact(a, b):.2f} |')
if MAIN in res:
    _, ok, df, lo, hi = res[MAIN]
    verdict = '통과' if (df >= -3 and lo >= -5) else '미통과'
    out.append(f'\n**주 판정(E4B QAT 종단 − 26B 직접)**: {df:+.1f}%p [{lo:+.1f}, {hi:+.1f}] → 통과 기준(점추정 ≥ −3 · 하한 ≥ −5) **{verdict}**')
    # 기존 264문제와 합친 396문제
    old = [(j, i) for j in ('heavy', 'mix4', 'mix5') for i in ns['IDX'][j]]
    best = (LO, HI)
    a = b = 0
    for j, i in old:
        g = SETS[j]['qs'][i]['gold']
        pa = run(j, i, best[0], best[1], MAIN)[0] == g
        pb = G[j]['gemma4:26b'][i] == g
        a += pa and not pb
        b += pb and not pa
    ok6 = res[MAIN][1]
    a6 = sum(ok6[i] and not base_ok[i] for i in range(N))
    b6 = sum(base_ok[i] and not ok6[i] for i in range(N))
    d2, l2, h2 = ci(a + a6, b + b6, len(old) + N)
    out.append(f'합친 {len(old) + N}문제(기존 264 + mix6 {N}; 기존 세트 기준선 키는 gemma4:26b — 같은 q4_K_M 가중치로 가정 `[가정]`): 종단(E4B QAT) − 26B 직접 {d2:+.1f}%p [{l2:+.1f}, {h2:+.1f}] (A만 {a + a6} : B만 {b + b6})')
    # 유형별
    types = list(dict.fromkeys(x['type'] for x in qs))
    out += ['', '| 유형 | 문제 | 26B 직접 | 종단(E4B QAT) | E4B QAT 직접 |', '|---|---:|---:|---:|---:|']
    for t in types:
        ii = [i for i in range(N) if qs[i]['type'] == t]
        out.append(f"| {t} | {len(ii)} | {sum(base_ok[i] for i in ii)} | {sum(ok[i] for i in ii)} | {sum(G['mix6'][MAIN][i] == gold[i] for i in ii)} |")
print('\n'.join(out))
if md:
    open(md, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
