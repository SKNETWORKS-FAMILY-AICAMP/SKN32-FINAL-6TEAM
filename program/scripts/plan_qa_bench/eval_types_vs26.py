# 유형별로 각 방식이 Gemma 26B 보다 실제로 점수가 높았는지 — heavy 판정 88(유형당 8) + mix4 88(유형당 8) = 유형당 16문제.
#  방식: Gemma E4B · 12B 직접, 전문가 구조(E4B/E4B/12B, 코드 분기 + 작은 모델), heavy 만 Jev·Codex 솔(정의 명시).
#  ▲ 이김 · ▼ 짐 · = 비김(26B 대비 맞은 수 차이). 재평가·WeMM·OpenDecider 는 eval_trio_types.py(기존 판정 90).
# 사용: python eval_types_vs26.py
import json
from collections import Counter
from eval_pipeline import load, run_one

H = json.load(open('fixtures/heavy.json', encoding='utf-8'))['sets']['heavy']['qs']
M = json.load(open('fixtures/mix4.json', encoding='utf-8'))['sets']['mix4']['qs']
gh = json.load(open('results/llm_heavy_out.json', encoding='utf-8'))
gm = json.load(open('results/llm_mix4_out.json', encoding='utf-8'))
qh, ih, oh = load('heavy')
qm, im, om = load('mix4')
REG = ('gemma4:e4b', 'gemma4:e4b', 'gemma4:12b')
jrows = json.load(open('results/jev_out_heavy_rules.json', encoding='utf-8'))['heavy']['rows']


def jev(i):
    r = jrows[i]['probs']
    k = max(r, key=r.get)
    return None if k == 'none' else int(k.split('_')[1])


sol = json.load(open('results/codex_gpt-6-sol_heavy_proto.json', encoding='utf-8'))['heavy']
held = [i for i, x in enumerate(H) if x['split'] == 'held']
methods = {
    'E4B': (lambda i: gh['gemma4:e4b']['picks'][i], lambda i: gm['gemma4:e4b']['picks'][i]),
    '12B': (lambda i: gh['gemma4:12b']['picks'][i], lambda i: gm['gemma4:12b']['picks'][i]),
    '26B': (lambda i: gh['gemma4:26b']['picks'][i], lambda i: gm['gemma4:26b']['picks'][i]),
    '구조': (lambda i: run_one(i, REG, qh, ih, oh)[0], lambda i: run_one(i, REG, qm, im, om)[0]),
}
types = list(dict.fromkeys(x['type'] for x in H))


def score(t, name):
    f, g = methods[name]
    a = sum(f(i) == H[i]['gold'] for i in held if H[i]['type'] == t)
    b = sum(g(i) == M[i]['gold'] for i in range(len(M)) if M[i]['type'] == t)
    return a + b


def mark(d):
    return f"{'▲' if d > 0 else ('▼' if d < 0 else '=')}{abs(d) if d else ''}"


print('## A. 유형별 맞은 수 — heavy(8) + mix4(8) = 유형당 16문제 (26B 와 비교)')
print(f"{'유형':<22}{'26B':>6}{'12B':>6}{'E4B':>6}{'구조':>6}   26B 대비: 12B / E4B / 구조")
wins = Counter()
tot = Counter()
for t in types:
    r = {n: score(t, n) for n in methods}
    print(f"{t:<22}{r['26B']:>6}{r['12B']:>6}{r['E4B']:>6}{r['구조']:>6}   {mark(r['12B'] - r['26B'])} / {mark(r['E4B'] - r['26B'])} / {mark(r['구조'] - r['26B'])}")
    for n in ('12B', 'E4B', '구조'):
        d = r[n] - r['26B']
        wins[(n, '이김' if d > 0 else ('짐' if d < 0 else '비김'))] += 1
    for n in methods:
        tot[n] += r[n]
    tot['소형 유형별 최선(사후 선택)'] += max(r['12B'], r['E4B'], r['구조'])
print('\n합계(176문제):', ' · '.join(f'{n} {v}' for n, v in tot.items()))
print('유형 11개 중 26B 대비 (이김/비김/짐):')
for n in ('12B', 'E4B', '구조'):
    print(f"  {n}: {wins[(n, '이김')]}/{wins[(n, '비김')]}/{wins[(n, '짐')]}")
print('\n## B. heavy 판정 88 유형당 8 — Jev·Codex 솔(정의 명시, 천장) vs 26B')
for t in types:
    ii = [i for i in held if H[i]['type'] == t]
    s26 = sum(methods['26B'][0](i) == H[i]['gold'] for i in ii)
    sj = sum(jev(i) == H[i]['gold'] for i in ii)
    ss = sum(sol.get(str(i)) == H[i]['gold'] for i in ii)
    print(f"  {t:<22} 26B {s26} · Jev {sj}{mark(sj - s26)} · 솔 {ss}{mark(ss - s26)}")
