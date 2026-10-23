# §67-2 — 둘 다 찾기(C)를 결정 모델의 저장된 확률로 오프라인 계산한다(새 추론 없음).
#  집합 = {확률 ≥ τ 인 일정 항목}, 최고 확률이 일정 항목이면 항상 포함. 「none」이 최고이고 τ 이상 항목이 없으면 빈 집합. τ ∈ {0.10, 0.15, 0.25, 0.35, 0.50}.
#  τ 는 개발 mix8+mix9 에서 C 정확(집합이 gold_set 과 같음)이 가장 높은 값(동률이면 큰 τ), 시험은 mix10·mix11·mix12.
# 사용: python eval_c_offline.py   → results/export/c_offline.csv · results/c_offline_mix8to12.md
import json, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
R = lambda n: os.path.join(HERE, 'results', n)
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
DEV, TEST = ['mix8', 'mix9'], ['mix10', 'mix11', 'mix12']
TAUS = [0.10, 0.15, 0.25, 0.35, 0.50]
GS = json.load(open(fixture('gold_sets.json'), encoding='utf-8'))
QT = {w: [q['type'] for q in json.load(open(fixture(f'{w}.json'), encoding='utf-8'))['sets'][w]['qs']] for w in SETS}
MODELS = [('decider-chat 31B', 'decider31bl'), ('OpenJev 26B', 'openjev26b'), ('Decider-12B bf16', 'decider12bl'), ('pplx-decider 27B', 'pplx27b'), ('Rune v3', 'rune26b')]


def norm(p):
    s = sum(p.values())
    return {k: v / s for k, v in p.items()} if s > 0 else p


def load(tag, w):
    return [norm(r['probs']) for r in json.load(open(R(f'dec_{tag}_{w}.json'), encoding='utf-8'))[w]['rows']]


P = {lab: {w: load(tag, w) for w in SETS} for lab, tag in MODELS}
# E1: OpenJev·31B·pplx 확률 평균
E1 = {}
for w in SETS:
    rows = []
    for i in range(len(P['OpenJev 26B'][w])):
        t = {}
        for lab in ('OpenJev 26B', 'decider-chat 31B', 'pplx-decider 27B'):
            for k, v in P[lab][w][i].items():
                t[k] = t.get(k, 0.0) + v / 3
        rows.append(t)
    E1[w] = rows
P['E1 확률 평균(OpenJev·31B·pplx)'] = E1


def pred(p, tau):
    top = max(p, key=p.get)
    s = {int(k.split('_')[1]) for k, v in p.items() if k.startswith('item_') and v >= tau}
    if top.startswith('item_'):
        s.add(int(top.split('_')[1]))
    return s


def score(S, G):
    G = set(G)
    exact = int(S == G)
    hit = int((S & G) != set() or (not S and not G))
    if not S and not G:
        f1 = 1.0
    elif not S or not G:
        f1 = 0.0
    else:
        tp = len(S & G)
        pr, rc = tp / len(S), tp / len(G)
        f1 = 0.0 if tp == 0 else 2 * pr * rc / (pr + rc)
    return exact, hit, f1


rec = []
for m, byset in P.items():
    for tau in TAUS:
        for w in SETS:
            for i, p in enumerate(byset[w]):
                e, h, f = score(pred(p, tau), GS[w][str(i)])
                rec.append((m, tau, w, i, QT[w][i], e, h, f))
df = pd.DataFrame(rec, columns=['model', 'tau', 'set', 'q_index', 'q_type', 'exact', 'hit', 'f1'])
df['compound'] = df['q_type'] == 'compound_intent'
df.to_csv(R(os.path.join('export', 'c_offline.csv')), index=False, encoding='utf-8-sig')
L = ['# 둘 다 찾기(C) — 결정 모델 오프라인(저장된 확률), mix8~12', '',
     '집합 = 확률 ≥ τ 인 일정 항목(최고 확률이 항목이면 항상 포함). 「C 정확」 = 집합이 정답 목록과 같음. τ 는 개발(mix8+9)에서 고르고 시험은 mix10~12(합 499문제).', '',
     '| 모델 | 고른 τ | 개발 C 정확 | 시험 C 정확 | 시험 하나라도 맞힘(B식) | 시험 요청 둘만 C 정확 | 시험 F1 |', '|---|---:|---|---|---|---|---:|']
for m in P:
    g = df[df['model'] == m]
    dev = g[g['set'].isin(DEV)].groupby('tau')['exact'].agg(['sum', 'size'])
    best = max(TAUS, key=lambda t: (dev.loc[t, 'sum'], t))
    d = g[(g['tau'] == best) & g['set'].isin(DEV)]
    t = g[(g['tau'] == best) & g['set'].isin(TEST)]
    tc = t[t['compound']]
    L.append(f"| {m} | {best} | {int(d['exact'].sum())}/{len(d)} ({100 * d['exact'].mean():.1f}%) | **{int(t['exact'].sum())}/{len(t)} ({100 * t['exact'].mean():.1f}%)** | {int(t['hit'].sum())}/{len(t)} | {int(tc['exact'].sum())}/{len(tc)} | {t['f1'].mean():.3f} |")
L += ['', '## τ 별 전체(5세트 835문제) C 정확', '', '| 모델 | ' + ' | '.join(f'τ={t}' for t in TAUS) + ' |', '|---|' + '---:|' * len(TAUS)]
for m in P:
    g = df[df['model'] == m]
    L.append(f'| {m} | ' + ' | '.join(f"{int(g[g['tau'] == t]['exact'].sum())}" for t in TAUS) + ' |')
open(R('c_offline_mix8to12.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))
