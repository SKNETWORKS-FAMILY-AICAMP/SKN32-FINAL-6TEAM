# 실험 1 — 이미 있는 재료로 만들 수 있는 검색 변형을 개발 세트 A(180) · B(160)에서 잰다. 임베딩은 같은 bge-m3(x600 서버 Ollama).
#  V0 운영 색인(직원용 본문) · V1 색인 E · V2 A+E 점수 합 · V3 E + BM25(글자 2-gram) 융합 · V4 A+E+BM25 융합.
#  지표: 답 있음 질문에서 정답 줄이 상위 3개 안인 비율(Recall@3) · MRR · 문턱 판정 대신 「답 없는 질문 새어 나감」은 E 임베딩 점수 문턱(0.55)으로 보인 조각이 있는 비율.
import sys

import numpy as np

from retr_lib import CH, bm25_ngram, embed, leak_at, load_sets, recall_at, text_A, text_E, zscore

sys.stdout.reconfigure(encoding='utf-8')
SETS = load_sets()
DA = embed([text_A(c) for c in CH])
DE = embed([text_E(c) for c in CH])
docsE = [text_E(c) for c in CH]
res = {}
print('| 변형 | A Recall@3 | A MRR | B Recall@3 | B MRR | 답 없는 질문 새어 나감(A · B, 문턱 0.55) |')
print('|---|---:|---:|---:|---:|---|')
variants = {}
for name, rows in SETS.items():
    Q = embed([r['q'] for r in rows])
    SA, SE = Q @ DA.T, Q @ DE.T
    BM = bm25_ngram(docsE, [r['q'] for r in rows])
    z = zscore
    variants[name] = {
        'V0 운영 색인(직원용 본문)': (SA, SA),
        'V1 색인 E': (SE, SE),
        'V2 A+E 점수 합': ((SA + SE) / 2, (SA + SE) / 2),
        'V3 E + BM25 융합(z 합)': (z(SE) + 0.5 * z(BM), SE),
        'V4 A+E + BM25 융합': (z(SA) + z(SE) + 0.7 * z(BM), SE),
        'V3b E + BM25 융합(가중 1.0)': (z(SE) + 1.0 * z(BM), SE),
    }
for vn in variants['A']:
    cells = []
    for name, rows in SETS.items():
        S, gate = variants[name][vn]
        h, n, mrr = recall_at(rows, S)
        cells.append((h, n, mrr))
    la = leak_at(SETS['A'], *variants['A'][vn], tau=0.55)
    lb = leak_at(SETS['B'], *variants['B'][vn], tau=0.55)
    print(f'| {vn} | {cells[0][0]}/{cells[0][1]} = {cells[0][0] / cells[0][1]:.3f} | {cells[0][2]:.3f} | {cells[1][0]}/{cells[1][1]} = {cells[1][0] / cells[1][1]:.3f} | {cells[1][2]:.3f} | {la[0]}/{la[1]} · {lb[0]}/{lb[1]} |')
