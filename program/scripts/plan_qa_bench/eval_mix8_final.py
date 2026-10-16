# mix8 최종 시험 — 연구 문서 §40 사전 등록대로(결과를 본 뒤 특징·문턱·0.85·비평 문턱을 바꾸지 않는다).
#  B0 = 앞단 e16c + 문턱(heavy 개발용 44 로 선택) + 넘김 E4B QAT · V1 = 앞단 e16d 로 바꾼 같은 방식
#  V2 = V1 의 앞단 자리를 학습형 분기(기존 5세트로 학습)로 · V3 = V1 + 같은 장소 문지기(0.85) · V4 = V1 + 짚은 항목 비평(문턱은 기존 5세트에서 고름)
#  참고 = 26B·12B·E4B QAT 직접, Jev 직접, Codex luna(정의 없음·명시)
#  짝지은 비교: B0 대비 V1, V1 대비 V2~V4 (정확검정 + 짝지은 부트스트랩 95% 구간). 보조: 유형별, 잡담 1,500개 오답 비율.
# 사용: python eval_mix8_final.py [--md 출력파일]
import json, math, os, random, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
argv0 = sys.argv
sys.argv = ['x', 'e16d', '--final', 'mix8']
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, G, run, pipe, grid, dev, S = (G0[k] for k in ('SETS', 'G', 'run', 'pipe', 'grid', 'dev', 'S'))
stage, fit, router_pred, same_place_gate, feats, LABELED, M = (G0[k] for k in ('stage', 'fit', 'router_pred', 'same_place_gate', 'feats', 'LABELED', 'M'))
R, J = G0['R'], G0['J']
W = 'mix8'


def inject(ns, tag):
    ns['SETS'][W] = J(fixture(f'{W}.json'))['sets'][W]
    for p, v in zip(J(os.path.join(HERE, 'fixtures', f'pairs_{W}.json')), J(R(f'ft_{tag}_{W}_scores.json'))[f'ft/emb_{tag}']):
        ns['S'][(p['set'], p['qi'])][p['item']] = v
    ns['G'][W] = G[W]


def choose(ns):
    gr, pp, dv = ns['grid'], ns['pipe'], ns['dev']
    return max(gr, key=lambda g: (pp('heavy', dv, *g, M)[0] - 2 * pp('heavy', dv, *g, M)[1] - 0.05 * pp('heavy', dv, *g, M)[2], -g[0]))


C = G0['ns0']['load']('e16c')
inject(C, 'e16c')
bestC, bestD = choose(C), choose(G0['ns'])
qs = SETS[W]['qs']
n = len(qs)
gold = [x['gold'] for x in qs]
types = sorted({x['type'] for x in qs})


def stat(preds, calls=None):
    ok = sum(p == g for p, g in zip(preds, gold))
    bad = sum(p is not None and p != g for p, g in zip(preds, gold))
    return ok, bad, calls


P = {}   # 방식 → (예측, 넘김 호출 수)
Pc = [C['run'](W, i, bestC[0], bestC[1], M) for i in range(n)]
P['B0 기준(e16c)'] = ([p for p, _ in Pc], sum(u for _, u in Pc))
Pd = [run(W, i, bestD[0], bestD[1], M) for i in range(n)]
P['V1 앞단 e16d'] = ([p for p, _ in Pd], sum(u for _, u in Pd))
model = fit(LABELED)
v2 = []
for i in range(n):
    st = stage(W, i)
    v2.append((st[1], st[2]) if st[0] == 'done' else router_pred(W, i, model))
P['V2 ML 분기'] = ([p for p, _ in v2], sum(u for _, u in v2))
v3 = [same_place_gate(W, i, bestD[0], bestD[1]) for i in range(n)]
P['V3 그래프 문지기'] = ([p for p, _ in v3], sum(u for _, u in v3))

# V4: 문턱은 기존 5세트(heavy 판정 88 포함)에서 고른다 — 단위는 정답 − 2×엉뚱한 답 − 0.05×(넘김 + 비평 호출)
VP = {}
okv = True
for w in LABELED + [W]:
    f = R(f'verify_{w}_gemma4_e4b-it-qat.json')
    if not os.path.exists(f):
        okv = False
        break
    VP[w] = {int(k): v for k, v in J(f)['p'].items()}
v4tau = None
if okv:
    def v4_eval(w, idx, tau, lo, hi):
        ok = bad = calls = ver = 0
        for i in idx:
            p, u = run(w, i, lo, hi, M)
            if u and p is not None:
                ver += 1
                if VP[w].get(i, 1.0) < tau:
                    p = None
            g = SETS[w]['qs'][i]['gold']
            ok += p == g
            bad += p is not None and p != g
            calls += u
        return ok, bad, calls, ver
    taus = [round(0.05 * k, 2) for k in range(1, 20)]
    idxs = {w: [i for i in range(len(SETS[w]['qs'])) if not (w == 'heavy' and SETS[w]['qs'][i].get('split') != 'held')] for w in LABELED}
    best_u = None
    rowsT = []
    for tau in taus:
        t = [0, 0, 0, 0]
        for w in LABELED:
            r = v4_eval(w, idxs[w], tau, bestD[0], bestD[1])
            t = [a + b for a, b in zip(t, r)]
        u = t[0] - 2 * t[1] - 0.05 * (t[2] + t[3])
        rowsT.append((tau, t, u))
        if best_u is None or u > best_u[0] + 1e-9:
            best_u = (u, tau)
    v4tau = best_u[1]
    base = [0, 0, 0, 0]
    for w in LABELED:
        r = v4_eval(w, idxs[w], 0.0, bestD[0], bestD[1])
        base = [a + b for a, b in zip(base, r)]
    v4 = []
    for i in range(n):
        p, u = run(W, i, bestD[0], bestD[1], M)
        ver = False
        if u and p is not None:
            ver = True
            if VP[W].get(i, 1.0) < v4tau:
                p = None
        v4.append((p, u, ver))
    P['V4 비평(IsRel 식)'] = ([p for p, _, _ in v4], sum(u for _, u, _ in v4))
    V4VER = sum(v for _, _, v in v4)

# 참고 방식(직접·Jev·luna)
REF = {}
for m, lab in (('gemma4:26b-a4b-it-q4_K_M', '26B 직접'), ('gemma4:12b', '12B 직접'), ('gemma4:e4b-it-qat', 'E4B QAT 직접')):
    if m in G[W]:
        REF[lab] = G[W][m]
jf = R('jev_out_mix8.json')
if os.path.exists(jf):
    jd = J(jf)[W]
    ids = jd['keys']
    jp = []
    for r in jd['rows']:
        pr = r['probs']
        k = max(pr, key=pr.get) if pr else 'none'
        jp.append(int(k.split('_')[1]) if k.startswith('item_') else None)
    REF['Jev 직접(유료)'] = jp
for lab, f in (('Codex luna', 'codex_gpt-6-luna_mix8.json'), ('Codex luna + 정의 명시', 'codex_gpt-6-luna_mix8_proto.json')):
    if os.path.exists(R(f)):
        d = J(R(f))[W]
        REF[lab] = [d.get(str(i)) for i in range(n)]


def ci(a, b, nn):
    d = [1] * a + [-1] * b + [0] * (nn - a - b)
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in range(nn)) / nn * 100 for _ in range(2000))
    return (a - b) / nn * 100, bs[49], bs[1949]


def pexact(b, c):
    nn = b + c
    return 1.0 if nn == 0 else min(1.0, 2 * sum(math.comb(nn, i) for i in range(min(b, c) + 1)) / 2 ** nn)


def pair(a, b):
    x = sum(p == g and q != g for p, q, g in zip(a, b, gold))
    y = sum(p != g and q == g for p, q, g in zip(a, b, gold))
    d, lo, hi = ci(x, y, n)
    return x, y, d, lo, hi, pexact(x, y)


out = [f'## mix8 최종 시험 — {n}문제(정답 없음 {sum(g is None for g in gold)}), 문턱: B0 {bestC[0]}/{bestC[1]} · V1~V4 {bestD[0]}/{bestD[1]}(heavy 개발용 44 로 선택), 넘김 E4B QAT',
       '| 방식 | 정답 | 엉뚱한 답 | 넘김 호출 | 정답 없음 맞춤(정답 없음 중) |', '|---|---:|---:|---:|---:|']
nn_ = sum(g is None for g in gold)
for k, (pr, calls) in P.items():
    ok, bad, _ = stat(pr)
    extra = f' (+비평 {V4VER})' if k.startswith('V4') else ''
    out.append(f'| {k} | **{ok}** ({ok / n:.1%}) | {bad} | {calls}{extra} | {sum(p is None for p, g in zip(pr, gold) if g is None)}/{nn_} |')
if v4tau is not None:
    out.append(f'\nV4 문턱 τ={v4tau}(기존 5세트에서 선택 · 비평 없음 기준 정답 {base[0]}/엉뚱 {base[1]}/호출 {base[2]} → 문턱 적용 뒤 {dict((r[0], r[1]) for r in rowsT)[v4tau]})')
out += ['', '### 짝지은 비교(정확검정 · 짝지은 부트스트랩 95% 구간)', '| 비교 | 앞쪽만 맞음 | 뒤쪽만 맞음 | 차이 %p [95% 구간] | p |', '|---|---:|---:|---|---:|']
for a, b in (('V1 앞단 e16d', 'B0 기준(e16c)'), ('V2 ML 분기', 'V1 앞단 e16d'), ('V3 그래프 문지기', 'V1 앞단 e16d'), ('V4 비평(IsRel 식)', 'V1 앞단 e16d')):
    if a in P and b in P:
        x, y, d, lo, hi, p = pair(P[a][0], P[b][0])
        out.append(f'| {a} − {b} | {x} | {y} | {d:+.1f} [{lo:+.1f}, {hi:+.1f}] | {p:.3f} |')
out += ['', '### 참고(직접 방식 · 규칙·앞단 없음)', '| 방식 | 정답 | 엉뚱한 답 | V1 과 짝지은 차이 %p [구간] · p |', '|---|---:|---:|---|']
for lab, pr in REF.items():
    ok, bad, _ = stat(pr)
    x, y, d, lo, hi, p = pair(pr, P['V1 앞단 e16d'][0])
    out.append(f'| {lab} | {ok} ({ok / n:.1%}) | {bad} | {d:+.1f} [{lo:+.1f}, {hi:+.1f}] · p={p:.3f} |')
out += ['', '### 유형별 정답(유형당 14~16문제 — 값이 작아 구간이 넓다)', '| 유형 | 문제 | ' + ' | '.join(list(P)[:4] + list(REF)[:3]) + ' |', '|---|---:|' + '---:|' * (len(list(P)[:4]) + len(list(REF)[:3]))]
for t in types:
    ids = [i for i, x in enumerate(qs) if x['type'] == t]
    cells = []
    for pr in [P[k][0] for k in list(P)[:4]] + [REF[k] for k in list(REF)[:3]]:
        cells.append(str(sum(pr[i] == gold[i] for i in ids)))
    out.append(f'| {t} | {len(ids)} | ' + ' | '.join(cells) + ' |')

# 잡담(앞 1,500, mix7 일정): 앞단만 거친 질의 — 정답은 항상 「없음」
chat = J(os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', '020.주제별 텍스트 일상 대화 데이터', 'processed', 'chat_sample_3000.json'))
E4 = J(R('chat_llm_mix7_gemma4_e4b-it-qat.json'))['picks']
from clauses import analyze
out += ['', '### 보조: 잡담 1,500개(mix7 일정 · 앞단과 넘김만, 규칙 단계 없음)에서 항목으로 답한 비율', '| 방식 | LLM 으로 넘김 | 항목으로 답함 |', '|---|---:|---:|']
NC = 1500
for tag, suf, (lo, hi) in (('B0 e16c', '', bestC), ('V1 e16d', '_e16d', bestD)):
    fr = J(R(f'chat_front_mix7{suf}.json'))
    mx = [max(r) for r in fr['sims'][:NC]]
    routed = [k for k in range(NC) if lo <= mx[k] < hi]
    fa = sum(E4[str(k)] is not None for k in routed) + sum(m >= hi for m in mx)
    out.append(f'| {tag} {lo}/{hi} | {len(routed) / NC:.1%} | {fa}/{NC} = {fa / NC:.2%} |')
fr = J(R('chat_front_mix7_e16d.json'))
sc, clf, uL = model
routed = fa = 0
for k in range(NC):
    d = sorted(fr['sims'][k], reverse=True)
    z = np.exp((np.array(d) - d[0]) / 0.05)
    pz = z / z.sum()
    ent = float(-(pz * np.log(pz + 1e-12)).sum())
    a = analyze(chat[k])
    f = [d[0], d[1], d[0] - d[1], ent, len(chat[k]) / 30.0, 1.0 if a['negation'] else 0.0, math.log(len(d))]
    pr = clf.predict_proba(sc.transform([f]))[0]
    p = np.zeros(3)
    for c_, q in zip(clf.classes_, pr):
        p[c_] = q
    best = max(((p[0] - 2 * (p[1] + p[2])), 'acc'), (p[2], 'none'), (uL, 'llm'))[1]
    if best == 'acc':
        fa += 1
    elif best == 'llm':
        routed += 1
        fa += E4[str(k)] is not None
out.append(f'| V2 ML 분기(e16d 점수) | {routed / NC:.1%} | {fa}/{NC} = {fa / NC:.2%} |')
print('\n'.join(out))
if '--md' in argv0:
    open(argv0[argv0.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
