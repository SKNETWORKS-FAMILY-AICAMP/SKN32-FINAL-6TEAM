# 서버에서: 실제 채팅 잡담(AI Hub 일상 대화 표본)을 질문처럼 앞단(학습 임베딩 ft_e16c)에 넣어 일정 항목과의 코사인 점수를 낸다 — 잡담이 일정 항목으로 잘못 받아들여지는 비율을 재기 위한 것.
#  항목 문서는 pairs_<세트>.json 의 같은 형식(첫 질문의 항목 문서들). 질문 앞 지시문은 학습 때와 같게 붙인다.
# 사용: python chat_fp_score.py <잡담 JSON> <세트 이름>... → chat_front_<세트>.json = {'sims': [[항목별 코사인] × 잡담 수]}
import json, sys
import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModel, AutoTokenizer

chat = json.load(open(sys.argv[1], encoding='utf-8'))
sets = sys.argv[2:]
name = 'Qwen/Qwen3-Embedding-0.6B'
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
tok = AutoTokenizer.from_pretrained(name, padding_side='left')
model = AutoModel.from_pretrained(name, torch_dtype=torch.float32).cuda()
import os
TAG = os.environ.get('TAG', 'e16c')
model = PeftModel.from_pretrained(model, f'/workspace/experts/ft_{TAG}_adapter').eval()


def enc(texts):
    b = tok(texts, padding=True, truncation=True, max_length=128, return_tensors='pt').to('cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        h = model(**b).last_hidden_state[:, -1, :]
    return F.normalize(h.float(), dim=-1)


@torch.no_grad()
def batched(texts):
    return torch.cat([enc(texts[k:k + 64]) for k in range(0, len(texts), 64)])


qv = batched([f'Instruct: {TASK}\nQuery: {t}' for t in chat])
for w in sets:
    pairs = json.load(open(f'pairs_{w}.json', encoding='utf-8'))
    q0 = [p for p in pairs if p['set'] == f'{w}_tt'][0]['qi']
    docs = [p['doc'] for p in pairs if p['set'] == f'{w}_tt' and p['qi'] == q0]
    dv = batched(docs)
    sims = (qv @ dv.T).cpu().tolist()
    json.dump({'docs': docs, 'sims': sims}, open(f'chat_front_{w}' + ('' if TAG == 'e16c' else '_' + TAG) + '.json', 'w'))
    print(w, '항목', len(docs), '잡담', len(chat), flush=True)
