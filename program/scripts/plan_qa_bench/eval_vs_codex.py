# 비교표 — Gemma 4 26B 직접 · 소형 조합(앞단 + 구조 + E4B QAT) · Codex gpt-6-luna 를 같은 문제에서 나란히.
#  평가 세트 5개: heavy 판정 88 · mix4 88 · mix5 88 · mix6 130(Codex 작성) · mix7 173(Codex 작성) = 567문제.
#  루나는 세트마다 한 번 호출로 질문 전부를 묶어 푼다(Gemma·소형 조합은 질문 하나씩) — 조건이 다르다. 루나는 클라우드 구독 모델이고 서비스용이 아니다(천장 기준으로만 읽는다).
#  소형 조합의 앞단 문턱은 mix7 사전 등록값 lo 0.10(주)과 기존 값 lo 0.25 를 둘 다 보인다.  짝지은 차이는 정확 McNemar·복원추출 95% 구간(시드 20261001).
# 사용: python eval_vs_codex.py [--md 출력파일]
import contextlib, io, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'eval_mix7.py'), encoding='utf-8').read()
head = src[:src.index("N = len(SETS['mix7']['qs'])")]
ns = {'__name__': 'em', '__file__': os.path.join(HERE, 'eval_mix7.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'em_head', 'exec'), ns)
sys.argv = bak
SETS, G, run, IDX = ns['SETS'], ns['G'], ns['run'], ns['IDX']
J = lambda f: json.load(open(os.path.join(HERE, 'results', f), encoding='utf-8'))
W = os.environ.get('WSEL', 'heavy,mix4,mix5,mix6,mix7').split(',')          # WSEL=mix6,mix7 이면 작성자가 다른 독립 세트만
BASE26 = {'heavy': 'gemma4:26b', 'mix4': 'gemma4:26b', 'mix5': 'gemma4:26b', 'mix6': 'gemma4:26b-a4b-it-q4_K_M', 'mix7': 'gemma4:26b-a4b-it-q4_K_M'}
LUNA = {'heavy': J('codex_gpt-6-luna_heavy.json')['heavy']}
for w in ('mix4', 'mix5', 'mix6', 'mix7'):
    LUNA[w] = J(f'codex_gpt-6-luna_{w}.json')[w]
LUNAP = {'heavy': J('codex_gpt-6-luna_heavy_proto.json')['heavy']}
for w in ('mix4', 'mix5', 'mix6', 'mix7'):
    LUNAP[w] = J(f'codex_gpt-6-luna_{w}_proto.json')[w]
idx = {w: (IDX[w] if w in IDX else list(range(len(SETS[w]['qs'])))) for w in W}
M = 'gemma4:e4b-it-qat'
methods = {
    '26B 직접(Gemma 4 26B, 18GB)': lambda w, i: G[w][BASE26[w]][i],
    '소형 조합(앞단+구조+E4B QAT, lo 0.10)': lambda w, i: run(w, i, 0.10, 0.6, M)[0],
    '소형 조합(앞단+구조+E4B QAT, lo 0.25)': lambda w, i: run(w, i, 0.25, 0.6, M)[0],
    'E4B QAT 직접(6.1GB)': lambda w, i: G[w][M][i],
    'Codex gpt-6-luna': lambda w, i: LUNA[w].get(str(i)),
    'Codex gpt-6-luna + 정의 명시(먼저 언급한 항목이 정답)': lambda w, i: LUNAP[w].get(str(i)),
}
P = {m: {w: [f(w, i) for i in idx[w]] for w in W} for m, f in methods.items()}
GOLD = {w: [SETS[w]['qs'][i]['gold'] for i in idx[w]] for w in W}


def stat(m, ws):
    ok = wrong = miss = n = 0
    for w in ws:
        for p, g in zip(P[m][w], GOLD[w]):
            n += 1
            if p == g:
                ok += 1
            elif p is None:
                miss += 1
            else:
                wrong += 1
    return ok, wrong, miss, n


def ci(a, b, n):
    d = [1] * a + [-1] * b + [0] * (n - a - b)
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in range(n)) / n * 100 for _ in range(2000))
    return (a - b) / n * 100, bs[49], bs[1949]


def pexact(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


NTOT = sum(len(GOLD[w]) for w in W)
out = [f'## 비교표 — 26B 직접 · 소형 조합 · Codex gpt-6-luna (정답/문제, 세트 {",".join(W)})', '| 방식 | ' + ' | '.join(f'{w}({len(GOLD[w])})' for w in W) + f' | **합 {NTOT}** | 엉뚱한 답 | 못 찾음 |', '|---|' + '---:|' * (len(W) + 3)]
for m in methods:
    cells = [f"{stat(m, [w])[0]}" for w in W]
    ok, wrong, miss, n = stat(m, W)
    out.append(f"| {m} | " + ' | '.join(cells) + f" | **{ok}** ({ok / n:.1%}) | {wrong} | {miss} |")
out += ['', f'## 짝지은 차이({NTOT}문제 합, A − B, %p [95% 구간], A만:B만, p)', '| A | B | 차이 | A만 : B만 | p |', '|---|---|---|---|---:|']
names = list(methods)
pairs = [(names[4], names[0]), (names[5], names[0]), (names[4], names[1]), (names[5], names[1]), (names[1], names[0]), (names[2], names[0]), (names[3], names[0]), (names[4], names[3])]
for A, B in pairs:
    a = b = n = 0
    for w in W:
        for pa, pb, g in zip(P[A][w], P[B][w], GOLD[w]):
            a += pa == g and pb != g
            b += pb == g and pa != g
            n += 1
    d, lo, hi = ci(a, b, n)
    out.append(f"| {A} | {B} | {d:+.1f} [{lo:+.1f}, {hi:+.1f}] | {a} : {b} | {pexact(a, b):.3f} |")
# 유형별(문제 유형이 있는 세트 전부)
types = sorted({SETS[w]['qs'][i]['type'] for w in W for i in idx[w]})
out += ['', f'## 유형별 정답({NTOT}문제 합, 유형마다 문제 수가 다르다)', '| 유형 | 문제 | 26B 직접 | 소형 조합(lo 0.10) | Codex luna | luna + 정의 명시 |', '|---|---:|---:|---:|---:|---:|']
for t in types:
    cnt = {m: 0 for m in methods}
    n = 0
    for w in W:
        for k, i in enumerate(idx[w]):
            if SETS[w]['qs'][i]['type'] != t:
                continue
            n += 1
            for m in methods:
                cnt[m] += P[m][w][k] == GOLD[w][k]
    out.append(f"| {t} | {n} | {cnt[names[0]]} | {cnt[names[1]]} | {cnt[names[4]]} | {cnt[names[5]]} |")
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
