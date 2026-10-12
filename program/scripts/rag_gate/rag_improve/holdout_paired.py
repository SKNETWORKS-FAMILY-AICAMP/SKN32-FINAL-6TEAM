# 보류 세트(H)에서 사전 등록한 변형들을 같은 질문으로 짝지어 비교한다(McNemar 정확검정 · 짝지은 부트스트랩 · Wilson 구간). 새 모델 호출 없음 — exp5 가 남긴 캐시만 읽는다.
#  보류 세트를 다시 재는 것이 아니다(같은 결과에서 통계만 더 낸다). 변형: V0(운영 색인) · V1(색인 E) · V5d(E + 예상 질문) · V7a(후보 10 재순위) · V7c(후보 20 재순위, 사전 등록 부록).
# 사용: python holdout_paired.py  → ../results/rag_improve/holdout_paired.txt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'eval_kit'))
from rerank_lib import llm_rank, load_cache                      # noqa: E402
from retr_lib import CH, IDS, IDX, OUT, d2q_top2, embed, text_A, text_E, zscore  # noqa: E402
from stats import fmt_ratio, mcnemar_exact, paired_bootstrap_diff  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
rows = json.load(open(os.path.join(HERE, 'holdout', 'holdout_questions.json'), encoding='utf-8'))['questions']
CACHE = load_cache()
DA, DE = embed([text_A(c) for c in CH]), embed([text_E(c) for c in CH])
Q = embed([r['q'] for r in rows])
SA, SE = Q @ DA.T, Q @ DE.T
S5 = zscore(SE) + 1.0 * zscore(d2q_top2(Q))
order5 = np.argsort(-S5, axis=1)


def hit3_rank(S):
    o = np.argsort(-S, axis=1)
    return [bool({IDX[g] for g in r['gold']} & set(o[i][:3].tolist())) for i, r in enumerate(rows) if r['type'] == 'answerable']


def hit3_rerank(model, nc):
    out = []
    for i, r in enumerate(rows):
        if r['type'] != 'answerable':
            continue
        cand = order5[i][:nc].tolist()
        pk = llm_rank(model, r['q'], cand, CACHE)                 # 캐시에 있어야 한다(exp5 가 만들었다)
        full = pk + [c for c in cand if c not in pk]
        out.append(bool({IDX[g] for g in r['gold']} & set(full[:3])))
    return out


V = {'V0 운영 색인': hit3_rank(SA), 'V1 색인 E': hit3_rank(SE), 'V5d E+예상질문': hit3_rank(S5), 'V7a 재순위(후보 10)': hit3_rerank('gemma4:12b', 10), 'V7c 재순위(후보 20)': hit3_rerank('gemma4:12b', 20)}
n = len(V['V0 운영 색인'])
out = [f'# 보류 세트 H — 답 있음 {n}문제, 상위 3 안에 정답(Recall@3) · 같은 질문 짝지은 비교 (2026-10-07, 보류 세트는 1회만 쟀고 이 표는 그 결과에서 통계만 낸 것)\n']
out.append('| 변형 | Recall@3 (Wilson 95%) |')
out.append('|---|---|')
for k, v in V.items():
    out.append(f'| {k} | {fmt_ratio(sum(v), n)} |')
out.append('\n| 비교(이쪽 − 저쪽) | 이쪽만 맞음 : 저쪽만 맞음 | McNemar p | 차이 95% 구간(짝지은 부트스트랩) |')
out.append('|---|---|---:|---|')
for a, b in (('V7c 재순위(후보 20)', 'V0 운영 색인'), ('V7c 재순위(후보 20)', 'V1 색인 E'), ('V7c 재순위(후보 20)', 'V7a 재순위(후보 10)'), ('V5d E+예상질문', 'V0 운영 색인'), ('V1 색인 E', 'V0 운영 색인')):
    m = mcnemar_exact(V[a], V[b])
    d = paired_bootstrap_diff([1.0 if x else 0.0 for x in V[a]], [1.0 if x else 0.0 for x in V[b]])
    out.append(f"| {a} − {b} | {m['a_only']} : {m['b_only']} | {m['p']:.3g} | {d['diff']:+.3f} ({d['lo']:+.3f}~{d['hi']:+.3f}) |")
text = '\n'.join(out)
open(os.path.join(OUT, 'holdout_paired.txt'), 'w', encoding='utf-8').write(text)
print(text)
