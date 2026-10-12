# 규정 답에 「검증 단계」(모델이 후보 중 직접 답하는 줄만 고름 + 색인 E 점수 문턱 0.45)를 넣었을 때의 오응답 · 재현율 · 정밀도 — 제품 실제 경로(결정 단위 → ask_policy)의 같은 문장으로.
#  입력: results/misanswer/{pool,decisions}.json(misanswer_product_path.py) — 결정 단위가 ask_policy 로 고른 문장만 대상이다(나머지는 규정을 안 붙이므로 그대로).
#  검증 단계 = 1단계(색인 E + 예상 질문) 후보 20 → gemma4:12b 재순위(V7c 와 같은 지시문 · 후보 수) → 고른 줄 중 색인 E 점수 0.45 이상만 보임(없으면 규정을 안 붙임).
# 사용: python verify_stage_eval.py   → ../results/misanswer/verify_stage_report.md
import concurrent.futures as cf
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'eval_kit'))
from rerank_lib import llm_rank, load_cache, save_cache  # noqa: E402
from retr_lib import CH, IDX, d2q_top2, embed, text_E, zscore  # noqa: E402
from stats import fmt_ratio  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
MIS = os.path.abspath(os.path.join(HERE, '..', 'results', 'misanswer'))
P = json.load(open(os.path.join(MIS, 'pool.json'), encoding='utf-8'))['pool']
DEC = json.load(open(os.path.join(MIS, 'decisions.json'), encoding='utf-8'))
REP_E = json.load(open(os.path.join(MIS, 'replies_E.json'), encoding='utf-8'))
CACHE = load_cache()
GATE, NC = 0.45, 20
AP = [x for x in P if DEC.get(x['q'], {}).get('action') == 'ask_policy']
print('ask_policy 로 고른 문장', len(AP), flush=True)
DE = embed([text_E(c) for c in CH])
Q = embed([x['q'] for x in AP])
SE = Q @ DE.T
S1 = zscore(SE) + 1.0 * zscore(d2q_top2(Q))
order = np.argsort(-S1, axis=1)
jobs = [('gemma4:12b', x['q'], order[i][:NC].tolist(), CACHE) for i, x in enumerate(AP)]
with cf.ThreadPoolExecutor(3) as ex:
    picks = list(ex.map(lambda a: llm_rank(*a), jobs))
save_cache(CACHE)


def group(x):
    if x['src'].startswith('합성'):
        return {'answerable': 'REG+', 'uncovered': 'REG-', 'offtopic': 'REG-', 'near_miss': 'NEAR'}[x['label']]
    return 'NON'


def build_ver(gate):
    v = {}      # 검증 단계를 넣은 뒤: 질문 → 보이는 줄
    for i, (x, pk) in enumerate(zip(AP, picks)):
        shown = [c for c in pk[:3] if SE[i, c] >= gate][:2]
        v[x['q']] = [CH[c]['source'] for c in shown]
    return v


ver = build_ver(GATE)
VERS = {0.50: build_ver(0.50), 0.55: build_ver(0.55)}
rows = []
for x in P:
    q = x['q']
    if q not in DEC or DEC[q].get('error'):
        continue
    g = group(x)
    cur = (REP_E.get(q) or {}).get('sources') if DEC[q]['action'] == 'ask_policy' else []
    new = ver.get(q, [])
    gold = set(x['gold'])
    row = {'g': g, 'cur': bool(cur), 'new': bool(new), 'cur_ok': bool(set(cur or []) & gold), 'new_ok': bool(set(new) & gold)}
    for gt in (0.50, 0.55):
        vv = VERS[gt].get(q, [])
        row[f'g{gt}'] = bool(vv)
        row[f'g{gt}_ok'] = bool(set(vv) & gold)
    rows.append(row)


def block(key):
    pos = [r for r in rows if r['g'] == 'REG+']
    neg = [r for r in rows if r['g'] in ('REG-', 'NON')]
    tp = sum(1 for r in pos if r[key + '_ok'])
    fp_wrong = sum(1 for r in pos if r[key] and not r[key + '_ok'])
    fp_neg = sum(1 for r in neg if r[key])
    prec_den = tp + fp_wrong + fp_neg
    return {'tp': tp, 'n_pos': len(pos), 'fp_neg': fp_neg, 'n_neg': len(neg), 'fp_wrong': fp_wrong, 'prec_den': prec_den, 'near_show': sum(1 for r in rows if r['g'] == 'NEAR' and r[key]), 'n_near': sum(1 for r in rows if r['g'] == 'NEAR')}


out = ['# 규정 답에 검증 단계를 넣으면 — 제품 실제 경로(결정 단위 → ask_policy)의 같은 문장 2,340개, 개선 색인 E 기준\n',
       '- 현재 = `question_reply` 그대로(색인 E, 점수 문턱 0.55, 문턱 넘은 상위 조각을 실음). 검증 단계 = 후보 20 → gemma4:12b 가 직접 답하는 줄만 고름 → 색인 E 점수 0.45 이상만 보임(없으면 규정을 안 붙임).',
       '- 결정 단위(1단계)의 선택은 같다 — 달라지는 것은 ask_policy 로 간 문장에서 실제로 규정을 붙이는 단계뿐이다.\n',
       '| 지표 | 현재(E, 문턱 0.55) | 검증 단계 추가 |', '|---|---|---|']
b0, b1 = block('cur'), block('new')
out.append(f"| 재현율(규정 질문 {b0['n_pos']}개 중 정답 규정을 붙임) | {fmt_ratio(b0['tp'], b0['n_pos'])} | {fmt_ratio(b1['tp'], b1['n_pos'])} |")
out.append(f"| 정밀도(규정을 붙인 답 중 정답 규정) | {fmt_ratio(b0['tp'], b0['prec_den'])} | {fmt_ratio(b1['tp'], b1['prec_den'])} |")
out.append(f"| **오응답률**(규정이 아닌 말 · 답 없는 말 {b0['n_neg']}개 중 규정을 붙임) | {fmt_ratio(b0['fp_neg'], b0['n_neg'])} | {fmt_ratio(b1['fp_neg'], b1['n_neg'])} |")
out.append(f"| 규정 질문에 **틀린 규정**을 붙임 | {b0['fp_wrong']}건 | {b1['fp_wrong']}건 |")
out.append(f"| 근접·부분 답 {b0['n_near']}개에 규정을 붙임(참고) | {b0['near_show']}건 | {b1['near_show']}건 |")
out.append('\n검증 단계의 점수 문턱을 올리면(같은 재순위 결과, 문턱만 바꿈):')
out.append('| 점수 문턱 | 재현율 | 정밀도 | 오응답률 |')
out.append('|---|---|---|---|')
out.append(f"| 현재(문턱 0.55, 재순위 없음) | {fmt_ratio(b0['tp'], b0['n_pos'])} | {fmt_ratio(b0['tp'], b0['prec_den'])} | {fmt_ratio(b0['fp_neg'], b0['n_neg'])} |")
for gt in (0.45, 0.50, 0.55):
    key = 'new' if gt == 0.45 else f'g{gt}'
    bb = block(key)
    out.append(f"| 재순위 + {gt} | {fmt_ratio(bb['tp'], bb['n_pos'])} | {fmt_ratio(bb['tp'], bb['prec_den'])} | {fmt_ratio(bb['fp_neg'], bb['n_neg'])} |")
out.append('\n- 한계: 합성 질문 · 1회. 개발 세트 A·B 와 보류 세트 H 의 질문이 섞여 있다(규정 질문 148 = A·B 답 있음). 후보 20 · 문턱 0.45 는 앞선 개발 세트 선택값이다. gemma4:12b 호출이 질문마다 한 번 더 든다.')
text = '\n'.join(out)
open(os.path.join(MIS, 'verify_stage_report.md'), 'w', encoding='utf-8').write(text)
print(text)
