# 서버에서: 저장해 둔 분류 인코더(/root/chain/cls_e5base — multilingual-e5-base, train_cls.py --save 의 첫 시드 최고 개발 점수 가중치)로
#  시험 세트 CX 400 · G96 를 예측해, Jev 계열 분류 시험(jev_cls_run.py)과 같은 모양의 파일로 저장한다 → 이 PC 의 cls_prf.py 가 클래스별 정밀도·재현율·F1 을 센다.
# 사용: python cls_predict_saved.py  → /root/chain/out/cls_pred_e5base.json
import json
import os
import sys

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

ROOT = '/root/chain'
META = json.load(open(f'{ROOT}/cls_e5base/meta.json', encoding='utf-8'))
HEADS = META['heads']
tok = AutoTokenizer.from_pretrained(META['name'])
torch.set_num_threads(int(os.environ.get('CLS_THREADS', '8')))


class Cls(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = AutoModel.from_pretrained(META['name'], dtype=torch.float32)
        h = self.enc.config.hidden_size
        self.drop = nn.Dropout(0.1)
        self.heads = nn.ModuleList([nn.Linear(h, len(v)) for v in HEADS.values()])

    def forward(self, **kw):
        kw.pop('token_type_ids', None)
        out = self.enc(**kw).last_hidden_state
        m = kw['attention_mask'].unsqueeze(-1).to(out.dtype)
        pooled = (out * m).sum(1) / m.sum(1).clamp(min=1)
        return [h(self.drop(pooled)) for h in self.heads]


model = Cls()
model.load_state_dict(torch.load(f'{ROOT}/cls_e5base/model.pt'))
model.eval()
out = {}
for f in ('test_cx.jsonl', 'test_g96.jsonl'):
    rows = [json.loads(l) for l in open(f'{ROOT}/fixtures/cls/{f}', encoding='utf-8')]
    preds = []
    for i in range(0, len(rows), 32):
        b = rows[i:i + 32]
        x = tok([r['message'] for r in b], padding=True, truncation=True, max_length=META['maxlen'], return_tensors='pt')
        with torch.no_grad():
            lg = model(**x)
        for j, r in enumerate(b):
            p = {'id': r['id']}
            for (h, labs), l in zip(HEADS.items(), lg):
                p[h] = labs[int(l[j].argmax())]
            preds.append(p)
    out[f] = {'preds': preds}
    print(f, len(preds), flush=True)
json.dump(out, open(f'{ROOT}/out/cls_pred_e5base.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('끝')
