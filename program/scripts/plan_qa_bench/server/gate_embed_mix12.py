# 서버에서: mix12 질문 문장의 e16d 임베딩만 만든다(gate_embed.py 와 같은 질의문 형식·같은 어댑터). 결과 gate_emb_e16d_mix12.npy (float16, 문장 수 × 1024)
# 사용: HF_HOME=/workspace/hf python gate_embed_mix12.py   (gate_sents_mix12.json 이 같은 폴더에 있어야 한다)
import json
import numpy as np
import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModel, AutoTokenizer

texts = json.load(open('gate_sents_mix12.json', encoding='utf-8'))['texts']
name = 'Qwen/Qwen3-Embedding-0.6B'
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
tok = AutoTokenizer.from_pretrained(name, padding_side='left')
base = AutoModel.from_pretrained(name, torch_dtype=torch.float32).cuda().eval()
model = PeftModel.from_pretrained(base, '/workspace/experts/ft_e16d_adapter').eval()
out = []
with torch.no_grad():
    for k in range(0, len(texts), 64):
        b = tok([f'Instruct: {TASK}\nQuery: {t}' for t in texts[k:k + 64]], padding=True, truncation=True, max_length=128, return_tensors='pt').to('cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            h = model(**b).last_hidden_state[:, -1, :]
        out.append(F.normalize(h.float(), dim=-1).cpu().numpy().astype('float16'))
np.save('gate_emb_e16d_mix12.npy', np.concatenate(out))
print('e16d', len(texts), flush=True)
