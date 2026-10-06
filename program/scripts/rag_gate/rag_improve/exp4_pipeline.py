# 실험 4 — 재순위(모델이 후보 10개에서 「직접 답하는 줄」을 고름)를 운영 규칙처럼 끝까지 돌려 본다: 답 있음 질문의 Recall@3 · 정답을 보인 비율 · 틀린 줄만 보인 비율, 답 없는 질문(uncovered · offtopic · near_miss)에 규정을 보이는 비율.
#  모델이 고른 줄이 없으면 규정을 보이지 않는다(거절). 선택 규칙: ① 재순위만 ② 재순위 + 색인 E 점수 문턱(τ) 둘 다 통과한 줄만.
#  재순위 결과는 exp3_rerank.py 의 캐시(rerank_cache.json)를 읽는다 — 같은 모델 · 같은 후보 · 같은 질문이어야 키가 맞는다.
# 사용: python exp4_pipeline.py [모델] [후보수] [세트: A,B,H]   (H = 보류 세트 — 마지막에 한 번만 쓴다)
import hashlib
import json
import os
import sys

import numpy as np

from retr_lib import CH, IDS, IDX, OUT, d2q_top2, embed, leak_at, load_sets, text_E, zscore


MODEL = sys.argv[1] if len(sys.argv) > 1 else 'gemma4:12b'
NC = int(sys.argv[2]) if len(sys.argv) > 2 else 10
WHICH = sys.argv[3].split(',') if len(sys.argv) > 3 else ['A', 'B']
sys.stdout.reconfigure(encoding='utf-8')
CACHE = json.load(open(os.path.join(OUT, 'rerank_cache.json'), encoding='utf-8'))
DE = embed([text_E(c) for c in CH])
SETS = load_sets()
for name in WHICH:
    rows = SETS[name]
    Q = embed([r['q'] for r in rows])
    SE = Q @ DE.T
    S1 = zscore(SE) + 1.0 * zscore(d2q_top2(Q))
    order = np.argsort(-S1, axis=1)
    for tau in (None, 0.40, 0.45, 0.50, 0.55):
        ans = ok = wrong = 0
        n_ans = 0
        leak = n_neg = 0
        nm_show = n_nm = 0
        r3 = 0
        for i, r in enumerate(rows):
            cand = order[i][:NC].tolist()
            key = hashlib.sha1(('\n'.join([MODEL, r['q'], ','.join(map(str, cand))])).encode('utf-8')).hexdigest()
            if key not in CACHE:
                print('캐시에 없는 질문 — 중단', name, i)
                sys.exit(1)
            picks = [c for c in CACHE[key] if tau is None or SE[i, c] >= tau][:3]
            if r['type'] == 'answerable':
                n_ans += 1
                gold = {IDX[g] for g in r['gold']}
                ans += bool(picks)
                hit = bool(set(picks) & gold)
                ok += hit
                wrong += (bool(picks) and not hit)
            elif r['type'] in ('uncovered', 'offtopic'):
                n_neg += 1
                leak += bool(picks)
            elif r['type'] == 'near_miss':
                n_nm += 1
                nm_show += bool(picks)
        print(f'{name} · 재순위({MODEL}) + 문턱 {tau}: 답 있음 {n_ans}: 답함 {ans} · 정답을 보임 {ok} = {ok / n_ans:.3f} · 틀린 줄만 {wrong} | 답 없는 질문 {n_neg}: 규정을 보임 {leak} = {leak / n_neg:.3f} | 근접·부분 답 {n_nm}: 보임 {nm_show}')
