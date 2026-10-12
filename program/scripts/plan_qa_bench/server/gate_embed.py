# 서버에서: 게이트용 문장 임베딩 — Qwen3-Embedding-0.6B(고정)와 e16d LoRA 를 얹은 판 두 가지를 .npy 로 저장한다. 질의문 형식은 앞단과 같다.
# 사용: HF_HOME=/workspace/hf python gate_embed.py → gate_emb_base.npy · gate_emb_e16d.npy (float16, 문장 수 × 1024)
import json, sys
import numpy as np
import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModel, AutoTokenizer

texts = json.load(open('gate_sents.json', encoding='utf-8'))['texts']
name = 'Qwen/Qwen3-Embedding-0.6B'
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
tok = AutoTokenizer.from_pretrained(name, padding_side='left')
base = AutoModel.from_pretrained(name, torch_dtype=torch.float32).cuda().eval()


def run(model, tag):
    out = []
    with torch.no_grad():
        for k in range(0, len(texts), 64):
            b = tok([f'Instruct: {TASK}\nQuery: {t}' for t in texts[k:k + 64]], padding=True, truncation=True, max_length=128, return_tensors='pt').to('cuda')
            with torch.autocast('cuda', dtype=torch.bfloat16):
                h = model(**b).last_hidden_state[:, -1, :]
            out.append(F.normalize(h.float(), dim=-1).cpu().numpy().astype('float16'))
    np.save(f'gate_emb_{tag}.npy', np.concatenate(out))
    print(tag, len(texts), flush=True)


run(base, 'base')
m2 = PeftModel.from_pretrained(base, '/workspace/experts/ft_e16d_adapter').eval()
run(m2, 'e16d')
