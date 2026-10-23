# 모델 × 문제 유형별 정답률 — 「요청 둘(compound_intent)」을 따로 떼어, 규칙(먼저 말한 항목이 정답)이 필요 없는 나머지 문제에서 실력을 비교한다.
#  입력: results/export/per_question.csv(로컬·결정 모델·조합) + results/claude_claude_*_mix*.json(Claude 문제별·생각 끔 — 정의 한 줄 없는 판).
#  출력: results/export/summary_by_type.csv(모델×유형) · summary_excl_compound.csv(요청 둘 제외/만) · 터미널에 순위와 짝지은 정확 검정.
import json, math, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
df = pd.read_csv(os.path.join(HERE, 'results', 'export', 'per_question.csv'))
df = df[df['set'].isin(SETS) & df['kind'].isin(['direct', 'direct_reference_unfair', 'combo'])]
rec = []
for (m, k), g in df.groupby(['model', 'kind']):
    if g['set'].nunique() < len(SETS):
        continue
    for _, r in g.iterrows():
        rec.append((m, k, r['set'], int(r['q_index']), r['q_type'], int(r['correct']), r['fair_comparison']))
for nm, tag in (('Claude Opus 5.5 문제별(생각 끔·CLI)', 'claude_opus_5_5'), ('Claude Fable 5.1 문제별(생각 끔·CLI)', 'claude_fable_5_1')):
    for w in SETS:
        qs = json.load(open(fixture(f'{w}.json'), encoding='utf-8'))['sets'][w]['qs']
        rows = json.load(open(os.path.join(HERE, 'results', f'claude_{tag}_{w}.json'), encoding='utf-8'))['rows']
        for i, q in enumerate(qs):
            rec.append((nm, 'direct', w, i, q['type'], int(rows[str(i)]['pick'] == q['gold']), True))
a = pd.DataFrame(rec, columns=['model', 'kind', 'set', 'q_index', 'q_type', 'correct', 'fair_comparison'])
a['compound'] = a['q_type'] == 'compound_intent'
bt = a.pivot_table(index=['model', 'kind', 'fair_comparison'], columns='q_type', values='correct', aggfunc='mean').round(3).reset_index()
out = os.path.join(HERE, 'results', 'export')
bt.to_csv(os.path.join(out, 'summary_by_type.csv'), index=False, encoding='utf-8-sig')
s = a.groupby(['model', 'kind', 'fair_comparison']).apply(lambda g: pd.Series({
    'n_excl': int((~g['compound']).sum()), 'correct_excl': int(g[~g['compound']]['correct'].sum()),
    'n_compound': int(g['compound'].sum()), 'correct_compound': int(g[g['compound']]['correct'].sum())})).reset_index()
s['acc_excl'] = (s['correct_excl'] / s['n_excl']).round(4)
s['acc_compound'] = (s['correct_compound'] / s['n_compound']).round(4)
s = s.sort_values('acc_excl', ascending=False)
s.to_csv(os.path.join(out, 'summary_excl_compound.csv'), index=False, encoding='utf-8-sig')
print(s[s['kind'] != 'combo'].head(16)[['model', 'correct_excl', 'n_excl', 'acc_excl', 'correct_compound', 'n_compound']].to_string(index=False))


def vec(model):
    g = a[(a['model'] == model) & (~a['compound'])].sort_values(['set', 'q_index'])
    return g['correct'].tolist()


def mcn(x, y):
    n10 = sum(1 for p, q in zip(x, y) if p and not q)
    n01 = sum(1 for p, q in zip(x, y) if q and not p)
    n = n10 + n01
    return n10, n01, (1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, j) for j in range(min(n10, n01) + 1)) / 2 ** n))


opus = 'Claude Opus 5.5 문제별(생각 끔·CLI)'
fable = 'Claude Fable 5.1 문제별(생각 끔·CLI)'
for ref in ('Qwen3.8 27B (올라마)', 'decider-chat Gemma4-31B bf16', 'Gemma 4 26B-A4B Q4_K_M (올라마)'):
    for cl in (opus, fable):
        n10, n01, p = mcn(vec(cl), vec(ref))
        print(f'[요청 둘 제외 769] {cl[:22]} 대 {ref[:30]}: Claude만 맞음 {n10} · 상대만 맞음 {n01}, 정확 McNemar p={p:.4f}')
