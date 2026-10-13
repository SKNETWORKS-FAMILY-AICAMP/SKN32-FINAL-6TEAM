# 서버에서: 교차 인코더(기본 BAAI/bge-reranker-v2-m3)로 (질문, 후보 문장) 쌍 점수를 낸다 — 학습 없이 그대로(제로샷). CPU 만 쓴다(GPU 학습 대기열과 겹치지 않게).
#  입력 ce_input.json(ce_build_input.py) → 출력 ce_scores_<이름>.json: {세트: [[후보별 점수 …] …]}. 점수는 모델 로짓(높을수록 관련).
# 사용: python ce_score.py <입력.json> <모델경로 또는 허깅페이스 이름> <출력.json> [스레드]
import json
import sys
import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

src, model_name, dst = sys.argv[1], sys.argv[2], sys.argv[3]
torch.set_num_threads(int(sys.argv[4]) if len(sys.argv) > 4 else 16)
d = json.load(open(src, encoding='utf-8'))
chunk_text = {c['i']: c['text'] for c in d['chunks']}
tok = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name, torch_dtype=torch.float32)
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(DEV)
model.eval()
res = {}
t0 = time.time()
for name, rows in d['sets'].items():
    res[name] = []
    for k, r in enumerate(rows):
        pairs = [[r['q'], chunk_text[c]] for c in r['cand']]
        with torch.no_grad():
            x = tok(pairs, padding=True, truncation=True, max_length=256, return_tensors='pt')
            x = {k: v.to(DEV) for k, v in x.items()}
            sc = model(**x).logits.view(-1).float().cpu().tolist()
        res[name].append([round(s, 4) for s in sc])
        if (k + 1) % 40 == 0:
            print(name, k + 1, '/', len(rows), round(time.time() - t0), '초', flush=True)
json.dump(res, open(dst, 'w'))
print('끝', round(time.time() - t0), '초')
