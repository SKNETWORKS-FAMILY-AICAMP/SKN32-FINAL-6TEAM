# 서버 B 의 CPU 로 교차 인코더(기본 BAAI/bge-reranker-v2-m3, 568M)를 우리 규정 관련성 자료로 이어 가르친다 — GPU 학습 대기열과 겹치지 않게 CPU 만 쓴다.
#  손실: 이진 교차 엔트로피(양성에 가중 pos_weight) · AdamW lr 2e-5 · 워밍업 6% 뒤 선형 감소 · 배치 16 · 기본 2에폭 · 최대 160토큰. 끝나면 bf16 으로 줄여 저장(디스크 절약).
# 사용: python ce_train.py <모델폴더> <ce_train.jsonl> <저장폴더> [에폭=2] [스레드=96]
import json
import math
import random
import sys
import time

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

mdir, data, out = sys.argv[1], sys.argv[2], sys.argv[3]
epochs = int(sys.argv[4]) if len(sys.argv) > 4 else 2
torch.set_num_threads(int(sys.argv[5]) if len(sys.argv) > 5 else 96)
random.seed(20261007)
torch.manual_seed(20261007)
rows = [json.loads(l) for l in open(data, encoding='utf-8')]
tok = AutoTokenizer.from_pretrained(mdir)
model = AutoModelForSequenceClassification.from_pretrained(mdir, dtype=torch.float32, num_labels=1)
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
model.to(DEV)
model.train()
BS, LR, POSW = 16, 2e-5, 3.0
steps_total = epochs * math.ceil(len(rows) / BS)
opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
warm = max(1, int(0.06 * steps_total))
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: (s + 1) / warm if s < warm else max(0.0, (steps_total - s) / max(1, steps_total - warm)))
loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(POSW, device=DEV))
t0 = time.time()
step = 0
for ep in range(epochs):
    random.shuffle(rows)
    for k in range(0, len(rows), BS):
        b = rows[k:k + BS]
        x = tok([r['q'] for r in b], [r['p'] for r in b], padding=True, truncation=True, max_length=160, return_tensors='pt')
        x = {k: v.to(DEV) for k, v in x.items()}
        y = torch.tensor([float(r['y']) for r in b], device=DEV)
        with torch.autocast(device_type=DEV, dtype=torch.bfloat16, enabled=(DEV == 'cuda')):
            logits = model(**x).logits.view(-1).float()
        loss = loss_fn(logits, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        sched.step()
        opt.zero_grad()
        step += 1
        if step % 20 == 0:
            el = time.time() - t0
            print(f'ep {ep + 1} step {step}/{steps_total} loss {loss.item():.4f} {el / 60:.1f}분 · 남은 약 {el / step * (steps_total - step) / 60:.0f}분', flush=True)
model.eval()
model.to(torch.bfloat16).save_pretrained(out, safe_serialization=True)
tok.save_pretrained(out)
print('저장', out, f'총 {(time.time() - t0) / 60:.1f}분', flush=True)
