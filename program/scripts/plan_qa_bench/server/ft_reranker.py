# 서버에서: Qwen3-Reranker-0.6B 를 우리 과제 전용으로 LoRA 미세조정(가중치 변경을 작게 유지 — 9월 논문의 「합성 자료 학습은 실제 분포에서 성능 하락」 경고를 반영).
#  손실 = 「yes/no」 두 토큰 확률에 대한 교차 엔트로피(원래 재평가 방식 그대로). 학습 자료는 gen_train.py 의 train_pairs.json.
#  끝나면 (1) 검증 쌍(처음 보는 장소)의 문제별 1위 정확도, (2) heavy·mix4 쌍(pairs.json)의 점수를 저장한다.
# 사용: python ft_reranker.py <출력 이름> [에폭=1] [학습률=1e-4] [rank=16]  → ft_<이름>_scores.json, ft_<이름>_val.json
import json, os, random, sys, time
import torch
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

tag = sys.argv[1]
epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
lr = float(sys.argv[3]) if len(sys.argv) > 3 else 1e-4
rank = int(sys.argv[4]) if len(sys.argv) > 4 else 16
name = os.environ.get('BASE', 'Qwen/Qwen3-Reranker-0.6B')
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
data = json.load(open('train_pairs.json', encoding='utf-8'))
pairs = json.load(open('pairs.json', encoding='utf-8'))
tok = AutoTokenizer.from_pretrained(name, padding_side='left')
model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float32, device_map='cuda')
model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, task_type='CAUSAL_LM',
                                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']))
yes, no = tok.convert_tokens_to_ids('yes'), tok.convert_tokens_to_ids('no')
pre = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct '
       'provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
suf = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def text(q, d):
    return f"{pre}<Instruct>: {TASK}\n<Query>: {q}\n<Document>: {d}{suf}"


def logits2(batch):
    enc = tok([text(x['q'], x['doc']) for x in batch], padding=True, truncation=True, max_length=384, return_tensors='pt').to('cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        lg = model(**enc).logits[:, -1, :]
    return torch.stack([lg[:, no], lg[:, yes]], 1).float()


opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)
train = data['train']
random.seed(1)
BS = 16
steps = epochs * (len(train) // BS)
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 30) * max(0.05, 1 - s / max(steps, 1)))
model.train()
t0 = time.time()
step = 0
for ep in range(epochs):
    random.shuffle(train)
    for k in range(0, len(train) - BS + 1, BS):
        b = train[k:k + BS]
        loss = F.cross_entropy(logits2(b), torch.tensor([x['label'] for x in b], device='cuda'))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad()
        step += 1
        if step % 200 == 0:
            print(f'step {step}/{steps} loss {loss.item():.4f} {time.time() - t0:.0f}s', flush=True)
model.eval()


@torch.no_grad()
def score(rows):
    out = []
    for k in range(0, len(rows), 32):
        out += torch.softmax(logits2(rows[k:k + 32]), 1)[:, 1].tolist()
    return out


val = data['val']
vs = score(val)
byg = {}
for x, s in zip(val, vs):
    byg.setdefault(x['g'], []).append((s, x['label']))
pos_q = [v for v in byg.values() if any(l for _, l in v)]
acc = sum(max(v)[1] for v in pos_q) / len(pos_q)
none_q = [v for v in byg.values() if not any(l for _, l in v)]
json.dump({'top1_acc_on_unseen_places': acc, 'n_pos_questions': len(pos_q), 'n_none_questions': len(none_q),
           'none_max_score_mean': sum(max(s for s, _ in v) for v in none_q) / max(1, len(none_q)),
           'pos_top_score_mean': sum(max(s for s, _ in v) for v in pos_q) / len(pos_q)}, open(f'ft_{tag}_val.json', 'w'))
print('검증(처음 보는 장소) 1위 정확도', f'{acc:.3f}', flush=True)
sc = score([{'q': p['q'], 'doc': p['doc']} for p in pairs])
json.dump({f'ft/{tag}': sc}, open(f'ft_{tag}_scores.json', 'w'))
print('heavy·mix4 쌍 점수 저장', len(sc), f'{time.time() - t0:.0f}s')
