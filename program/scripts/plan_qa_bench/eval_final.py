# 최종 판정 — 처음 보는 독립 세트(mix5, 다른 일정)에서 「학습 임베딩 0.6B + 구조 + 소형 넘김」을 한 번만 잰다.
#  문턱(lo·hi)은 heavy 개발용 44문제(같은 학습 모델의 점수)로만 고르고, 넘김 모델은 사전에 정한 것(E4B·E2B)을 그대로 쓴다. mix5 로는 고르지 않는다.
#  비교: 같은 mix5 에서 Gemma 26B·12B·E4B·E2B 직접 짚기.
# 사용: python eval_final.py <FT 점수 키> <heavy 점수 파일> <mix5 점수 파일> [넘김 모델,...]
import json, math, os, sys
from collections import defaultdict
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
KEY, F_HEAVY, F_MIX5 = sys.argv[1:4]
FBS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['gemma4:e4b', 'gemma4:e2b']
J = lambda f: json.load(open(f, encoding='utf-8'))
pairs_h = J(os.path.join(HERE, 'fixtures', 'pairs_experts.json'))
pairs_5 = J(os.path.join(HERE, 'fixtures', 'pairs_mix5.json'))
S = defaultdict(dict)
for pr, f in ((pairs_h, F_HEAVY), (pairs_5, F_MIX5)):
    for p, v in zip(pr, J(f)[KEY]):
        S[(p['set'], p['qi'])][p['item']] = v
SET = {j: J(fixture(f'{j}.json'))['sets'][j] for j in ('heavy', 'mix5')}
G = {j: J(os.path.join(HERE, 'results', f'llm_{j}_out.json')) for j in ('heavy', 'mix5')}
for _j in list(G):        # GEPA식으로 최적화한 E4B 프롬프트의 답(서버 eval_prompt --dump 결과)을 넘김 모델 「gepa_e4b」 로 쓸 수 있게 한다
    _f = os.path.join(HERE, 'results', f'gepa_e4b_{_j}.json')
    if os.path.exists(_f):
        G[_j]['gepa_e4b'] = json.load(open(_f, encoding='utf-8'))



def top(job, kind, i):
    d = S.get((f'{job}_{kind}', i))
    if not d:
        return None, 0.0
    k = max(d, key=d.get)
    return k, d[k]


def run(job, i, lo, hi, fb, tau_a=0.4):
    st = SET[job]
    qs, items = st['qs'], st['items']
    x = qs[i]
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    if rs['day'] is None:
        rs['day'] = rule_slots(x['q'], items)['day']
    anchor = None
    if rs['rel'] is not None:
        k, p = top(job, 'excl' if a['negation'] else 'tt', i)
        anchor = k if p >= tau_a else None
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = anchor
    r = resolve(items, slots)
    if r[0] == 'item':
        return r[1], False
    if r[0] == 'none':
        return None, False
    llm = G[job][fb]['picks'][i]
    if x['history']:
        return llm, True
    k, p = top(job, 'tt', i)
    if p >= hi:
        return k, False
    if p < lo:
        return None, False
    return llm, True


def evaluate(job, idx, lo, hi, fb):
    qs = SET[job]['qs']
    ok = bad = miss = calls = 0
    bt = defaultdict(int)
    for i in idx:
        p, used = run(job, i, lo, hi, fb)
        g = qs[i]['gold']
        ok += (p == g); bad += (p is not None and p != g); miss += (p is None and g is not None); calls += used
        bt[qs[i]['type']] += (p == g)
    return ok, bad, miss, calls, bt


grid = [(lo, hi) for lo in (0.15, 0.25, 0.3, 0.35, 0.4, 0.45) for hi in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75) if lo < hi]
dev = [i for i, x in enumerate(SET['heavy']['qs']) if x['split'] == 'dev']
mix = list(range(len(SET['mix5']['qs'])))
print(f'## 최종 판정: mix5(다른 일정 · 처음 보는 88문제) — 앞단 {KEY}')
for fb in FBS:
    best = max(grid, key=lambda g: (evaluate('heavy', dev, *g, fb)[0] - 2 * evaluate('heavy', dev, *g, fb)[1] - 0.05 * evaluate('heavy', dev, *g, fb)[3], -g[0]))
    r = evaluate('mix5', mix, *best, fb)
    print(f"  구조 + 넘김 {fb:<12} (문턱 lo={best[0]} hi={best[1]}, heavy 개발용으로 선택): 정답 {r[0]}/{len(mix)}={r[0] / len(mix):.0%} · 엉뚱 {r[1]} · 못 찾음 {r[2]} · 넘김 호출 {r[3]}/{len(mix)}={r[3] / len(mix):.0%}")
    print('    유형별:', dict(r[4]))
print('  비교(직접 짚기, 일정 전체 제시):')
qs5 = SET['mix5']['qs']
for m in ('gemma4:26b', 'gemma4:12b', 'gemma4:e4b', 'gemma4:e2b'):
    if m in G['mix5']:
        p = G['mix5'][m]['picks']
        ok = sum(p[i] == qs5[i]['gold'] for i in mix)
        bad = sum(p[i] is not None and p[i] != qs5[i]['gold'] for i in mix)
        miss = sum(p[i] is None and qs5[i]['gold'] is not None for i in mix)
        print(f"    {m:<12} 정답 {ok}/{len(mix)}={ok / len(mix):.0%} · 엉뚱 {bad} · 못 찾음 {miss}")
