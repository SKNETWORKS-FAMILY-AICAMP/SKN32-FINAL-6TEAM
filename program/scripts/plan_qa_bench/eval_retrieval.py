# 소형 검색·재평가 모델(Qwen3-Reranker-4B/0.6B · WeMM-4B · Qwen3-Embedding-0.6B)의 후보 줄이기·「없음」 판정 능력 채점.
#  - 질문마다 항목 51개 점수 → 소프트맥스(온도는 heavy 개발용 44 에서만 고름) → 재현율@1·3·5 (정답이 있고 앞 대화가 필요 없는 문제)
#  - 「없음」 판정: 1위 점수의 문턱을 heavy 개발용에서만 골라 정답이 「없음」인 문제를 가르는 정확도(균형 정확도)
#  - A3 = 재평가4B + WeMM-4B 확률 평균(yok3x 표기). 투표가 아니라 점수 평균이며 사용자가 지정한 조합이다.
# 사용: python eval_retrieval.py
import json, math, os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
pairs = json.load(open(os.path.join(HERE, 'fixtures', 'pairs_experts.json'), encoding='utf-8'))
sc = json.load(open(os.path.join(HERE, 'results', 'expert_scores_out.json'), encoding='utf-8'))
import glob
for f in glob.glob(os.path.join(HERE, 'results', 'ft_*_scores.json')):
    sc.update(json.load(open(f, encoding='utf-8')))          # 학습시킨 전용 모델(ft/…)
JOB = {j: json.load(open(fixture(f'{j}.json'), encoding='utf-8'))['sets'][j]['qs'] for j in ('heavy', 'mix4')}
NAMES = {'ft/emb_e16b': 'FT임베딩0.6B(전용학습)', 'ft/r16a': 'FT재평가0.6B(전용학습)', 'Qwen/Qwen3-Reranker-4B': '재평가4B', 'tencent/WeMM-Embedding-4B': 'WeMM-4B', 'Qwen/Qwen3-Reranker-0.6B': '재평가0.6B', 'Qwen/Qwen3-Embedding-0.6B': '임베딩0.6B'}
S = {n: defaultdict(dict) for n in NAMES.values()}
for m, n in NAMES.items():
    if m not in sc:
        continue
    for p, v in zip(pairs, sc[m]):
        S[n][(p['set'], p['qi'])][p['item']] = v


def softmax(d, t):
    mx = max(d.values())
    e = {k: math.exp((v - mx) / t) for k, v in d.items()}
    z = sum(e.values())
    return {k: v / z for k, v in e.items()}


def items_dev():
    return [(i, x) for i, x in enumerate(JOB['heavy']) if x['split'] == 'dev' and x['gold'] is not None and not x['history']]


def temp_for(n):
    best = None
    for t in (0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5):
        nll = 0.0
        k = 0
        for i, x in items_dev():
            pr = softmax(S[n][('heavy_tt', i)], t)
            nll += -math.log(max(pr.get(x['gold'], 0), 1e-9))
            k += 1
        if best is None or nll / k < best[0]:
            best = (nll / k, t)
    return best[1]


T = {n: temp_for(n) for k, n in NAMES.items() if k in sc}
MODELS = [n for k, n in NAMES.items() if k in sc] + ['A3(재평가4B+WeMM-4B)', 'A3s(재평가0.6B+임베딩0.6B)']


def probs(model, job, i):
    key = (f'{job}_tt', i)
    if model.startswith('A3s'):
        a, b = probs('재평가0.6B', job, i), probs('임베딩0.6B', job, i)
    elif model.startswith('A3'):
        a, b = probs('재평가4B', job, i), probs('WeMM-4B', job, i)
    else:
        return softmax(S[model][key], T[model])
    return {k: (a[k] + b[k]) / 2 for k in a}


def topk(pr, k):
    return sorted(pr, key=pr.get, reverse=True)[:k]


def eval_set(job, idx):
    out = {}
    for m in MODELS:
        hit = {1: 0, 3: 0, 5: 0, 10: 0}
        n = 0
        for i in idx:
            x = JOB[job][i]
            if x['gold'] is None or x['history']:
                continue
            pr = probs(m, job, i)
            n += 1
            for k in hit:
                hit[k] += x['gold'] in topk(pr, k)
        out[m] = (hit, n)
    return out


held = [i for i, x in enumerate(JOB['heavy']) if x['split'] == 'held']
allm = list(range(len(JOB['mix4'])))
print('## 후보 재현율 (정답이 있고 앞 대화가 필요 없는 문제) — @1 / @3 / @5 / @10')
for job, idx, lab in (('heavy', held, 'heavy 판정'), ('mix4', allm, 'mix4(처음 보는 세트)')):
    r = eval_set(job, idx)
    print(f'  {lab}')
    for m in MODELS:
        h, n = r[m]
        print(f"    {m:<26} {h[1]}/{n}={h[1] / n:.0%} · {h[3]}/{n}={h[3] / n:.0%} · {h[5]}/{n}={h[5] / n:.0%} · @10 {h[10]}/{n}={h[10] / n:.0%}")

print('\n## 「없음」 판정 — 1위 확률 문턱(heavy 개발용에서 고름), 정답이 없는 문제를 가르는 균형 정확도')


def top1(m, job, i):
    pr = probs(m, job, i)
    return max(pr.values())


for m in MODELS:
    dev = [(top1(m, 'heavy', i), x['gold'] is None) for i, x in enumerate(JOB['heavy']) if x['split'] == 'dev']
    best = max((t / 100 for t in range(0, 100, 2)), key=lambda t: (sum(s < t for s, none in dev if none) / max(1, sum(none for _, none in dev)) + sum(s >= t for s, none in dev if not none) / max(1, sum(not none for _, none in dev))) / 2)
    row = []
    for job, idx in (('heavy', held), ('mix4', allm)):
        tp = tn = P = N = 0
        for i in idx:
            x = JOB[job][i]
            if x['history']:
                continue
            none = x['gold'] is None
            pred_none = top1(m, job, i) < best
            P += none; N += not none
            tp += none and pred_none; tn += (not none) and (not pred_none)
        row.append(f"{tp}/{P}  {tn}/{N}")
    print(f"  {m:<26} 문턱 {best:.2f} · heavy: 없음 잡음/맞는 것 유지 {row[0]} · mix4: {row[1]}")
