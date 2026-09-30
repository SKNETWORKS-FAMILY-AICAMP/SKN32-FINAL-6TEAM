# 학습시킨 소형 재평가 전문가(FT)를 전문가 구조에 붙여 재는 채점기.
#  흐름: ①절 분석 ②규칙 조회(기준 항목은 FT 가 짚는다) ③앞 대화가 있는 문제는 LLM(12B) ④그 밖은 FT 확신도로 갈림:
#        1위 확률 ≥ hi → 그 항목 · < lo → 「없음」 · 사이 → LLM(12B, 일정 전체) 으로 넘김. lo·hi 는 heavy 개발용 44문제로만 고른다.
#  비교용: 26B 직접 · 12B 직접 · 기존 구조(E4B/E4B/12B). 지표: 정답 수 · 엉뚱한 답 · 못 찾음 · LLM 을 부른 문제 비율.
# 사용: python eval_ft_pipeline.py <FT 점수 이름(예: ft/r16a)> [점수 파일들...]
import json, math, os, sys
from collections import defaultdict
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve
from eval_pipeline import load, run_one

HERE = os.path.dirname(os.path.abspath(__file__))
FT = sys.argv[1]
files = sys.argv[2:] or [os.path.join(HERE, 'results', f'{FT.split("/")[-1]}_scores.json')]
scores = {}
for f in files:
    scores.update(json.load(open(f, encoding='utf-8')))
pairs = json.load(open(os.path.join(HERE, 'fixtures', 'pairs_experts.json'), encoding='utf-8'))
S = defaultdict(dict)
for p, v in zip(pairs, scores[FT]):
    S[(p['set'], p['qi'])][p['item']] = v
DATA = {j: load(j) for j in ('heavy', 'mix4')}
G = {'heavy': json.load(open(os.path.join(HERE, 'results', 'llm_heavy_out.json'), encoding='utf-8')),
     'mix4': json.load(open(os.path.join(HERE, 'results', 'llm_mix4_out.json'), encoding='utf-8'))}
REG = ('gemma4:e4b', 'gemma4:e4b', 'gemma4:12b')
FB = os.environ.get('FALLBACK', 'gemma4:12b')      # 확신도가 애매하거나 앞 대화가 있을 때 부르는 LLM (기본 12B, FALLBACK=gemma4:e4b 로 12B 를 뺀 판)


def top(job, kind, i):
    d = S.get((f'{job}_{kind}', i))
    if not d:
        return None, 0.0
    k = max(d, key=d.get)
    return k, d[k]


def run(job, i, lo, hi, tau_a=None):
    tau_a = tau_a if tau_a is not None else (0.4 if ('emb' in FT or 'Embedding' in FT or 'WeMM' in FT) else 0.5)
    qs, items, out = DATA[job]
    x = qs[i]
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    if rs['day'] is None:
        rs['day'] = rule_slots(x['q'], items)['day']
    anchor = None
    if rs['rel'] is not None:
        kind = 'excl' if a['negation'] else 'tt'
        k, p = top(job, kind, i)
        anchor = k if p >= tau_a else None
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = anchor
    r = resolve(items, slots)
    if r[0] == 'item':
        return r[1], False
    if r[0] == 'none':
        return None, False
    llm = G[job][FB]['picks'][i]
    if x['history']:
        return llm, True                    # 앞 대화는 FT 가 못 읽는다 → LLM
    k, p = top(job, 'tt', i)
    if p >= hi:
        return k, False
    if p < lo:
        return None, False
    return llm, True


def evaluate(job, idx, lo, hi):
    qs = DATA[job][0]
    ok = bad = miss = calls = 0
    bt = defaultdict(int)
    for i in idx:
        p, used = run(job, i, lo, hi)
        g = qs[i]['gold']
        ok += (p == g); bad += (p is not None and p != g); miss += (p is None and g is not None); calls += used
        bt[qs[i]['type']] += (p == g)
    return ok, bad, miss, calls, bt


qh = DATA['heavy'][0]
dev = [i for i, x in enumerate(qh) if x['split'] == 'dev']
held = [i for i, x in enumerate(qh) if x['split'] == 'held']
mix = list(range(len(DATA['mix4'][0])))
if 'emb' in FT or 'Embedding' in FT or 'WeMM' in FT:      # 코사인 유사도 척도
    grid = [(lo, hi) for lo in (0.15, 0.25, 0.3, 0.35, 0.4, 0.45) for hi in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75) if lo < hi]
else:
    grid = [(lo, hi) for lo in (0.02, 0.05, 0.1, 0.2, 0.3, 0.5) for hi in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99) if lo < hi]
best = max(grid, key=lambda g: (evaluate('heavy', dev, *g)[0] - 2 * evaluate('heavy', dev, *g)[1] - 0.05 * evaluate('heavy', dev, *g)[3], -g[0]))
print(f'## {FT} · 넘김 모델 {FB} — 개발용(heavy dev 44)으로 고른 문턱 lo={best[0]} hi={best[1]}')
print(f"{'':<34}{'정답':>10}{'엉뚱':>5}{'못찾음':>6}{'LLM 호출 문제':>14}")
for job, idx, lab in (('heavy', held, 'heavy 판정 88'), ('mix4', mix, 'mix4 88(처음 보는 세트)')):
    r = evaluate(job, idx, *best)
    print(f"{'FT 구조 · ' + lab:<34}{r[0]:>4}/{len(idx)}={r[0] / len(idx):.0%}{r[1]:>5}{r[2]:>6}{r[3]:>8}/{len(idx)}={r[3] / len(idx):.0%}")
    qs, items, out = DATA[job]
    g = G[job]
    for name, get in (('26B 직접', lambda i: g['gemma4:26b']['picks'][i]), ('12B 직접', lambda i: g['gemma4:12b']['picks'][i]),
                      ('기존 구조(E4B/E4B/12B)', lambda i: run_one(i, REG, qs, items, out)[0])):
        ok = sum(get(i) == qs[i]['gold'] for i in idx)
        bad = sum(get(i) is not None and get(i) != qs[i]['gold'] for i in idx)
        miss = sum(get(i) is None and qs[i]['gold'] is not None for i in idx)
        print(f"{'  ' + name:<34}{ok:>4}/{len(idx)}={ok / len(idx):.0%}{bad:>5}{miss:>6}")
r = evaluate('mix4', mix, *best)
print('\nmix4 유형별(FT 구조, 유형당 8):', {t: v for t, v in r[4].items()})
