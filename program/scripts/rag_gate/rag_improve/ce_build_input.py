# 전용 재순위 모델(교차 인코더)을 시험하기 위한 입력을 만든다 — 1단계(색인 E + 예상 질문, V5d)로 뽑은 후보 20개와 질문을 파일로 저장한다(모델 호출 없음, 임베딩 캐시만 읽는다).
#  세트: A(180) · B(160) · H(보류 140). 출력: results/rag_improve/ce_input.json  → 서버에서 ce_score.py 로 (질문, 후보) 쌍 점수를 낸다 → ce_eval.py 가 Recall@3 · 새어 나감을 센다.
# 사용: python ce_build_input.py
import json
import os
import sys

import numpy as np

from retr_lib import CH, HERE, IDS, IDX, OUT, d2q_top2, embed, load_sets, text_E, zscore

sys.stdout.reconfigure(encoding='utf-8')
NC = 20
SETS = load_sets()
SETS['H'] = json.load(open(os.path.join(HERE, 'holdout', 'holdout_questions.json'), encoding='utf-8'))['questions']
DE = embed([text_E(c) for c in CH])
out = {'chunks': [{'i': i, 'source': c['source'], 'text': f"{c['section']}: {c['line'] or c['content'][:160]}"} for i, c in enumerate(CH)], 'sets': {}}
for name, rows in SETS.items():
    Q = embed([r['q'] for r in rows])
    S1 = zscore(Q @ DE.T) + 1.0 * zscore(d2q_top2(Q))
    SE = Q @ DE.T
    order = np.argsort(-S1, axis=1)
    out['sets'][name] = [{'q': r['q'], 'type': r['type'], 'gold': [IDX[g] for g in (r.get('gold') or [])], 'cand': order[i][:NC].tolist(), 'se': [round(float(SE[i, c]), 4) for c in order[i][:NC]]} for i, r in enumerate(rows)]
    print(name, len(rows))
json.dump(out, open(os.path.join(OUT, 'ce_input.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('저장', os.path.join(OUT, 'ce_input.json'))
