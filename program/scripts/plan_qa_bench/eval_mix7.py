# mix7(작성자 Codex 독립 세트, 176문제) 판정 — 사전 등록(연구 문서 §33)대로: 주 = lo 0.10 / hi 0.6, 비교 = lo 0.25. 넘김 = 올라마 E4B QAT, 기준선 = 26B q4_K_M 직접.
#  통과 = 종단(lo 0.10) 대 26B 직접의 짝지은 차이 점추정 ≥ −3%p 이고 95% 구간 하한 ≥ −5%p. 보조 = lo 0.10 대 0.25 · mix6 과 합친 306 · 기존 264 까지 합친 570.
#  결과를 본 뒤 코드·문턱을 고치지 않는다.
# 사용: python eval_mix7.py [--md 출력파일]
import contextlib, io, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
md = sys.argv[sys.argv.index('--md') + 1] if '--md' in sys.argv else None
src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
head = src[:src.index('rows = []')]
ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'eval_night_head', 'exec'), ns)
sys.argv = bak
S, G, SETS, run, IDX = ns['S'], ns['G'], ns['SETS'], ns['run'], ns['IDX']
R = lambda *a: os.path.join(HERE, 'results', *a)
J = lambda f: json.load(open(f, encoding='utf-8'))
for w in ('mix6', 'mix7'):
    SETS[w] = J(fixture(f'{w}.json'))['sets'][w]
    for p, v in zip(J(os.path.join(HERE, 'fixtures', f'pairs_{w}.json')), J(R(f'ft_e16c_{w}_scores.json'))['ft/emb_e16c']):
        S[(p['set'], p['qi'])][p['item']] = v
    G[w] = {}
    if os.path.exists(R(f'llm_{w}_out.json')):
        for m, v in J(R(f'llm_{w}_out.json')).items():
            if not m.startswith('_') and '#' not in m and isinstance(v, dict) and 'picks' in v:
                G[w][m] = v['picks']
BASE, MAIN, HI = 'gemma4:26b-a4b-it-q4_K_M', 'gemma4:e4b-it-qat', 0.6
cands = [m for m in [MAIN, 'gemma4:e4b', 'gemma4:12b', 'gemma4:12b-it-qat', BASE, 'gemma4:e2b', 'gemma4:e4b-it-q8_0'] if m in G['mix7']]


def ci(a, b, n):
    d = [1] * a + [-1] * b + [0] * (n - a - b)
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in range(n)) / n * 100 for _ in range(2000))
    return (a - b) / n * 100, bs[49], bs[1949]


def pexact(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def preds(w, m, lo):
    out = []
    calls = 0
    for i in range(len(SETS[w]['qs'])):
        p, u = run(w, i, lo, HI, m)
        out.append(p)
        calls += u
    return out, calls


def okvec(w, p):
    return [p[i] == SETS[w]['qs'][i]['gold'] for i in range(len(p))]


N = len(SETS['mix7']['qs'])
gold7 = [x['gold'] for x in SETS['mix7']['qs']]
base7 = [G['mix7'][BASE][i] == gold7[i] for i in range(N)]
out = [f'## mix7 판정 — {N}문제(정답 null {sum(g is None for g in gold7)}), 앞단 + 구조 + 넘김, hi {HI}, 기준선 26B q4_K_M 직접 {sum(base7)}/{N}']
out += ['| 넘김 모델 | lo | 직접 정답 | 종단 정답 | 엉뚱한 답 | 넘김 호출 | 종단 − 26B 직접: A만:B만 | 차이 %p [95% 구간] |', '|---|---:|---:|---:|---:|---:|---|---|']
R7 = {}
for m in cands:
    for lo in (0.10, 0.25):
        p, calls = preds('mix7', m, lo)
        ok = okvec('mix7', p)
        bad = sum(p[i] is not None and p[i] != gold7[i] for i in range(N))
        a = sum(ok[i] and not base7[i] for i in range(N))
        b = sum(base7[i] and not ok[i] for i in range(N))
        df, l, h = ci(a, b, N)
        R7[(m, lo)] = (p, ok, calls)
        out.append(f"| {m} | {lo} | {sum(G['mix7'][m][i] == gold7[i] for i in range(N))} | **{sum(ok)}** | {bad} | {calls} | {a}:{b} | {df:+.1f} [{l:+.1f}, {h:+.1f}] |")
if (MAIN, 0.10) in R7:
    ok10, ok25 = R7[(MAIN, 0.10)][1], R7[(MAIN, 0.25)][1]
    a = sum(ok10[i] and not base7[i] for i in range(N))
    b = sum(base7[i] and not ok10[i] for i in range(N))
    df, l, h = ci(a, b, N)
    verdict = '통과' if (df >= -3 and l >= -5) else '미통과'
    out.append(f"\n**주 판정(E4B QAT 종단, lo 0.10 − 26B 직접)**: {df:+.1f}%p [{l:+.1f}, {h:+.1f}] → 통과 기준(점추정 ≥ −3 · 하한 ≥ −5) **{verdict}**")
    a2 = sum(ok10[i] and not ok25[i] for i in range(N))
    b2 = sum(ok25[i] and not ok10[i] for i in range(N))
    d2, l2, h2 = ci(a2, b2, N)
    out.append(f"보조: lo 0.10 − lo 0.25 (같은 E4B QAT): {d2:+.1f}%p [{l2:+.1f}, {h2:+.1f}] (A만 {a2} : B만 {b2}, p={pexact(a2, b2):.2f}); 넘김 호출 {R7[(MAIN, 0.10)][2]}/{N} 대 {R7[(MAIN, 0.25)][2]}/{N}")

    def pooled(sets, lo):
        a = b = n = 0
        for w in sets:
            if w in ('heavy', 'mix4', 'mix5'):
                for i in IDX[w]:
                    g = SETS[w]['qs'][i]['gold']
                    pa = run(w, i, lo, HI, MAIN)[0] == g
                    pb = G[w]['gemma4:26b'][i] == g
                    a += pa and not pb
                    b += pb and not pa
                    n += 1
            else:
                p, _ = preds(w, MAIN, lo)
                g = [x['gold'] for x in SETS[w]['qs']]
                bs = G[w][BASE]
                for i in range(len(p)):
                    pa, pb = p[i] == g[i], bs[i] == g[i]
                    a += pa and not pb
                    b += pb and not pa
                    n += 1
        return a, b, n

    for label, sets in (('mix6 + mix7', ['mix6', 'mix7']), ('기존 264 + mix6 + mix7', ['heavy', 'mix4', 'mix5', 'mix6', 'mix7'])):
        for lo in (0.10, 0.25):
            a, b, n = pooled(sets, lo)
            d3, l3, h3 = ci(a, b, n)
            out.append(f'합친 {label} ({n}문제), lo {lo}: 종단 − 26B 직접 {d3:+.1f}%p [{l3:+.1f}, {h3:+.1f}] (A만 {a} : B만 {b})')
    types = list(dict.fromkeys(x['type'] for x in SETS['mix7']['qs']))
    out += ['', '| 유형 | 문제 | 26B 직접 | 종단 lo 0.10 | 종단 lo 0.25 | E4B QAT 직접 |', '|---|---:|---:|---:|---:|---:|']
    for t in types:
        ii = [i for i in range(N) if SETS['mix7']['qs'][i]['type'] == t]
        out.append(f"| {t} | {len(ii)} | {sum(base7[i] for i in ii)} | {sum(ok10[i] for i in ii)} | {sum(ok25[i] for i in ii)} | {sum(G['mix7'][MAIN][i] == gold7[i] for i in ii)} |")
print('\n'.join(out))
if md:
    open(md, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
