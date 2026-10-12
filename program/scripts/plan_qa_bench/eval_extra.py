# §42 추가 방식의 오프라인 채점 — 저장된 결과만 쓴다(서버·비용 없음).
#  V5 RL 식 정책(소프트맥스 선형 정책 + REINFORCE) · V7 Codex 앞단(C1 규칙→luna · C2 규칙→앞단 확정→luna) · V8 LLM 앞단(L1~L4: 규칙 → E4B QAT / 12B / 26B / E4B QAT→26B 승격)
#  기본(참고): 기존 5세트(heavy 판정 88·mix4·mix5·mix6·mix7) 교차검증(V5) · --final: mix8 한 번(학습은 기존 5세트)
# 사용: python eval_extra.py [--final] [--md 출력파일]
import json, math, os, random, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = '--final' in sys.argv
argv0 = sys.argv
sys.argv = ['x', 'e16d'] + (['--final', 'mix8'] if FINAL else [])
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, G, run, pipe, grid, dev, S = (G0[k] for k in ('SETS', 'G', 'run', 'pipe', 'grid', 'dev', 'S'))
stage, DATA, LABELED, M, feats = (G0[k] for k in ('stage', 'DATA', 'LABELED', 'M', 'feats'))
R, J = G0['R'], G0['J']
EVAL = ['mix8'] if FINAL else LABELED
best = max(grid, key=lambda g: (pipe('heavy', dev, *g, M)[0] - 2 * pipe('heavy', dev, *g, M)[1] - 0.05 * pipe('heavy', dev, *g, M)[2], -g[0]))
lo, hi = best


def idx_of(w):
    return [i for i in range(len(SETS[w]['qs'])) if not (w == 'heavy' and SETS[w]['qs'][i].get('split') != 'held')]


def key26(w):
    for k in ('gemma4:26b-a4b-it-q4_K_M', 'gemma4:26b'):
        if k in G[w]:
            return k
    return None


def luna(w, proto):
    f = R(f'codex_gpt-6-luna_{w}' + ('_proto' if proto else '') + '.json')
    d = J(f)[w]
    return [d.get(str(i)) for i in range(len(SETS[w]['qs']))]


LUNA = {w: {False: luna(w, False), True: luna(w, True)} for w in EVAL}
VP = {}
for w in LABELED + (['mix8'] if FINAL else []):
    f = R(f'verify_{w}_gemma4_e4b-it-qat.json')
    if os.path.exists(f):
        VP[w] = {int(k): v for k, v in J(f)['p'].items()}


def l4_tau():
    if not all(w in VP for w in LABELED):
        return None
    best_u = None
    for k in range(1, 20):
        tau = k * 0.05
        u = 0.0
        for w in LABELED:
            for i in idx_of(w):
                p, used = run(w, i, lo, hi, M)
                gold = SETS[w]['qs'][i]['gold']
                st = stage(w, i)
                if st[0] == 'done':
                    pr = st[1]
                else:
                    pe = G[w][M][i]
                    pr = pe
                    if pe is None or VP[w].get(i, 1.0) < tau:
                        pr = G[w][key26(w)][i]
                u += (pr == gold) - 2 * (pr is not None and pr != gold)
        if best_u is None or u > best_u[0] + 1e-9:
            best_u = (u, tau)
    return best_u[1]


TAU = l4_tau()


def methods(w):
    """방식 → (예측 목록, 문제별 호출 수 목록)"""
    qs = SETS[w]['qs']
    n = len(qs)
    out = {}
    k26 = key26(w)
    base = [run(w, i, lo, hi, M) for i in range(n)]
    out['V1 기준(앞단 e16d + E4B QAT)'] = ([p for p, _ in base], [int(u) for _, u in base])

    def build(fn):
        pr, cl = [], []
        for i in range(n):
            st = stage(w, i)
            if st[0] == 'done':
                pr.append(st[1])
                cl.append(int(bool(st[2])))
            else:
                p, c = fn(i)
                pr.append(p)
                cl.append(c)
        return pr, cl

    for name, key in (('L1 규칙→E4B QAT', M), ('L2 규칙→12B', 'gemma4:12b'), ('L3 규칙→26B', k26)):
        out[name] = build(lambda i, key=key: (G[w][key][i], 1))
    if TAU is not None and w in VP:
        def l4(i):
            pe = G[w][M][i]
            if pe is None or VP[w].get(i, 1.0) < TAU:
                return G[w][k26][i], 2
            return pe, 1
        out[f'L4 규칙→E4B QAT→(없음·비평<{TAU:.2f})→26B'] = build(l4)
    out['C1 규칙→luna'] = build(lambda i: (LUNA[w][False][i], 1))
    out['C1 규칙→luna+정의'] = build(lambda i: (LUNA[w][True][i], 1))

    def c2(i):
        d = S[(f'{w}_tt', i)]
        k = max(d, key=d.get)
        if d[k] >= hi:
            return k, 0
        return LUNA[w][True][i], 1
    out['C2 규칙→앞단 확정→luna+정의'] = build(c2)
    return out


# ---------- V5 RL 식 정책 ----------
def act_rewards(w, i, t1):
    gold = SETS[w]['qs'][i]['gold']
    acc = 1.0 if t1 == gold else -2.0
    non = 1.0 if gold is None else 0.0
    p = G[w][M][i]
    llm = (1.0 if p == gold else (0.0 if p is None else -2.0)) - 0.05
    return np.array([acc, non, llm])


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
        P = np.exp(lg)
        P /= P.sum(1, keepdims=True)
        a = np.array([rng.choice(3, p=p) for p in P])
        r = Rw[np.arange(len(a)), a]
        adv = r - r.mean()                                   # 평균 보상 기준선
        onehot = np.eye(3)[a]
        grad = Z.T @ ((onehot - P) * adv[:, None]) / len(Z)   # REINFORCE: ∇ log π · (보상 − 기준선)
        m = 0.9 * m + 0.1 * grad
        v = 0.999 * v + 0.001 * grad ** 2
        W += lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
    return mu, sd, W


def v5_pred(w, i, pol):
    mu, sd, W = pol
    f, t1 = feats(w, i)
    z = np.append((np.array(f) - mu) / sd, 1.0)
    a = int(np.argmax(z @ W))
    if a == 0:
        return t1, False
    if a == 1:
        return None, False
    return G[w][M][i], True


rows = {}
for w in EVAL:
    ms = methods(w)
    pol = train_policy(LABELED if FINAL else [s for s in LABELED if s != w])
    pr, cl = [], []
    for i in range(len(SETS[w]['qs'])):
        st = stage(w, i)
        if st[0] == 'done':
            p, u = st[1], st[2]
        else:
            p, u = v5_pred(w, i, pol)
        pr.append(p)
        cl.append(int(bool(u)))
    ms['V5 RL 식 정책'] = (pr, cl)
    rows[w] = ms
names = list(rows[EVAL[0]])
out = [f'## §42 추가 방식 오프라인 채점 — {"mix8 한 번(학습 = 기존 5세트)" if FINAL else "기존 5세트 참고(V5 는 세트 하나 빼고 학습)"} · 앞단 e16d 문턱 {lo}/{hi}(heavy 개발용 44 로 선택) · L4 τ={TAU}',
       '| 방식 | ' + ' | '.join(f'{w}({len(idx_of(w))})' for w in EVAL) + f' | **합** | 엉뚱한 답 | LLM·Codex 호출 |', '|---|' + '---:|' * (len(EVAL) + 4)]
tot_n = sum(len(idx_of(w)) for w in EVAL)
VEC = {}
for nme in names:
    ok = bad = calls = 0
    cells = []
    vec = []
    for w in EVAL:
        o = 0
        pr, cl = rows[w][nme]
        for i in idx_of(w):
            calls += cl[i]
            g = SETS[w]['qs'][i]['gold']
            o += pr[i] == g
            bad += pr[i] is not None and pr[i] != g
            vec.append(int(pr[i] == g))
        cells.append(str(o))
        ok += o
    VEC[nme] = vec
    out.append(f'| {nme} | ' + ' | '.join(cells) + f' | **{ok}**/{tot_n} ({ok / tot_n:.1%}) | {bad} | {calls} |')
base = names[0]


def pexact(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


out += ['', f'### {base} 와 짝지은 비교(정확검정)', '| 방식 | 그 방식만 맞음 | 기준만 맞음 | p |', '|---|---:|---:|---:|']
for nme in names[1:]:
    a = sum(x == 1 and y == 0 for x, y in zip(VEC[nme], VEC[base]))
    b = sum(x == 0 and y == 1 for x, y in zip(VEC[nme], VEC[base]))
    out.append(f'| {nme} | {a} | {b} | {pexact(a, b):.3f} |')
# 유형별 정답(세트 합) · 두 방식 중 하나라도 맞춘 문제 수(천장 — 선택 규칙이 없는 상한이라 달성 가능한 값이 아니다)
types = sorted({x['type'] for w in EVAL for x in SETS[w]['qs']})
ordr = [k for k in names if k.startswith(('V1', 'L3', 'C2', 'V5'))]
out += ['', '### 유형별 정답(세트 합)', '| 유형 | 문제 | ' + ' | '.join(k.split(' ')[0] for k in ordr) + ' |', '|---|---:|' + '---:|' * len(ordr)]
for t in types:
    cells = []
    nq = 0
    for k in ordr:
        o = 0
        nq = 0
        for w in EVAL:
            pr, _ = rows[w][k]
            for i in idx_of(w):
                if SETS[w]['qs'][i]['type'] == t:
                    nq += 1
                    o += pr[i] == SETS[w]['qs'][i]['gold']
        cells.append(str(o))
    out.append(f'| {t} | {nq} | ' + ' | '.join(cells) + ' |')
out += ['', '### 천장(둘 중 하나라도 맞춘 문제 수 — 어느 쪽을 믿을지 모르는 상한)', '| 쌍 | 합집합 정답 |', '|---|---:|']
vk = {k.split(' ')[0]: VEC[k] for k in names}
for a_, b_ in (('V1', 'L3'), ('V1', 'C2'), ('V1', 'V5'), ('C2', 'L3')):
    if a_ in vk and b_ in vk:
        out.append(f'| {a_} ∪ {b_} | {sum(x or y for x, y in zip(vk[a_], vk[b_]))}/{tot_n} |')
print('\n'.join(out))
if '--md' in argv0:
    open(argv0[argv0.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
