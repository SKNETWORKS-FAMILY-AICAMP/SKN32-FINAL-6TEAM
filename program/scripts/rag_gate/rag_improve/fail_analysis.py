# 규정 검색 개선 — 재순위(gemma4:12b, 후보 10)까지 했는데도 정답 줄이 상위 3 안에 못 든 질문을 한 건씩 보여 준다(개발 세트 B). 캐시만 읽으므로 새 모델 호출이 없다.
#  각 실패마다: 질문 · 정답 줄 · 1단계에서 정답의 순위 · 재순위가 고른 줄 · 모델이 고른 것이 정답과 같은 뜻인지(라벨이 모호한지) 눈으로 판단할 재료.
# 사용: python fail_analysis.py [세트 B] [모델 gemma4:12b]
import hashlib
import json
import os
import sys

import numpy as np

from retr_lib import CH, IDS, IDX, OUT, embed, load_sets, text_E, zscore

WHICH = sys.argv[1] if len(sys.argv) > 1 else 'B'
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'gemma4:12b'
NC = 10
sys.stdout.reconfigure(encoding='utf-8')
CACHE = json.load(open(os.path.join(OUT, 'rerank_cache.json'), encoding='utf-8'))
d2q = json.load(open(os.path.join(OUT, 'doc2query.json'), encoding='utf-8'))


def d2q_scores(Q):
    flat, owner = [], []
    for i, s in enumerate(IDS):
        for q in d2q.get(s, []):
            flat.append(q)
            owner.append(i)
    owner = np.array(owner)
    G = embed(flat)
    sim = Q @ G.T
    top2 = np.zeros((Q.shape[0], len(IDS)), dtype=np.float32)
    for i in range(len(IDS)):
        cols = np.where(owner == i)[0]
        top2[:, i] = np.sort(sim[:, cols], axis=1)[:, ::-1][:, :2].mean(axis=1)
    return top2


def line(c):
    return f"[{CH[c]['doc_title']} / {CH[c]['section']}] {CH[c]['line'] or CH[c]['content'][:100]}"


rows = load_sets()[WHICH]
Q = embed([r['q'] for r in rows])
DE = embed([text_E(c) for c in CH])
S1 = zscore(Q @ DE.T) + 1.0 * zscore(d2q_scores(Q))
order = np.argsort(-S1, axis=1)
fails = []
for i, r in enumerate(rows):
    if r['type'] != 'answerable':
        continue
    gold = {IDX[g] for g in r['gold']}
    cand = order[i][:NC].tolist()
    key = hashlib.sha1(('\n'.join([MODEL, r['q'], ','.join(map(str, cand))])).encode('utf-8')).hexdigest()
    pk = CACHE.get(key)
    if pk is None:
        print('캐시 없음(모델 호출이 필요) —', r['q'])
        continue
    full = pk + [c for c in cand if c not in pk]
    top3 = full[:3]
    if not (gold & set(top3)):
        rank1 = next((k + 1 for k, c in enumerate(order[i]) if c in gold), None)
        fails.append((r, gold, rank1, top3, pk))
print(f'세트 {WHICH} · {MODEL} · 재순위 뒤 상위 3 에 정답이 없는 질문 {len(fails)}건')
for n, (r, gold, rank1, top3, pk) in enumerate(fails, 1):
    print(f"\n### 실패 {n}: {r['q']}")
    print('  정답  :', ' | '.join(line(g) for g in gold))
    print('  1단계 정답 순위:', rank1, '· 후보 10 안:', 'O' if rank1 and rank1 <= NC else 'X', '· 모델이 고른 개수:', len(pk))
    for k, c in enumerate(top3, 1):
        print(f'  상위{k}   :', line(c), '(모델 선택)' if c in pk else '(1단계 순서)')
