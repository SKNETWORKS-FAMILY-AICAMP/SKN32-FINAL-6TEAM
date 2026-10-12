# 서버에서: 「한 줄로 이은 시험」 2단계 준비 — 학습 임베딩(Qwen3-Embedding-0.6B + LoRA e16d)으로 질문 ↔ 일정 항목 코사인을 질문마다 실제로 계산한다.
#  규칙 단계가 「앞뒤」 표현에서 기준 항목을 찾을 때 쓰는 점수(eval_night.top 과 같은 값: 질문 절 ↔ 항목 설명 코사인, 기준 문턱 0.4)다.
#  방법은 ft_embed.py 와 같다(질문 앞에 Instruct 줄, 마지막 토큰 벡터, 정규화, bf16 autocast, 최대 128토큰). 질문마다 따로(배치 1) 계산해 지연도 잰다.
#  GPU 를 2.4GB 쓰므로 두 llama 서버를 띄우기 전에 돌리고 끝나면 비운다.
# 사용: python chain_emb.py [검증용 저장 점수 파일(ft_e16d_mix8_scores.json)]  → /root/chain/out/emb_scores.json
import json
import os
import sys
import time

import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModel, AutoTokenizer

ROOT = '/root/chain'
sys.path.insert(0, ROOT)
from clauses import analyze  # noqa: E402

W = os.environ.get('SETS', 'mix8,mix9,mix10,mix11,mix12').split(',')     # 섞은 시험 세트(mixed8~12)는 SETS 와 EMB_FILE 로 지정한다
NAME = 'Qwen/Qwen3-Embedding-0.6B'
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
os.makedirs(f'{ROOT}/out', exist_ok=True)
tok = AutoTokenizer.from_pretrained(NAME, padding_side='left')
base = AutoModel.from_pretrained(NAME, torch_dtype=torch.float32).cuda()
model = PeftModel.from_pretrained(base, f'{ROOT}/ft_e16d_adapter').eval()


def enc(texts):
    b = tok(texts, padding=True, truncation=True, max_length=128, return_tensors='pt').to('cuda')
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        h = model(**b).last_hidden_state[:, -1, :]
    return F.normalize(h.float(), dim=-1)


qtext = lambda q: f'Instruct: {TASK}\nQuery: {q}'
J = lambda f: json.load(open(f, encoding='utf-8'))
out = {}
check = []
stored = J(sys.argv[1])['ft/emb_e16d'] if len(sys.argv) > 1 else None
for w in W:
    job = J(f'{ROOT}/fixtures/{w}.json')['sets'][w]
    pairs = J(f'{ROOT}/fixtures/pairs_{w}.json')
    doc_of = {}
    for p in pairs:
        doc_of[p['item']] = p['doc']            # 항목 설명 문장은 짝 자료에 들어 있는 것을 그대로 쓴다(같은 항목은 같은 문장)
    ids = sorted(doc_of)
    dv = enc([doc_of[k] for k in ids])
    w_out = {}
    for i, x in enumerate(job['qs']):
        a = analyze(x['q'])
        row = {}
        for kind, txt in (('tt', a['tt']), ('excl', a['excl'])):
            if not txt:
                continue
            torch.cuda.synchronize()
            t0 = time.perf_counter()
            qv = enc([qtext(txt)])[0]
            sc = (dv @ qv).tolist()
            torch.cuda.synchronize()
            row[kind] = {'scores': {str(k): s for k, s in zip(ids, sc)}, 'ms': (time.perf_counter() - t0) * 1000, 'q': txt}
        w_out[str(i)] = row
    out[w] = w_out
    print(w, len(w_out), flush=True)
    if stored is not None and w == 'mix8':       # 저장된 점수(mix8 쌍 7,770개)와 견준다
        n = d = 0
        mx = 0.0
        for p, v in zip(pairs, stored):
            row = w_out[str(p['qi'])].get(p['set'].split('_')[1])
            if row is None or p['q'] != row['q']:
                continue
            s = row['scores'].get(str(p['item']))
            if s is not None:
                n += 1
                mx = max(mx, abs(s - v))
        check = {'compared_pairs': n, 'total_pairs': len(pairs), 'max_abs_diff': mx}
        print('저장 점수와 비교', check, flush=True)
json.dump({'scores': out, 'check_mix8': check}, open(f"{ROOT}/out/{os.environ.get('EMB_FILE', 'emb_scores.json')}", 'w'), ensure_ascii=False)
print('끝')
