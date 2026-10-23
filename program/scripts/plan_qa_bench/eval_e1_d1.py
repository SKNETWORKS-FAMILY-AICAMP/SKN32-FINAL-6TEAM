# §60-2 에서 mix11 결과를 보기 전에 고정한 후보 둘(E1·D1)을 4세트 합산(mix8~11)에서 판정한다. 다른 조합은 만들지 않는다.
#  E1 = OpenJev 26B · decider-chat 31B · pplx 27B 의 확률 평균(정규화 후 합)
#  D1 = Decider-12B(bf16) 최고 확률 ≥ 0.9 이면 그 답, 아니면 Qwen3.8 27B 의 답
#  비교: 31B · Qwen3.8 27B · Gemma 26B 직접. 짝지은 정확 McNemar(양쪽), 「이겼다」 = 점추정 앞서고 p < 0.025(후보 둘).
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
R = lambda n: os.path.join(HERE, 'results', n)
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
GOLD = {w: [x['gold'] for x in json.load(open(fixture(f'{w}.json'), encoding='utf-8'))['sets'][w]['qs']] for w in SETS}


def probs(tag, w):
    return [r['probs'] for r in json.load(open(R(f'dec_{tag}_{w}.json'), encoding='utf-8'))[w]['rows']]


def pick(k):
    return int(k.split('_')[1]) if k.startswith('item_') else None


def norm(p):
    s = sum(p.values())
    return {k: v / s for k, v in p.items()}


P = {t: {w: probs(t, w) for w in SETS} for t in ('openjev26b', 'decider31bl', 'pplx27b', 'decider12bl')}
LLM = {w: json.load(open(R(f'llm_{w}_out.json'), encoding='utf-8')) for w in SETS}
V = {}
V['31B 직접'] = {w: [pick(max(p, key=p.get)) for p in P['decider31bl'][w]] for w in SETS}
V['Qwen3.8 27B 직접'] = {w: LLM[w]['qwen3.8:27b']['picks'] for w in SETS}
V['Gemma 26B 직접'] = {w: LLM[w]['gemma4:26b-a4b-it-q4_K_M']['picks'] for w in SETS}
E1, D1 = {}, {}
for w in SETS:
    out = []
    for i in range(len(GOLD[w])):
        t = {}
        for tag in ('openjev26b', 'decider31bl', 'pplx27b'):
            for k, v in norm(P[tag][w][i]).items():
                t[k] = t.get(k, 0.0) + v
        out.append(pick(max(t, key=t.get)))
    E1[w] = out
    d = []
    for i, p in enumerate(P['decider12bl'][w]):
        q = norm(p)
        k = max(q, key=q.get)
        d.append(pick(k) if q[k] >= 0.9 else V['Qwen3.8 27B 직접'][w][i])
    D1[w] = d
V['E1 확률 평균(OpenJev·31B·pplx)'] = E1
V['D1 Decider-12B → Qwen3.8(τ 0.9)'] = D1


def vec(v, sets=None):
    return [int(v[w][i] == GOLD[w][i]) for w in (sets or SETS) for i in range(len(GOLD[w]))]


def mcnemar(a, b):
    n10 = sum(1 for x, y in zip(a, b) if x and not y)
    n01 = sum(1 for x, y in zip(a, b) if y and not x)
    n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    k = min(n10, n01)
    p = min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)
    return n10, n01, p


N = sum(len(g) for g in GOLD.values())
print(f'5세트 합산 {N}문제')
for n, v in V.items():
    x = vec(v)
    per = ' · '.join(f"{sum(int(v[w][i] == GOLD[w][i]) for i in range(len(GOLD[w])))}/{len(GOLD[w])}" for w in SETS)
    print(f'{n}: {sum(x)}/{N} = {100 * sum(x) / N:.1f}%  ({per})')
print()
for label, ss in (('5세트 합산(개발 mix8·mix9 와 탐색에 쓴 mix10 포함 — 낙관적)', SETS), ('mix8~mix11 합산(작성자 Codex 네 세트)', SETS[:4]), ('mix11 만(후보 고정 뒤 처음 본 세트 — 깨끗한 확인)', ['mix11']), ('mix12 만(작성자 Claude — 두 번째 깨끗한 확인)', ['mix12'])):
    NN = sum(len(GOLD[w]) for w in ss)
    print(f'--- {label} {NN}문제')
    for n in ('31B 직접', 'Qwen3.8 27B 직접', 'Gemma 26B 직접', 'E1 확률 평균(OpenJev·31B·pplx)', 'D1 Decider-12B → Qwen3.8(τ 0.9)'):
        print(f'  {n}: {sum(vec(V[n], ss))}/{NN}')
    for cand in ('E1 확률 평균(OpenJev·31B·pplx)', 'D1 Decider-12B → Qwen3.8(τ 0.9)'):
        a = vec(V[cand], ss)
        for ref in ('31B 직접', 'Qwen3.8 27B 직접', 'Gemma 26B 직접'):
            b = vec(V[ref], ss)
            n10, n01, p = mcnemar(a, b)
            verdict = '이김' if sum(a) > sum(b) and p < 0.025 else ('졌음' if sum(b) > sum(a) and p < 0.025 else '구분되지 않음')
            print(f'  {cand} vs {ref}: {sum(a) - sum(b):+d}문제 (후보만 맞음 {n10} · 기준만 맞음 {n01}, 정확 McNemar p={p:.3f}) → {verdict}')
calls = sum(1 for w in SETS for i, p in enumerate(P['decider12bl'][w]) if max(norm(p).values()) < 0.9)
print(f'D1 이 Qwen3.8 로 넘긴 문제(5세트): {calls}/{N} = {100 * calls / N:.1f}%')
