# ML 분기(V2)와 그래프 문지기(V3)의 시험 — 연구 문서 §40 사전 등록.
#  기준(B0/V1) = 앞단 점수가 문턱을 넘으면 확정 · 낮으면 없음 · 사이는 LLM(문턱은 heavy 개발용 44 로 선택).
#  V2 = 같은 자리(규칙·앞 대화가 못 정한 문제)에서 다항 로지스틱 회귀가 「앞단 1위가 맞음(A) · 틀림(B) · 정답 없음(N)」의 확률을 내고, 세 행동(확정·없음·LLM)의 기대 보상이 가장 큰 것을 고른다.
#    보상: 맞음 +1 · 틀린 답 −2 · 없음으로 닫음 = 정답 없을 때 +1, 있을 때 0 · LLM = 학습 세트에서 잰 평균 보상 − 0.05(호출 비용).  분기 문턱이 따로 없다(비용 0.05 는 지금까지의 목적식 그대로).
#  V3 = 문턱 방식에서 앞단 1위로 확정하기 전에, 같은 장소 이름의 다른 항목이 1위 점수의 0.85 배 이상이면 LLM 으로 보낸다(같은 장소 간선).
#  평가: 세트 하나를 빼고 학습해 그 세트에서 시험(heavy 는 판정 88). mix8 시험은 모든 라벨 세트로 학습해 mix8 하나만 쓴다(--final mix8).
# 사용: python eval_router.py [TAG=e16d] [--final mix8] [--md 출력파일]
import contextlib, io, json, math, os, random, sys
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

HERE = os.path.dirname(os.path.abspath(__file__))
tag = next((a for a in sys.argv[1:] if not a.startswith('--') and a != sys.argv[sys.argv.index('--final') + 1 if '--final' in sys.argv else -1] and a != (sys.argv[sys.argv.index('--md') + 1] if '--md' in sys.argv else '')), 'e16d')
final = sys.argv[sys.argv.index('--final') + 1] if '--final' in sys.argv else None
argv0 = sys.argv
sys.argv = ['x']
src = open(os.path.join(HERE, 'eval_front_v3.py'), encoding='utf-8').read()
head = src[:src.index('res = {}')]
ns0 = {'__name__': 'ev', '__file__': os.path.join(HERE, 'eval_front_v3.py')}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'h', 'exec'), ns0)
ns = ns0['load'](tag)
sys.argv = argv0
SETS, G, run, pipe, grid, dev, IDX, top, S = (ns[k] for k in ('SETS', 'G', 'run', 'pipe', 'grid', 'dev', 'IDX', 'top', 'S'))
M = 'gemma4:e4b-it-qat'
R = lambda *a: os.path.join(HERE, 'results', *a)
J = lambda f: json.load(open(f, encoding='utf-8'))
if final:
    SETS[final] = J(os.path.join(HERE, 'fixtures', f'{final}.json'))['sets'][final]
    for p, v in zip(J(os.path.join(HERE, 'fixtures', f'pairs_{final}.json')), J(R(f'ft_{tag}_{final}_scores.json'))[f'ft/emb_{tag}']):
        S[(p['set'], p['qi'])][p['item']] = v
    G[final] = {m: v['picks'] for m, v in J(R(f'llm_{final}_out.json')).items() if isinstance(v, dict) and 'picks' in v and '#' not in m and not m.startswith('_')}
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve

LABELED = ['heavy', 'mix4', 'mix5', 'mix6', 'mix7']
EVAL_SETS = [final] if final else LABELED


def qidx(w):
    if w == 'heavy' and not final:
        return list(range(len(SETS[w]['qs'])))
    return list(range(len(SETS[w]['qs'])))


def stage(w, i, tau_a=0.4):
    """규칙·앞 대화가 정하면 ('done', 답, 호출여부), 앞단 자리면 ('front', None, None)."""
    st = SETS[w]
    x = st['qs'][i]
    items = st['items']
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    if rs['day'] is None:
        rs['day'] = rule_slots(x['q'], items)['day']
    anchor = None
    if rs['rel'] is not None:
        k, p = top(w, 'excl' if a['negation'] else 'tt', i)
        anchor = k if p >= tau_a else None
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = anchor
    r = resolve(items, slots)
    if r[0] == 'item':
        return 'done', r[1], False
    if r[0] == 'none':
        return 'done', None, False
    if x['history']:
        return 'done', G[w][M][i], True
    return 'front', None, None


def feats(w, i):
    d = S[(f'{w}_tt', i)]
    v = sorted(d.values(), reverse=True)
    s1, s2 = v[0], v[1] if len(v) > 1 else 0.0
    z = np.array(v) / 0.05
    z = np.exp(z - z.max())
    pz = z / z.sum()
    ent = float(-(pz * np.log(pz + 1e-12)).sum())
    x = SETS[w]['qs'][i]
    a = analyze(x['q'])
    return [s1, s2, s1 - s2, ent, len(x['q']) / 30.0, 1.0 if a['negation'] else 0.0, math.log(len(v))], max(d, key=d.get)


def label(w, i, top1):
    g = SETS[w]['qs'][i]['gold']
    if g is None:
        return 2
    return 0 if top1 == g else 1


def llm_util(w, i):
    g = SETS[w]['qs'][i]['gold']
    p = G[w][M][i]
    if p == g:
        return 1.0
    return 0.0 if p is None else -2.0


# 앞단 자리에 오는 문제의 특징·라벨·LLM 보상
DATA = {}
for w in set(LABELED + ([final] if final else [])):
    rows = []
    for i in range(len(SETS[w]['qs'])):
        st = stage(w, i)
        if st[0] != 'front':
            continue
        f, t1 = feats(w, i)
        rows.append((i, f, label(w, i, t1), t1, llm_util(w, i)))
    DATA[w] = rows


def fit(train_sets):
    X = np.array([r[1] for w in train_sets for r in DATA[w]])
    y = np.array([r[2] for w in train_sets for r in DATA[w]])
    sc = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=2000, C=1.0).fit(sc.transform(X), y)
    uL = float(np.mean([r[4] for w in train_sets for r in DATA[w]])) - 0.05
    return sc, clf, uL


def router_pred(w, i, model):
    sc, clf, uL = model
    f, t1 = feats(w, i)
    p = np.zeros(3)
    pr = clf.predict_proba(sc.transform([f]))[0]
    for c, q in zip(clf.classes_, pr):
        p[c] = q
    u_acc = p[0] * 1 + (p[1] + p[2]) * (-2)
    u_none = p[2] * 1
    best = max((u_acc, 'acc'), (u_none, 'none'), (uL, 'llm'))[1]
    if best == 'acc':
        return t1, False
    if best == 'none':
        return None, False
    return G[w][M][i], True


def same_place_gate(w, i, lo, hi):
    """V3: 문턱 방식의 결과에서, 확정(앞단 1위)이 같은 장소의 경쟁 항목과 0.85 이내면 LLM 으로 보낸다."""
    p, used = run(w, i, lo, hi, M)
    st = stage(w, i)
    if st[0] != 'front' or used:
        return p, used
    d = S[(f'{w}_tt', i)]
    k = max(d, key=d.get)
    if d[k] < hi:
        return p, used
    items = {it['id']: it for it in SETS[w]['items']}
    for j, s in d.items():
        if j != k and items[j]['place'] == items[k]['place'] and s >= 0.85 * d[k]:
            return G[w][M][i], True
    return p, used


# 문턱(개발용 44 로 선택)
best = max(grid, key=lambda g: (pipe('heavy', dev, *g, M)[0] - 2 * pipe('heavy', dev, *g, M)[1] - 0.05 * pipe('heavy', dev, *g, M)[2], -g[0]))
out = [f'## ML 분기(V2)·그래프 문지기(V3) — 앞단 {tag}, 넘김 E4B QAT, 기준 문턱 {best[0]}/{best[1]}(heavy 개발용 44 로 선택)']
tot = {'기준(문턱)': [0, 0, 0], 'V2 ML 분기': [0, 0, 0], 'V3 그래프 문지기': [0, 0, 0]}
rows_out = []
VEC = {k: [] for k in tot}
for w in EVAL_SETS:
    test_idx = [i for i in range(len(SETS[w]['qs'])) if not (w == 'heavy' and SETS[w]['qs'][i].get('split') != 'held')]
    train_sets = [s for s in LABELED if s != w] if not final else LABELED
    model = fit(train_sets)
    cell = {}
    for name, fn in (('기준(문턱)', lambda i: run(w, i, best[0], best[1], M)), ('V2 ML 분기', None), ('V3 그래프 문지기', lambda i: same_place_gate(w, i, best[0], best[1]))):
        ok = bad = calls = 0
        for i in test_idx:
            if name == 'V2 ML 분기':
                st = stage(w, i)
                p, used = (st[1], st[2]) if st[0] == 'done' else router_pred(w, i, model)
            else:
                p, used = fn(i)
            g = SETS[w]['qs'][i]['gold']
            ok += p == g
            VEC[name].append(int(p == g))
            bad += p is not None and p != g
            calls += used
        cell[name] = (ok, bad, calls)
        for k, v in zip(range(3), (ok, bad, calls)):
            tot[name][k] += v
    n = len(test_idx)
    rows_out.append((w, n, cell))
out.append('| 세트 | 문제 | ' + ' | '.join(f'{k} 정답/엉뚱/호출' for k in tot) + ' |')
out.append('|---|---:|' + '---|' * len(tot))
for w, n, cell in rows_out:
    out.append(f'| {w} | {n} | ' + ' | '.join(f'{cell[k][0]}/{cell[k][1]}/{cell[k][2]}' for k in tot) + ' |')
N = sum(n for _, n, _ in rows_out)
out.append(f'| **합** | {N} | ' + ' | '.join(f'**{tot[k][0]}**/{tot[k][1]}/{tot[k][2]}' for k in tot) + ' |')
from math import comb


def mcn(a, b):
    n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
    n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
    n = n01 + n10
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, k) for k in range(0, min(n01, n10) + 1)) / 2 ** n)
    return n01, n10, p


for k in ('V2 ML 분기', 'V3 그래프 문지기'):
    n01, n10, p = mcn(VEC['기준(문턱)'], VEC[k])
    out.append(f'짝지은 비교 {k} vs 기준: {k}만 맞음 {n01} · 기준만 맞음 {n10} · 정확검정 p={p:.3f}')
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
