# §64-2 사전 등록 — conformal 위임(저장된 확률만 쓴다, 새 추론 없음).
#  작은 모델 = Decider-12B(bf16) 확률, 큰 모델 = Qwen3.8 27B 짚은 답(대안: 31B 1순위). 보정 = mix8+9+10, 시험 = --test 로 준 세트(mix11, 나중에 mix12).
#  비교: 넘김 비율을 맞춘 확신 문턱 규칙(문턱 τ′ = 시험 세트에서 같은 문제 수를 넘기는 값).
# 사용: python eval_conformal.py [--test mix11[,mix12]]
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
R = lambda n: os.path.join(HERE, 'results', n)
CAL = ['mix8', 'mix9', 'mix10']
TEST = sys.argv[sys.argv.index('--test') + 1].split(',') if '--test' in sys.argv else ['mix11']
ALPHAS = [0.02, 0.05, 0.10]
ALLS = CAL + TEST
GOLD = {w: [x['gold'] for x in json.load(open(fixture(f'{w}.json'), encoding='utf-8'))['sets'][w]['qs']] for w in ALLS}


def norm(p):
    s = sum(p.values())
    return {k: v / s for k, v in p.items()}


def load(tag, w):
    return [norm(r['probs']) for r in json.load(open(R(f'dec_{tag}_{w}.json'), encoding='utf-8'))[w]['rows']]


def pick(k):
    return int(k.split('_')[1]) if k.startswith('item_') else None


def gkey(g):
    return 'none' if g is None else f'item_{g}'


SM = {w: load('decider12bl', w) for w in ALLS}
BIG = {w: json.load(open(R(f'llm_{w}_out.json'), encoding='utf-8'))['qwen3.8:27b']['picks'] for w in ALLS}
B31 = {w: [pick(max(p, key=p.get)) for p in load('decider31bl', w)] for w in ALLS}


def scores(ws):
    return [1 - SM[w][i].get(gkey(GOLD[w][i]), 0.0) for w in ws for i in range(len(GOLD[w]))]


def qhat(sc, alpha):
    n = len(sc)
    k = min(n, math.ceil((n + 1) * (1 - alpha)))
    return sorted(sc)[k - 1]


def mcnemar(a, b):
    n10 = sum(1 for x, y in zip(a, b) if x and not y)
    n01 = sum(1 for x, y in zip(a, b) if y and not x)
    n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    k = min(n10, n01)
    return n10, n01, min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)


def run(cal_ws, test_ws, alpha, big):
    q = qhat(scores(cal_ws), alpha)
    out, deleg, cover, sizes = [], 0, 0, []
    pm = []
    for w in test_ws:
        for i, p in enumerate(SM[w]):
            C = [k for k, v in p.items() if 1 - v <= q]
            sizes.append(len(C))
            cover += gkey(GOLD[w][i]) in C
            top = max(p, key=p.get)
            pm.append((p[top], w, i))
            if len(C) == 1:
                out.append((w, i, pick(C[0]), 0))
            else:
                out.append((w, i, big[w][i], 1))
                deleg += 1
    return q, out, deleg, cover, sizes, pm


def ok(out):
    return [int(a == GOLD[w][i]) for w, i, a, _d in out]


print(f'보정 {"+".join(CAL)}({sum(len(GOLD[w]) for w in CAL)}문제) · 시험 {"+".join(TEST)}({sum(len(GOLD[w]) for w in TEST)}문제)')
NT = sum(len(GOLD[w]) for w in TEST)
small = [int(pick(max(SM[w][i], key=SM[w][i].get)) == GOLD[w][i]) for w in TEST for i in range(len(GOLD[w]))]
bigv = [int(BIG[w][i] == GOLD[w][i]) for w in TEST for i in range(len(GOLD[w]))]
b31 = [int(B31[w][i] == GOLD[w][i]) for w in TEST for i in range(len(GOLD[w]))]
print(f'참고: 작은 모델 단독 {sum(small)}/{NT} · Qwen3.8 단독 {sum(bigv)}/{NT} · 31B 단독 {sum(b31)}/{NT}')
for bn, big in (('Qwen3.8 27B', BIG), ('31B', B31)):
    print(f'\n=== 큰 모델 = {bn}')
    for a in ALPHAS:
        q, out, deleg, cover, sizes, pm = run(CAL, TEST, a, big)
        conf = ok(out)
        # 넘김 비율을 맞춘 확신 문턱: 확률이 낮은 deleg 개를 넘긴다
        low = set((w, i) for _p, w, i in sorted(pm)[:deleg])
        thr = [int((big[w][i] if (w, i) in low else pick(max(SM[w][i], key=SM[w][i].get))) == GOLD[w][i]) for w in TEST for i in range(len(GOLD[w]))]
        n10, n01, p = mcnemar(conf, thr)
        print(f'α={a}: q̂={q:.3f} · 정답 {sum(conf)}/{NT} · 넘김 {deleg}/{NT}({100 * deleg / NT:.1f}%) · 커버리지 {cover}/{NT}({100 * cover / NT:.1f}%, 목표 ≥{100 * (1 - a):.0f}%) · 집합 크기 1:{sizes.count(1)} 2+:{sum(1 for s in sizes if s > 1)}'
              f' | 넘김 비율 맞춘 문턱 {sum(thr)}/{NT} → conformal {sum(conf) - sum(thr):+d}(conformal 만 맞음 {n10} · 문턱만 맞음 {n01}, p={p:.3f})')
print('\n[참고] 보정 세트 안 교차 확인(두 세트로 보정, 한 세트로 시험 — 보장이 지켜지는지만 본다)')
for t in CAL:
    cal = [w for w in CAL if w != t]
    for a in ALPHAS:
        q = qhat(scores(cal), a)
        cov = sum(gkey(GOLD[t][i]) in [k for k, v in SM[t][i].items() if 1 - v <= q] for i in range(len(GOLD[t])))
        print(f'  시험 {t} α={a}: 커버리지 {cov}/{len(GOLD[t])} = {100 * cov / len(GOLD[t]):.1f}% (목표 ≥{100 * (1 - a):.0f}%)')
