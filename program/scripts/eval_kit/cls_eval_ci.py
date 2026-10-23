# 학습한 분류 인코더(multilingual-e5-base, 서버 C 에서 받아 둔 가중치)로 시험 세트 CX 400 · G96 의 네 라벨을 다시 예측해 확률까지 모아 신뢰구간 · MCC · 보정(ECE · Brier)을 낸다.
#  가중치: datasets/_archive/2026-10-06_server_c_models/cls_e5base/model.pt (이 PC CPU 로 추론 — 이 폴더의 모델 설정은 Hugging Face 에서 설정 파일만 받는다, 가중치는 받지 않는다).
#  · 정확도: Wilson 95% · 매크로 F1: 부트스트랩 95%(B=2,000) · MCC · ECE(15칸) · Brier. 값이 없는(마스크) 칸은 제외 — 칸마다 표본 수를 적는다.
# 사용: python cls_eval_ci.py  → results/cls_eval_ci.txt
import json
import os
import sys

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoTokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')
from stats import bootstrap_ci, ece, fmt_ratio, mcc_multiclass, prf_table  # noqa: E402

MD = os.environ.get('CLS_MD', os.path.join(ROOT, 'datasets', '_archive', '2026-10-06_server_c_models', 'cls_e5base'))   # 이 PC 는 가상 메모리가 모자라 서버 B CPU 에서 돌렸다(환경 변수로 경로 지정)
META = json.load(open(os.path.join(MD, 'meta.json'), encoding='utf-8'))
HEADS = META['heads']
FIX = os.environ.get('CLS_FIX', os.path.join(ROOT, 'program', 'scripts', 'plan_qa_bench', 'fixtures', 'cls'))
HEAD_KO = {'intent': '요청 종류(의도)', 'sentiment': '감정', 'severity': '긴급도', 'case_type': '대상 종류'}
LOW = os.environ.get('LOW_MEM', '0') == '1'      # 가상 메모리가 모자라는 PC: 껍데기(meta)만 만들고 불러온 가중치를 그대로 연결(복사 없음)
torch.set_num_threads(8)
tok = AutoTokenizer.from_pretrained(META['name'])


class Cls(nn.Module):
    def __init__(self):
        super().__init__()
        cfg = AutoConfig.from_pretrained(META['name'])
        if LOW:
            with torch.device('meta'):
                self.enc = AutoModel.from_config(cfg)
        else:
            self.enc = AutoModel.from_config(cfg)
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
print('가중치 불러오기', flush=True)
state = torch.load(os.path.join(MD, 'model.pt'), map_location='cpu', weights_only=True)
model.load_state_dict(state, assign=LOW)
if LOW:
    emb = model.enc.embeddings
    n_pos = model.enc.config.max_position_embeddings
    emb.position_ids = torch.arange(n_pos).expand((1, -1))
    emb.token_type_ids = torch.zeros(emb.position_ids.size(), dtype=torch.long)
    assert not any(p.is_meta for p in model.parameters())
model.eval()
lines = []
for tname, tfile in (('CX 400', 'test_cx.jsonl'), ('G96', 'test_g96.jsonl')):
    rows = [json.loads(l) for l in open(os.path.join(FIX, tfile), encoding='utf-8')]
    probs = {h: [] for h in HEADS}
    for i in range(0, len(rows), 32):
        b = rows[i:i + 32]
        x = tok([r['message'] for r in b], padding=True, truncation=True, max_length=META['maxlen'], return_tensors='pt')
        with torch.no_grad():
            lg = model(**x)
        for (h, labs), l in zip(HEADS.items(), lg):
            probs[h] += torch.softmax(l, -1).numpy().tolist()
    lines.append(f'\n## 시험 세트 {tname}')
    lines.append('| 라벨 | 표본 | 정확도 (Wilson 95%) | 매크로 F1 (부트스트랩 95%) | MCC | ECE | Brier |')
    lines.append('|---|---:|---|---|---:|---:|---:|')
    detail = []
    allc = {}
    for h, labs in HEADS.items():
        idx = [k for k, r in enumerate(rows) if r.get(h) in labs and not r.get('mask_' + h)]
        gold = [rows[k][h] for k in idx]
        P = np.array([probs[h][k] for k in idx])
        pred = [labs[int(np.argmax(p))] for p in P]
        conf = P.max(1)
        corr = [g == p for g, p in zip(gold, pred)]
        for k, c in zip(idx, corr):
            allc.setdefault(k, {})[h] = c
        t = prf_table(gold, pred, labs)
        units = list(zip(gold, pred))
        point, lo, hi = bootstrap_ci(units, lambda u: prf_table([a for a, b in u], [b for a, b in u], labs)['macro_f1'], B=2000)
        e = ece(conf, corr)
        lines.append(f"| {HEAD_KO[h]} | {len(idx)} | {fmt_ratio(sum(corr), len(corr))} | {point:.3f} ({lo:.3f}~{hi:.3f}) | {mcc_multiclass(gold, pred, labs):.3f} | {e['ece']:.3f} | {e['brier']:.3f} |")
        detail.append((h, e, np.mean(conf), np.mean(corr)))
    full = [v for v in allc.values() if len(v) == len(HEADS)]
    if full:
        lines.append(f"\n네 축 동시 정답률(네 라벨 모두 값이 있고 모두 맞은 문장): {fmt_ratio(sum(1 for v in full if all(v.values())), len(full))}")
    lines.append('\n보정 요약 — 평균 확신도 대 실제 정확도(차이가 크면 확신이 실제보다 높거나 낮다):')
    for h, e, mc, acc in detail:
        lines.append(f'- {HEAD_KO[h]}: 평균 확신도 {mc:.3f} · 정확도 {acc:.3f} · ECE {e["ece"]:.3f}')
text = '# 학습한 분류 인코더(multilingual-e5-base, 시드 1개) — 신뢰구간 · 보정\n' + '\n'.join(lines) + '\n\n- 한계: 시험 문장은 모델이 쓴 합성(CX: Codex 작성 + Claude 교차 라벨 · G96: Claude 초안 라벨, 사람 검수 전). 가중치는 한 시드의 값이다.\n'
os.makedirs(os.environ.get('CLS_OUT', os.path.join(HERE, 'results')), exist_ok=True)
open(os.path.join(os.environ.get('CLS_OUT', os.path.join(HERE, 'results')), 'cls_eval_ci.txt'), 'w', encoding='utf-8').write(text)
print(text)
