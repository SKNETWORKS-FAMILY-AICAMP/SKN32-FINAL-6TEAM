# 서버에서: 저장해 둔 앞단(Qwen3-Embedding-0.6B + ft_e16c LoRA 어댑터)으로 새 세트 쌍(pairs_<세트>.json)의 코사인 점수를 낸다(재학습 없음).
# 사용: python score_mix6.py <세트이름 예 mix6> [어댑터 폴더=/workspace/experts/ft_e16c_adapter] → ft_e16c_<세트>_scores.json
import json, sys
import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModel, AutoTokenizer

which = sys.argv[1]
adapter = sys.argv[2] if len(sys.argv) > 2 else '/workspace/experts/ft_e16c_adapter'
name = 'Qwen/Qwen3-Embedding-0.6B'
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
tok = AutoTokenizer.from_pretrained(name, padding_side='left')
model = AutoModel.from_pretrained(name, torch_dtype=torch.float32).cuda()
model = PeftModel.from_pretrained(model, adapter).eval()


def enc(texts):
    b = tok(texts, padding=True, truncation=True, max_length=128, return_tensors='pt').to('cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        h = model(**b).last_hidden_state[:, -1, :]
    return F.normalize(h.float(), dim=-1)


@torch.no_grad()
def batched(texts):
    return torch.cat([enc(texts[k:k + 64]) for k in range(0, len(texts), 64)])


pairs = json.load(open(f'pairs_{which}.json', encoding='utf-8'))
qs, ds = sorted({p['q'] for p in pairs}), sorted({p['doc'] for p in pairs})
qv, dv = batched([f'Instruct: {TASK}\nQuery: {q}' for q in qs]), batched(ds)
qi, di = {q: i for i, q in enumerate(qs)}, {d: i for i, d in enumerate(ds)}
json.dump({'ft/emb_e16c': [float((qv[qi[p['q']]] * dv[di[p['doc']]]).sum()) for p in pairs]}, open(f'ft_e16c_{which}_scores.json', 'w'))
print('쌍 점수 저장', len(pairs))
