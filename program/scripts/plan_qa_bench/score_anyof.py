# 채점 방식 B — 요청 둘 문제는 「말한 항목이면 모두 정답」(pick ∈ gold_set). 나머지 문제는 기존 채점 그대로. 이미 나온 모델 출력(per_question.csv · Claude 문제별 결과)을 다시 채점한다(새 추론 없음).
#  입력: results/export/per_question.csv · results/claude_claude_*_mix*.json(정의 한 줄 없는 판) · fixtures/gold_sets.json
#  출력: results/export/summary_anyof.csv · results/anyof_table_mix8to12.md · 터미널에 순위 + 짝지은 정확 검정
import json, math, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
GS = json.load(open(os.path.join(HERE, 'fixtures', 'gold_sets.json'), encoding='utf-8'))
Q = {w: json.load(open(os.path.join(HERE, 'fixtures', f'{w}.json'), encoding='utf-8'))['sets'][w]['qs'] for w in SETS}


def okB(w, i, pick):
    g = GS[w][str(i)]
    return int((pick is None and not g) or (pick is not None and pick in g))


df = pd.read_csv(os.path.join(HERE, 'results', 'export', 'per_question.csv'))
df = df[df['set'].isin(SETS) & df['kind'].isin(['direct', 'direct_reference_unfair', 'combo'])]
rec = []
for (m, k), g in df.groupby(['model', 'kind']):
    if g['set'].nunique() < len(SETS):
        continue
    fair = bool(g['fair_comparison'].iloc[0])
    for _, r in g.iterrows():
        w, i = r['set'], int(r['q_index'])
        pick = None if pd.isna(r['pick']) else int(r['pick'])
        rec.append((m, k, fair, w, i, Q[w][i]['type'], int(r['correct']), okB(w, i, pick)))
for nm, tag in (('Claude Opus 5.5 문제별(생각 끔·CLI)', 'claude_opus_5_5'), ('Claude Fable 5.1 문제별(생각 끔·CLI)', 'claude_fable_5_1')):
    for w in SETS:
        rows = json.load(open(os.path.join(HERE, 'results', f'claude_{tag}_{w}.json'), encoding='utf-8'))['rows']
        for i, q in enumerate(Q[w]):
            p = rows[str(i)]['pick']
            rec.append((nm, 'direct', True, w, i, q['type'], int(p == q['gold']), okB(w, i, p)))
a = pd.DataFrame(rec, columns=['model', 'kind', 'fair', 'set', 'q_index', 'q_type', 'A', 'B'])
a['compound'] = a['q_type'] == 'compound_intent'
s = a.groupby(['model', 'kind', 'fair']).apply(lambda g: pd.Series({
    'n': len(g), 'A_correct': int(g['A'].sum()), 'B_correct': int(g['B'].sum()),
    'compound_A': int(g[g['compound']]['A'].sum()), 'compound_B': int(g[g['compound']]['B'].sum()), 'n_compound': int(g['compound'].sum()),
    'noncompound_correct': int(g[~g['compound']]['A'].sum()), 'n_noncompound': int((~g['compound']).sum())}), include_groups=False).reset_index()
s['A_acc'] = (s['A_correct'] / s['n']).round(4)
s['B_acc'] = (s['B_correct'] / s['n']).round(4)
s = s.sort_values('B_acc', ascending=False)
s.to_csv(os.path.join(HERE, 'results', 'export', 'summary_anyof.csv'), index=False, encoding='utf-8-sig')
a.to_csv(os.path.join(HERE, 'results', 'export', 'per_question_anyof.csv'), index=False, encoding='utf-8-sig')

L = ['# 채점 방식 B(요청 둘은 말한 항목이면 모두 정답) — mix8~12, 835문제', '',
     '생성: score_anyof.py. 「A」 = 지금 방식(먼저 말한 항목만 정답), 「B」 = 요청 둘 66문제만 말한 항목이면 정답, 나머지 769문제는 A 와 같다. ⚠ 표시 행은 묶음 풀이(공정 비교 아님).', '',
     '| 모델·구성 | 종류 | A 합 | B 합 | 요청 둘만 A → B (66) | 요청 둘 제외 (769) |', '|---|---|---:|---:|---|---:|']
for _, r in s.iterrows():
    mark = '' if r['fair'] else '⚠ '
    L.append(f"| {mark}{r['model'][:70]} | {r['kind']} | {r['A_correct']} ({100 * r['A_acc']:.1f}%) | **{r['B_correct']} ({100 * r['B_acc']:.1f}%)** | {r['compound_A']} → {r['compound_B']} | {r['noncompound_correct']} ({100 * r['noncompound_correct'] / r['n_noncompound']:.1f}%) |")
open(os.path.join(HERE, 'results', 'anyof_table_mix8to12.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print(s[s['kind'] != 'combo'].head(14)[['model', 'A_correct', 'B_correct', 'compound_A', 'compound_B', 'n']].to_string(index=False))


def vec(m, col):
    g = a[a['model'] == m].sort_values(['set', 'q_index'])
    return g[col].tolist()


def mcn(x, y):
    n10 = sum(1 for p, q in zip(x, y) if p and not q)
    n01 = sum(1 for p, q in zip(x, y) if q and not p)
    n = n10 + n01
    return n10, n01, (1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, j) for j in range(min(n10, n01) + 1)) / 2 ** n))


opus = 'Claude Opus 5.5 문제별(생각 끔·CLI)'
fable = 'Claude Fable 5.1 문제별(생각 끔·CLI)'
for ref in ('Qwen3.8 27B (올라마)', 'decider-chat Gemma4-31B bf16', 'Gemma 4 26B-A4B Q4_K_M (올라마)'):
    for cl in (opus, fable):
        n10, n01, p = mcn(vec(cl, 'B'), vec(ref, 'B'))
        print(f'[B 835] {cl[:22]} 대 {ref[:26]}: Claude만 맞음 {n10} · 상대만 맞음 {n01}, 정확 McNemar p={p:.4f}')
