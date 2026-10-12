# 실험 2 — 조각마다 미리 만든 예상 질문(doc2query, gen_doc2query.py)을 색인에 더한다. 질문 ↔ 예상 질문 유사도의 조각별 최댓값(SQ)을 색인 E 점수(SE)와 합친다.
#  평가 질문은 예상 질문을 만들 때 쓰이지 않았다(조각 글만 보고 생성). 가중치는 개발 세트 A·B 평균으로 고르되 표에 전부 보인다.
import json
import os
import sys

import numpy as np

from retr_lib import CH, IDS, OUT, embed, leak_at, load_sets, recall_at, text_E, zscore

sys.stdout.reconfigure(encoding='utf-8')
SRC = sys.argv[1] if len(sys.argv) > 1 else 'doc2query.json'
d2q = json.load(open(os.path.join(OUT, SRC), encoding='utf-8'))
SETS = load_sets()
DE = embed([text_E(c) for c in CH])
flat, owner = [], []
for i, s in enumerate(IDS):
    for q in d2q.get(s, []):
        flat.append(q)
        owner.append(i)
owner = np.array(owner)
G = embed(flat)
print(f'예상 질문 {len(flat)}개 · 질문 없는 조각 {sum(1 for s in IDS if not d2q.get(s))}개')


def chunk_max(Q):
    sim = Q @ G.T
    out = np.full((Q.shape[0], len(IDS)), -1.0, dtype=np.float32)
    for j, o in enumerate(owner):
        out[:, o] = np.maximum(out[:, o], sim[:, j])
    return out


def chunk_top2(Q):
    sim = Q @ G.T
    out = np.zeros((Q.shape[0], len(IDS)), dtype=np.float32)
    for i in range(len(IDS)):
        cols = np.where(owner == i)[0]
        if len(cols):
            top = np.sort(sim[:, cols], axis=1)[:, ::-1][:, :2]
            out[:, i] = top.mean(axis=1)
    return out


rows_out = []
store = {}
for name, rows in SETS.items():
    Q = embed([r['q'] for r in rows])
    SE = Q @ DE.T
    SQ = chunk_max(Q)
    store[name] = (SE, SQ, chunk_top2(Q))
print('| 변형 | A Recall@3 | A MRR | B Recall@3 | B MRR | 평균 Recall@3 | 새어 나감 A · B (E 점수 문턱 0.55) |')
print('|---|---:|---:|---:|---:|---:|---|')


def show(label, f):
    cells = []
    for name, rows in SETS.items():
        SE, SQ, SQ2 = store[name]
        S = f(SE, SQ, SQ2)
        cells.append(recall_at(rows, S) + (S,))
    la = leak_at(SETS['A'], cells[0][3], store['A'][0], 0.55)
    lb = leak_at(SETS['B'], cells[1][3], store['B'][0], 0.55)
    avg = (cells[0][0] / cells[0][1] + cells[1][0] / cells[1][1]) / 2
    print(f'| {label} | {cells[0][0]}/{cells[0][1]} = {cells[0][0] / cells[0][1]:.3f} | {cells[0][2]:.3f} | {cells[1][0]}/{cells[1][1]} = {cells[1][0] / cells[1][1]:.3f} | {cells[1][2]:.3f} | {avg:.3f} | {la[0]}/{la[1]} · {lb[0]}/{lb[1]} |')
    return avg


show('V1 색인 E (기준)', lambda SE, SQ, SQ2: SE)
show('V5a 예상 질문만(최댓값)', lambda SE, SQ, SQ2: SQ)
show('V5b 예상 질문만(상위 2 평균)', lambda SE, SQ, SQ2: SQ2)
for w in (0.5, 1.0, 2.0):
    show(f'V5c E + {w}×예상 질문 최댓값 (z 합)', lambda SE, SQ, SQ2, w=w: zscore(SE) + w * zscore(SQ))
for w in (0.5, 1.0):
    show(f'V5d E + {w}×예상 질문 상위 2 평균 (z 합)', lambda SE, SQ, SQ2, w=w: zscore(SE) + w * zscore(SQ2))
show('V5e max(E, 예상 질문)', lambda SE, SQ, SQ2: np.maximum(SE, SQ))
show('V5f (E + 예상 질문 최댓값)/2', lambda SE, SQ, SQ2: (SE + SQ) / 2)
