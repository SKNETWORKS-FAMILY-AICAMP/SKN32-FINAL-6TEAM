# 최종 채점 — §40·§42·§45 사전 등록 방식 전부를 시험 세트(기본 mix8, mix9)에서 한 번 채점한다.
#  규칙·문턱·τ·특징은 기존 5세트(heavy 판정 88·mix4·mix5·mix6·mix7)에서만 고른다. 시험 세트로는 아무것도 고르지 않는다.
#  방식: B0(e16c)·V1(e16d)·V2 ML 분기·V3 같은 장소 문지기·V4 E4B 비평·V5 RL 식 정책·V10 작은 LLM 판정기(Jev 대체)·V11 12B 비평·V12 비평 승격·V13 그래프 앞단(e16g)
#        · 앞단 구성: L1~L3 규칙→LLM · C1·C2 Codex luna · 참고: 직접 짚기(26B·12B·E4B QAT)·Jev 직접·luna
#  각 방식은 필요한 결과 파일이 있을 때만 채점한다(없으면 표에서 빠지고 이유를 적는다).
# 사용: python eval_final_all.py [--sets mix8,mix9] [--md 출력파일]
import contextlib, io, json, math, os, random, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
argv0 = sys.argv
EV = argv0[argv0.index('--sets') + 1].split(',') if '--sets' in argv0 else ['mix8', 'mix9']
sys.argv = ['x', 'e16d']
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, G, S, run, pipe, grid, dev = (G0[k] for k in ('SETS', 'G', 'S', 'run', 'pipe', 'grid', 'dev'))
stage, fit, router_pred, same_place_gate, feats, DATA, LABELED, M = (G0[k] for k in ('stage', 'fit', 'router_pred', 'same_place_gate', 'feats', 'DATA', 'LABELED', 'M'))
R, J = G0['R'], G0['J']
F = lambda n: os.path.join(HERE, 'fixtures', n)
M12 = 'gemma4:12b'
NOTES = []


def inject(ns, tag, ws):
    for w in ws:
        if w in LABELED:
            continue
        if w not in ns['SETS']:
            ns['SETS'][w] = J(F(f'{w}.json'))['sets'][w]
        for p, v in zip(J(F(f'pairs_{w}.json')), J(R(f'ft_{tag}_{w}_scores.json'))[f'ft/emb_{tag}']):
            ns['S'][(p['set'], p['qi'])][p['item']] = v
        if w not in ns['G']:
            ns['G'][w] = {m: v['picks'] for m, v in J(R(f'llm_{w}_out.json')).items() if isinstance(v, dict) and 'picks' in v and '#' not in m and not m.startswith('_')}


inject(G0['ns'], 'e16d', EV)
for w in EV:
    G[w] = G0['ns']['G'][w]
    SETS[w] = G0['ns']['SETS'][w]


def choose(ns):
    gr, pp, dv = ns['grid'], ns['pipe'], ns['dev']
    return max(gr, key=lambda g: (pp('heavy', dv, *g, M)[0] - 2 * pp('heavy', dv, *g, M)[1] - 0.05 * pp('heavy', dv, *g, M)[2], -g[0]))


lo, hi = choose(G0['ns'])
C = G0['ns0']['load']('e16c')
inject(C, 'e16c', EV)
for w in EV:
    C['G'][w] = G[w]
loC, hiC = choose(C)
CG = None
if all(os.path.exists(R(f'ft_e16g_{s}_scores.json')) for s in ['mix5', 'mix6', 'mix7'] + EV) and os.path.exists(R('ft_e16g_scores.json')):
    CG = G0['ns0']['load']('e16g')
    inject(CG, 'e16g', EV)
    for w in EV:
        CG['G'][w] = G[w]
    loG, hiG = choose(CG)
else:
    NOTES.append('V13(e16g): 앞단 점수 파일이 아직 없어 채점하지 못했다')


def idx_of(w):
    return [i for i in range(len(SETS[w]['qs'])) if not (w == 'heavy' and SETS[w]['qs'][i].get('split') != 'held')]


def k26(w):
    for k in ('gemma4:26b-a4b-it-q4_K_M', 'gemma4:26b'):
        if k in G[w]:
            return k
    return None


def load_opt(f):
    return J(f) if os.path.exists(f) else None


VP = {}      # E4B 비평 p
VP12 = {}    # 12B 비평 p
JD = {}      # 판정기 {문제: {항목: p}}
for w in LABELED + EV:
    f = load_opt(R(f'verify_{w}_gemma4_e4b-it-qat.json'))
    if f:
        VP[w] = {int(k): v for k, v in f['p'].items()}
    f = load_opt(R(f'verify_{w}_gemma4_12b.json'))
    if f:
        VP12[w] = {int(k): v for k, v in f['p'].items()}
    f = load_opt(R(f'judge_{w}_gemma4_e4b-it-qat.json'))
    if f:
        JD[w] = {int(k): {int(a): b for a, b in v.items()} for k, v in f['p'].items()}


def have(d):
    return all(w in d for w in LABELED + EV)


# ---------- 방식별 예측기: (세트, 문제번호) → (예측, 호출 수) ----------
def p_v1(w, i):
    p, u = run(w, i, lo, hi, M)
    return p, int(u)


def make_critic_pred(vp, tau, escalate=None):
    def f(w, i):
        p, u = run(w, i, lo, hi, M)
        c = int(u)
        if u and p is not None:
            c += 1
            if vp[w].get(i, 1.0) < tau:
                if escalate:
                    p = G[w][escalate][i]
                    c += 1
                else:
                    p = None
        return p, c
    return f


def util(fn, ws, per=None):
    ok = bad = calls = 0
    for w in ws:
        for i in idx_of(w):
            p, c = fn(w, i)
            g = SETS[w]['qs'][i]['gold']
            ok += p == g
            bad += p is not None and p != g
            calls += c
    return ok - 2 * bad - 0.05 * calls, ok, bad, calls


def pick_tau(maker, grid_=None):
    best = None
    for tau in (grid_ or [round(0.05 * k, 2) for k in range(1, 20)]):
        u = util(maker(tau), LABELED)[0]
        if best is None or u > best[0] + 1e-9:
            best = (u, tau)
    return best[1]


TAU = {}
P = {}   # 이름 → (w, i) → (pred, calls)
P['B0 기준(e16c)'] = lambda w, i: (lambda r: (r[0], int(r[1])))(C['run'](w, i, loC, hiC, M))
P['V1 앞단 e16d'] = p_v1
model2 = fit(LABELED)


def p_v2(w, i):
    st = stage(w, i)
    if st[0] == 'done':
        return st[1], int(bool(st[2]))
    p, u = router_pred(w, i, model2)
    return p, int(u)


P['V2 ML 분기'] = p_v2
P['V3 그래프 문지기'] = lambda w, i: (lambda r: (r[0], int(r[1])))(same_place_gate(w, i, lo, hi))
if have(VP):
    TAU['V4'] = pick_tau(lambda t: make_critic_pred(VP, t))
    P['V4 E4B 비평'] = make_critic_pred(VP, TAU['V4'])
else:
    NOTES.append('V4: 비평 확률 파일이 모든 세트에 없다')
if have(VP12):
    TAU['V11'] = pick_tau(lambda t: make_critic_pred(VP12, t))
    P['V11 12B 비평'] = make_critic_pred(VP12, TAU['V11'])
else:
    NOTES.append('V11: 12B 비평 확률 파일이 아직 모든 세트에 없다')
if have(VP):
    TAU['V12'] = pick_tau(lambda t: make_critic_pred(VP, t, escalate=M12))
    P['V12 E4B 비평→12B 승격'] = make_critic_pred(VP, TAU['V12'], escalate=M12)


# V5 RL 식 정책
def act_rewards(w, i, t1):
    gold = SETS[w]['qs'][i]['gold']
    p = G[w][M][i]
    return np.array([1.0 if t1 == gold else -2.0, 1.0 if gold is None else 0.0, (1.0 if p == gold else (0.0 if p is None else -2.0)) - 0.05])


def train_policy(train_sets, seed=20261003, epochs=1500, lr=0.05):
    X = np.array([r[1] for w in train_sets for r in DATA[w]])
    Rw = np.array([act_rewards(w, r[0], r[3]) for w in train_sets for r in DATA[w]])
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
    rng = np.random.default_rng(seed)
    W = np.zeros((Z.shape[1], 3))
    m = np.zeros_like(W)
    v = np.zeros_like(W)
    for t in range(1, epochs + 1):
        lg = Z @ W
        lg -= lg.max(1, keepdims=True)
        Pp = np.exp(lg)
        Pp /= Pp.sum(1, keepdims=True)
        a = np.array([rng.choice(3, p=p) for p in Pp])
        r = Rw[np.arange(len(a)), a]
        adv = r - r.mean()
        grad = Z.T @ ((np.eye(3)[a] - Pp) * adv[:, None]) / len(Z)
        m = 0.9 * m + 0.1 * grad
        v = 0.999 * v + 0.001 * grad ** 2
        W += lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return mu, sd, W


pol = train_policy(LABELED)


def p_v5(w, i):
    st = stage(w, i)
    if st[0] == 'done':
        return st[1], int(bool(st[2]))
    mu, sd, W = pol
    f, t1 = feats(w, i)
    a = int(np.argmax(np.append((np.array(f) - mu) / sd, 1.0) @ W))
    if a == 0:
        return t1, 0
    if a == 1:
        return None, 0
    return G[w][M][i], 1


P['V5 RL 식 정책'] = p_v5


# V10 작은 LLM 판정기
def make_v10(tau):
    def f(w, i):
        st = stage(w, i)
        if st[0] == 'done':
            return st[1], int(bool(st[2]))
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        s1 = d[k]
        if s1 >= hi:
            return k, 0
        if s1 < lo:
            return None, 0
        row = JD[w].get(i)
        if not row:
            return None, 0
        best = max(row, key=lambda a: (row[a], -list(row).index(a)))
        return (best if row[best] >= tau else None), len(row)
    return f


if have(JD):
    TAU['V10'] = pick_tau(make_v10)
    P['V10 판정기(Jev 대체)'] = make_v10(TAU['V10'])
else:
    NOTES.append('V10: 판정기 확률 파일이 아직 모든 세트에 없다')
if CG is not None:
    P['V13 그래프 앞단 e16g'] = lambda w, i: (lambda r: (r[0], int(r[1])))(CG['run'](w, i, loG, hiG, M))


# 앞단 구성(규칙 뒤)
def luna(w, proto):
    f = load_opt(R(f'codex_gpt-6-luna_{w}' + ('_proto' if proto else '') + '.json'))
    return None if f is None else [f[w].get(str(i)) for i in range(len(SETS[w]['qs']))]


LUNA = {w: {False: luna(w, False), True: luna(w, True)} for w in LABELED + EV}


def after_rules(fn):
    def f(w, i):
        st = stage(w, i)
        if st[0] == 'done':
            return st[1], int(bool(st[2]))
        return fn(w, i)
    return f


for name, key in (('L1 규칙→E4B QAT', M), ('L2 규칙→12B', M12)):
    P[name] = after_rules(lambda w, i, key=key: (G[w][key][i], 1))
if all(k26(w) for w in LABELED + EV):
    P['L3 규칙→26B'] = after_rules(lambda w, i: (G[w][k26(w)][i], 1))
    if have(VP):
        TAU['L4'] = pick_tau(lambda t: after_rules(lambda w, i: (G[w][k26(w)][i], 2) if (G[w][M][i] is None or VP[w].get(i, 1.0) < t) else (G[w][M][i], 1)))
        P['L4 규칙→E4B QAT→(없음·비평<τ)→26B'] = after_rules(lambda w, i: (G[w][k26(w)][i], 2) if (G[w][M][i] is None or VP[w].get(i, 1.0) < TAU['L4']) else (G[w][M][i], 1))
else:
    NOTES.append('L3·L4: 26B 짚기가 모든 세트에 있지는 않다(시험 세트 26B 계산 대기)')
if all(LUNA[w][True] is not None for w in LABELED + EV):
    P['C1 규칙→luna+정의'] = after_rules(lambda w, i: (LUNA[w][True][i], 1))

    def c2(w, i):
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        return (k, 0) if d[k] >= hi else (LUNA[w][True][i], 1)
    P['C2 규칙→앞단 확정→luna+정의'] = after_rules(c2)
else:
    NOTES.append('C1·C2: luna 결과가 모든 세트에 없다')

# ---------- §48·§49 방식: J1 Jev 앞단 · J2 로컬 확신도 앞단 · V15 힌트(QAT) · V16 적대적 검토 ----------
GRID_HI = [round(0.5 + 0.05 * k, 2) for k in range(0, 10)] + [0.99]
JEV = {}
for w in LABELED + EV:
    f = load_opt(R(f'jev_out_{w}.json'))
    if f and w in f:
        JEV[w] = f[w]


def jev_choice(w, i):
    r = JEV[w]['rows'][i]
    pr = r['probs']
    if not pr:
        return None, 0.0
    k = max(pr, key=pr.get)
    return (int(k.split('_')[1]) if k.startswith('item_') else None), pr[k]


def make_j1(tau):
    def f(w, i):
        st = stage(w, i)
        if st[0] == 'done':
            return st[1], int(bool(st[2]))
        it, p1 = jev_choice(w, i)
        if p1 >= tau:
            return it, 0
        return G[w][M][i], 1
    return f


if have(JEV):
    TAU['J1'] = pick_tau(make_j1, GRID_HI)
    P['J1 Jev 앞단(확신 ≥ τ 이면 Jev, 아니면 E4B QAT)'] = make_j1(TAU['J1'])
    JEV_CALLS = {w: sum(1 for i in range(len(SETS[w]['qs'])) if stage(w, i)[0] == 'front') for w in EV}
else:
    NOTES.append('J1: Jev 결과가 모든 세트에 없다')
LP = {}
for w in LABELED + EV:
    f = load_opt(R(f'llm_{w}_lp_out.json'))
    if f and M in f and f[M].get('conf'):
        LP[w] = f[M]


def make_j2(tau):
    def f(w, i):
        st = stage(w, i)
        if st[0] == 'done':
            return st[1], int(bool(st[2]))
        c = LP[w]['conf'][i]
        if c is not None and c >= tau:
            return LP[w]['picks'][i], 1
        return G[w][M12][i], 2
    return f


if have(LP):
    TAU['J2'] = pick_tau(make_j2, GRID_HI)
    P['J2 로컬 확신도 앞단(E4B QAT 확신 ≥ τ 이면 그대로, 아니면 12B)'] = make_j2(TAU['J2'])
else:
    NOTES.append('J2: E4B QAT 확신도(logprob) 결과가 모든 세트에 없다')
HINT = {}
for w in LABELED + EV:
    f = load_opt(R(f'llm_{w}_hint_out.json'))
    if f and M in f:
        HINT[w] = f[M]['picks']
if have(HINT):
    def p_v15(w, i):
        st = stage(w, i)
        if st[0] == 'done':
            return st[1], int(bool(st[2]))
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        s1 = d[k]
        if s1 >= hi:
            return k, 0
        if s1 < lo:
            return None, 0
        return HINT[w][i], 1
    P['V15 힌트(QAT)'] = p_v15
else:
    NOTES.append('V15: 힌트(QAT) 짚기 결과가 모든 세트에 없다')


def load_adv(tag):
    d = {}
    for w in LABELED + EV:
        f = load_opt(R(f'adv_{w}_{tag}.json'))
        if f:
            d[w] = {int(k): v for k, v in f['rows'].items()}
    return d


def make_v16(adv):
    def f(w, i):
        p, u = run(w, i, lo, hi, M)
        c = int(u)
        if u and p is not None:
            row = adv[w].get(i)
            c += 1
            if row and row['duel']:
                c += 2
                if row['duel'] == ['alt', 'alt']:
                    p = row['alt']
                elif row['duel'] == ['neither', 'neither']:
                    p = None
        return p, c
    return f


for tag, lab_ in (('gemma4_e4b-it-qat', 'V16 적대적 검토(E4B QAT 반론)'), ('gemma4_12b', 'V16b 적대적 검토(12B 반론)')):
    A = load_adv(tag)
    if have(A):
        P[lab_] = make_v16(A)
    else:
        NOTES.append(f'{lab_}: 반론 결과가 모든 세트에 없다')

# ---------- V9 Jev 없는 작은 LLM 전문가 구조(§19: 관문·기준 E4B / 짚기·검증 12B — 배치는 §19 에서 heavy 개발용으로 고른 값 고정) ----------
if all(os.path.exists(R(f'llm_tasks_out_{w}.json')) for w in EV):
    import eval_pipeline as _EP
    _TO = {w: J(R(f'llm_tasks_out_{w}.json')) for w in EV}
    _CFG = ('gemma4:e4b', 'gemma4:e4b', 'gemma4:12b')

    def p_v9(w, i):
        p, calls, how = _EP.run_one(i, _CFG, SETS[w]['qs'], SETS[w]['items'], _TO[w])
        return (p if not isinstance(p, tuple) else None), len(calls)
    P['V9 전문가 구조(Jev 없음, E4B/E4B/12B)'] = p_v9
else:
    NOTES.append('V9: 전문가 구조 결과(llm_tasks_out)가 시험 세트에 모두 있지는 않다')

# ---------- §50 Y2 분류 게이트 ----------
GATE = {}
for tag_ in ('base', 'e16d'):
    f = load_opt(R(f'gate_p_{tag_}.json'))
    if f:
        GATE[tag_] = {w: {int(k): v for k, v in d.items()} for w, d in f['p'].items()}
        GATE[tag_ + '_chat'] = f['chat_test']


def make_y2(tag_, tau):
    def f(w, i):
        st = stage(w, i)
        if st[0] == 'done':
            return st[1], int(bool(st[2]))
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        s1 = d[k]
        if s1 >= hi:
            return k, 0
        if s1 < lo:
            return (G[w][M][i], 1) if GATE[tag_][w][i] >= tau else (None, 0)
        return G[w][M][i], 1
    return f


for tag_, lab_ in (('base', 'Y2 게이트(고정 임베딩)'), ('e16d', 'Y2 게이트(e16d 임베딩)')):
    if tag_ in GATE and all(w in GATE[tag_] and GATE[tag_][w] for w in LABELED + EV):
        TAU['Y2' + tag_] = pick_tau(lambda t, tg=tag_: make_y2(tg, t))
        P[lab_] = make_y2(tag_, TAU['Y2' + tag_])
    else:
        NOTES.append(f'{lab_}: 게이트 확률 파일이 없다')

# ---------- 채점 ----------
names = list(P)
res = {}
for w in EV:
    res[w] = {n: [P[n](w, i) for i in range(len(SETS[w]['qs']))] for n in names}
gold = {w: [x['gold'] for x in SETS[w]['qs']] for w in EV}


def vec(n, ws):
    return [int(res[w][n][i][0] == gold[w][i]) for w in ws for i in range(len(gold[w]))]


def stats(n, ws):
    ok = bad = calls = 0
    for w in ws:
        for i, (p, c) in enumerate(res[w][n]):
            ok += p == gold[w][i]
            bad += p is not None and p != gold[w][i]
            calls += c
    return ok, bad, calls


def pexact(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def ci(a, b, n):
    d = [1] * a + [-1] * b + [0] * (n - a - b)
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in range(n)) / n * 100 for _ in range(2000))
    return (a - b) / n * 100, bs[49], bs[1949]


out = [f'## 최종 채점 — 시험 세트 {", ".join(f"{w}({len(gold[w])})" for w in EV)} · 앞단 e16d 문턱 {lo}/{hi} · B0 {loC}/{hiC}' + (f' · e16g {loG}/{hiG}' if CG is not None else '') + f' · τ {TAU}']
for n_ in NOTES:
    out.append(f'- ※ {n_}')
tot_n = sum(len(gold[w]) for w in EV)
out += ['', '| 방식 | ' + ' | '.join(f'{w} 정답' for w in EV) + f' | **합 {tot_n}** | 엉뚱한 답 | 호출 |', '|---|' + '---:|' * (len(EV) + 3)]
for n in names:
    cells = [str(stats(n, [w])[0]) for w in EV]
    ok, bad, calls = stats(n, EV)
    out.append(f'| {n} | ' + ' | '.join(cells) + f' | **{ok}** ({ok / tot_n:.1%}) | {bad} | {calls} |')
ref = {}
for w in EV:
    for m_, lab in ((k26(w), '26B 직접'), (M12, '12B 직접'), (M, 'E4B QAT 직접')):
        if m_ and m_ in G[w]:
            ref.setdefault(lab, {})[w] = G[w][m_]
    f = load_opt(R(f'jev_out_{w}.json'))
    if f:
        jp = []
        for r in f[w]['rows']:
            pr = r['probs']
            k = max(pr, key=pr.get) if pr else 'none'
            jp.append(int(k.split('_')[1]) if k.startswith('item_') else None)
        ref.setdefault('Jev 직접(유료)', {})[w] = jp
    for dtag, dlab in (('winnow12b', 'Winnow-12B Q8 직접'), ('nimble9b', 'Nimble-9B-v3 Q8 직접'), ('kev9b', 'Kev-9B Q8 직접'), ('kev4b', 'Kev-4B Q8 직접'),
                       ('decider4b', 'Decider-4B v2.1 Q8 직접'), ('laya', 'Laya Q8 직접'), ('malkuth4b', 'Malkuth-4B 직접'), ('imajev4b', 'Imajev-4B 직접')):
        fd = load_opt(R(f'dec_{dtag}_{w}.json'))
        if fd and w in fd and fd.get('_errors', 1) < len(fd[w]['rows']):
            jp = []
            for r in fd[w]['rows']:
                pr = r['probs']
                k = max(pr, key=pr.get) if pr else 'none'
                jp.append(int(k.split('_')[1]) if k.startswith('item_') else None)
            ref.setdefault(dlab, {})[w] = jp
    for lab, proto in (('Codex luna 직접', False), ('Codex luna+정의 직접', True)):
        if LUNA[w][proto] is not None:
            ref.setdefault(lab, {})[w] = LUNA[w][proto]
out += ['', '### 참고(직접 짚기 — 규칙·앞단 없음, 호출은 문제 수만큼)', '| 방식 | ' + ' | '.join(f'{w} 정답' for w in EV) + ' | 합 | 엉뚱한 답 | V1 과 짝지은 차이 %p [구간] (그 방식만 : V1 만, p) |', '|---|' + '---:|' * (len(EV) + 2) + '---|']
_v1 = vec('V1 앞단 e16d', EV)
for lab, d in ref.items():
    if not all(w in d for w in EV):
        continue
    oks = [sum(d[w][i] == gold[w][i] for i in range(len(gold[w]))) for w in EV]
    bad = sum(d[w][i] is not None and d[w][i] != gold[w][i] for w in EV for i in range(len(gold[w])))
    _v = [int(d[w][i] == gold[w][i]) for w in EV for i in range(len(gold[w]))]
    _a = sum(x == 1 and y == 0 for x, y in zip(_v, _v1))
    _b = sum(x == 0 and y == 1 for x, y in zip(_v, _v1))
    _d, _l, _h = ci(_a, _b, tot_n)
    out.append(f'| {lab} | ' + ' | '.join(map(str, oks)) + f' | **{sum(oks)}** ({sum(oks) / tot_n:.1%}) | {bad} | {_d:+.1f} [{_l:+.1f}, {_h:+.1f}] ({_a} : {_b}, p={pexact(_a, _b):.3f}) |')
out += ['', '### V1 과 짝지은 비교(합친 시험 세트 · 정확검정 · 짝지은 부트스트랩 95% 구간)', '| 방식 | 그 방식만 맞음 | V1 만 맞음 | 차이 %p [구간] | p |', '|---|---:|---:|---|---:|']
v1 = vec('V1 앞단 e16d', EV)
for n in names:
    if n.startswith('V1 '):
        continue
    a = sum(x == 1 and y == 0 for x, y in zip(vec(n, EV), v1))
    b = sum(x == 0 and y == 1 for x, y in zip(vec(n, EV), v1))
    d, l, h = ci(a, b, tot_n)
    out.append(f'| {n} | {a} | {b} | {d:+.1f} [{l:+.1f}, {h:+.1f}] | {pexact(a, b):.3f} |')
if len(EV) > 1:
    out += ['', '### 세트별 V1 대비 차이(그 방식만 맞음 : V1 만 맞음)', '| 방식 | ' + ' | '.join(EV) + ' |', '|---|' + '---:|' * len(EV)]
    for n in names:
        if n.startswith('V1 '):
            continue
        cells = []
        for w in EV:
            a = sum(x == 1 and y == 0 for x, y in zip(vec(n, [w]), vec('V1 앞단 e16d', [w])))
            b = sum(x == 0 and y == 1 for x, y in zip(vec(n, [w]), vec('V1 앞단 e16d', [w])))
            cells.append(f'{a} : {b}')
        out.append(f'| {n} | ' + ' | '.join(cells) + ' |')
types = sorted({x['type'] for w in EV for x in SETS[w]['qs']})
show = [n for n in names if n.split(' ')[0] in ('V1', 'B0', 'L3', 'C2', 'V4', 'V10', 'V11')]
out += ['', '### 유형별 정답(합친 시험 세트)', '| 유형 | 문제 | ' + ' | '.join(n.split(' ')[0] for n in show) + ' |', '|---|---:|' + '---:|' * len(show)]
for t in types:
    ids = [(w, i) for w in EV for i, x in enumerate(SETS[w]['qs']) if x['type'] == t]
    out.append(f'| {t} | {len(ids)} | ' + ' | '.join(str(sum(res[w][n][i][0] == gold[w][i] for w, i in ids)) for n in show) + ' |')
# 잡담 부작용(앞 1,500개, mix7 일정, 앞단만 + 넘김 E4B QAT): V1 대 Y2 — 항목으로 답한 비율
if any(k.startswith('Y2') for k in names):
    try:
        E4c = J(R('chat_llm_mix7_gemma4_e4b-it-qat.json'))['picks']
        sims = J(R('chat_front_mix7_e16d.json'))['sims']
        NC = 1500
        mx = [max(r) for r in sims[:NC]]

        def answered(tag_, tau):
            routed = ans = 0
            for k in range(NC):
                if mx[k] >= hi:
                    ans += 1
                elif mx[k] >= lo:
                    routed += 1
                    ans += E4c[str(k)] is not None
                elif tag_ is not None and GATE[tag_ + '_chat'][k] >= tau:
                    routed += 1
                    ans += E4c[str(k)] is not None
            return routed, ans
        r0 = answered(None, 0)
        out.append('')
        out.append(f'### 잡담 부작용(AI Hub 잡담 앞 {NC}개 — 항목으로 답한 비율, 정답은 항상 「없음」)')
        out.append(f'| 방식 | LLM 으로 넘김 | 항목으로 답함 |\n|---|---:|---:|\n| V1 앞단 e16d | {r0[0] / NC:.1%} | {r0[1]}/{NC} = {r0[1] / NC:.2%} |')
        for tag_, lab_ in (('base', 'Y2 게이트(고정 임베딩)'), ('e16d', 'Y2 게이트(e16d 임베딩)')):
            if 'Y2' + tag_ in TAU:
                r = answered(tag_, TAU['Y2' + tag_])
                out.append(f'| {lab_} τ_g={TAU["Y2" + tag_]} | {r[0] / NC:.1%} | {r[1]}/{NC} = {r[1] / NC:.2%} |')
    except Exception as e_:  # noqa: BLE001
        out.append(f'(잡담 부작용 계산 실패: {e_})')
if 'JEV_CALLS' in globals():
    out.append('')
    out.append('J1 의 Jev(유료) 호출 수: ' + ' · '.join(f'{w} {JEV_CALLS[w]}건' for w in EV) + ' — 규칙 단계가 못 정한 문제 전부를 한 번씩(이미 보낸 결과를 재사용했고 새로 부르지 않았다)')
print('\n'.join(out))
if '--md' in argv0:
    open(argv0[argv0.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
