# 교차 인코더 점수(ce_score.py 결과)로 후보를 다시 줄 세우고 지표를 센다 — 새 모델 호출 없음.
#  · Recall@3: 후보 20개를 점수 순으로 놓고 상위 3 안에 정답이 있는 비율(모델 재순위 V7c 와 같은 지표) · Hit@2(고객에게 보이는 줄 수)
#  · 보임 규칙: 점수가 θ 이상인 줄만(상위 3 중 앞 2개) 고객에게 보인다 → 정답을 보임 · 답 없는 질문에 보임(새어 나감) · 근접·부분 답에 보임.
#    θ 는 개발 세트(A+B)에서 「새어 나감 ≤ 2% 중 정답을 가장 많이 보이는 값」으로 고른다. 보류 세트(H)는 그 θ 를 한 번 적용한다.
# 사용: python ce_eval.py <ce_scores.json> [이름]
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'eval_kit'))
from stats import fmt_ratio, mcnemar_exact  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.path.abspath(os.path.join(HERE, '..', 'results', 'rag_improve'))
scores = json.load(open(sys.argv[1], encoding='utf-8'))
name = sys.argv[2] if len(sys.argv) > 2 else 'CE'
D = json.load(open(os.path.join(OUT, 'ce_input.json'), encoding='utf-8'))


def per_set(sname, theta=None):
    rows, sc = D['sets'][sname], scores[sname]
    r3 = h2 = n_ans = shown_ok = 0
    neg = leak = nm = nm_show = 0
    base3 = 0
    flags = []
    for r, s in zip(rows, sc):
        order = np.argsort(-np.array(s))
        top = [r['cand'][i] for i in order[:3]]
        top_s = [s[i] for i in order[:3]]
        if r['type'] == 'answerable':
            n_ans += 1
            g = set(r['gold'])
            ok3 = bool(g & set(top))
            r3 += ok3
            h2 += bool(g & set(top[:2]))
            base3 += bool(g & set(r['cand'][:3]))
            if theta is not None:
                shown = [c for c, v in zip(top, top_s) if v >= theta][:2]
                shown_ok += bool(g & set(shown))
            flags.append(ok3)
        elif r['type'] in ('uncovered', 'offtopic'):
            neg += 1
            if theta is not None:
                leak += bool([c for c, v in zip(top, top_s) if v >= theta][:2])
        elif r['type'] == 'near_miss':
            nm += 1
            if theta is not None:
                nm_show += bool([c for c, v in zip(top, top_s) if v >= theta][:2])
    return {'n': n_ans, 'r3': r3, 'base3': base3, 'h2': h2, 'shown_ok': shown_ok, 'neg': neg, 'leak': leak, 'nm': nm, 'nm_show': nm_show, 'flags': flags}


out = [f'# {name} — 교차 인코더 재순위(제로샷, 후보 20개 점수순) 지표\n']
# θ 고르기(개발 세트 A+B)
grid = [round(x, 1) for x in np.arange(-6, 6.01, 0.5)]
best = None
rows_t = []
for th in grid:
    a, b = per_set('A', th), per_set('B', th)
    n_neg, leak = a['neg'] + b['neg'], a['leak'] + b['leak']
    ok, n = a['shown_ok'] + b['shown_ok'], a['n'] + b['n']
    rows_t.append((th, ok, n, leak, n_neg))
    if leak / n_neg <= 0.02 and (best is None or ok > best[1]):
        best = (th, ok, n, leak, n_neg)
out.append('개발 세트(A+B) 점수 문턱 θ 별 — 정답을 보임 / 답 없는 질문에 보임')
out.append('| θ | 정답을 보임 | 답 없는 질문에 보임 |')
out.append('|---:|---|---|')
for th, ok, n, leak, n_neg in rows_t[::2]:
    out.append(f'| {th:g} | {fmt_ratio(ok, n)} | {fmt_ratio(leak, n_neg)} |')
theta = best[0] if best else 0.0
out.append(f'\n선택한 θ = {theta:g} (개발 세트에서 새어 나감 ≤ 2% 중 정답을 보인 비율이 가장 큰 값)\n')
out.append('| 세트 | Recall@3 (1단계 V5d → 교차 인코더) | Hit@2 | θ 적용: 정답을 보임 | 답 없는 질문에 보임 | 근접·부분 답에 보임 |')
out.append('|---|---|---|---|---|---|')
for s in ('A', 'B', 'H'):
    m = per_set(s, theta)
    out.append(f"| {s} | {fmt_ratio(m['base3'], m['n'])} → **{fmt_ratio(m['r3'], m['n'])}** | {fmt_ratio(m['h2'], m['n'])} | {fmt_ratio(m['shown_ok'], m['n'])} | {fmt_ratio(m['leak'], m['neg'])} | {m['nm_show']}/{m['nm']} |")
text = '\n'.join(out)
open(os.path.join(OUT, f'ce_eval_{name}.txt'), 'w', encoding='utf-8').write(text)
print(text)
