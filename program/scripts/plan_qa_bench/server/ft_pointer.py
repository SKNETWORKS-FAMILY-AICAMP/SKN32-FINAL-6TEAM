# 서버에서: 소형 언어 모델을 「항목 짚기」 전용으로 LoRA 미세조정하고 사람이 쓴 세트(heavy·mix4·mix5)에서 직접 짚기를 재서 답을 저장한다.
#  학습: pointer_sft.json(gen_pointer_sft.py). 손실은 답 토큰({"item": …}+종료)에만. 학습률·에폭·rank 는 인자. 검증은 학습에서 뺀 장소.
#  평가: 프롬프트는 llm_point_heavy.py 와 같다. 결과 ft_pointer_<이름>_<세트>.json = {'picks': [문제별 항목 번호|null]}
# 사용: python ft_pointer.py <모델> <이름> [에폭=1] [학습률=2e-4] [rank=16]
import json, os, re, sys, time
from datetime import date
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

base, tag = sys.argv[1], sys.argv[2]
epochs = int(sys.argv[3]) if len(sys.argv) > 3 else 1
lr = float(sys.argv[4]) if len(sys.argv) > 4 else 2e-4
rank = int(sys.argv[5]) if len(sys.argv) > 5 else 16
data = json.load(open(os.environ.get('SFT', 'pointer_sft.json'), encoding='utf-8'))      # SFT=pointer_sft_v2.json 로 2판 자료
LIM = int(os.environ.get('LIMIT', '0'))           # 속도 측정용: 학습 문제 수 제한
if LIM:
    data['train'] = data['train'][:LIM]
tok = AutoTokenizer.from_pretrained(base)
tok.padding_side = 'left'
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.bfloat16, device_map='cuda')
model.gradient_checkpointing_enable()
model.enable_input_require_grads()
model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, task_type='CAUSAL_LM', target_modules='all-linear'))
print('학습 가능 파라미터', sum(p.numel() for p in model.parameters() if p.requires_grad), flush=True)


def chat(text):
    msgs = [{'role': 'user', 'content': text}]
    try:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


def encode(ex):
    p = tok(chat(ex['prompt']), add_special_tokens=False)['input_ids']
    a = tok(ex['answer'] + (tok.eos_token or ''), add_special_tokens=False)['input_ids']
    ids = (p + a)[-3400:]
    return torch.tensor([ids], device='cuda'), len(a)


def answer_loss(ids, na):
    # 전체 문장의 어휘 확률표(길이×25만)를 만들면 16GB 를 넘는다 — 답 토큰 위치의 출력만 계산한다
    out = model(input_ids=ids, logits_to_keep=na + 1)
    logits = out.logits[0, :-1].float()
    return torch.nn.functional.cross_entropy(logits, ids[0, -na:])


opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=0.0)
train = data['train']
ACC = 8
steps = epochs * (len(train) // ACC)
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 10) * max(0.05, 1 - s / max(steps, 1)))
model.train()
t0 = time.time()
import random
random.seed(5)
step = 0
for ep in range(epochs):
    random.shuffle(train)
    for k in range(0, len(train) - ACC + 1, ACC):
        tot = 0.0
        for ex in train[k:k + ACC]:
            ids, na = encode(ex)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                loss = answer_loss(ids, na) / ACC
            loss.backward()
            tot += loss.item()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad()
        step += 1
        if step % 10 == 0 or LIM:
            print(f'step {step}/{steps} loss {tot:.4f} {time.time() - t0:.0f}s', flush=True)
if os.environ.get('SKIP_EVAL'):
    print('속도 측정만 하고 종료', f'{time.time() - t0:.0f}s', flush=True)
    sys.exit(0)
model.eval()
model.gradient_checkpointing_disable()
model.config.use_cache = True


@torch.no_grad()
def answer(texts, bs=6):
    outs = []
    for k in range(0, len(texts), bs):
        enc = tok([chat(t) for t in texts[k:k + bs]], return_tensors='pt', padding=True, add_special_tokens=False).to('cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16):
            g = model.generate(**enc, max_new_tokens=14, do_sample=False, pad_token_id=tok.pad_token_id)
        for row in g:
            s = tok.decode(row[enc['input_ids'].shape[1]:], skip_special_tokens=True)
            m = re.search(r'"item"\s*:\s*(null|\d+)', s)
            outs.append(None if (not m or m.group(1) == 'null') else int(m.group(1)))
    return outs


val = data['val']
vp = answer([x['prompt'] for x in val])
vacc = sum(p == x['gold'] for p, x in zip(vp, val)) / len(val)
print(f'검증(처음 보는 장소·합성) 정확도 {vacc:.3f}', flush=True)
W = '월화수목금토일'
res = {'val_acc_synthetic': vacc, 'train_sec': time.time() - t0}
for which in ('heavy', 'mix4', 'mix5'):
    st = json.load(open(f'{which}.json', encoding='utf-8'))['sets'][which]
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    plan = '\n'.join(f"{i['id']}. {days.index(i['date']) + 1}일차 {date.fromisoformat(i['date']).month}/{date.fromisoformat(i['date']).day}({W[date.fromisoformat(i['date']).weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}" for i in items)
    ids = {i['id'] for i in items}
    texts = []
    for x in st['qs']:
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        texts.append("오늘은 {today} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}고객 질문: {q}\n\n"
                     "이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null."
                     .replace('{today}', st['today']).replace('{plan}', plan).replace('{hist}', hist).replace('{q}', x['q']))
    picks = [p if p in ids else None for p in answer(texts)]
    json.dump({'picks': picks}, open(f'ft_pointer_{tag}_{which}.json', 'w'))
    idx = [i for i, x in enumerate(st['qs']) if which != 'heavy' or x.get('split') == 'held']
    ok = sum(picks[i] == st['qs'][i]['gold'] for i in idx)
    res[which] = f"{ok}/{len(idx)}"
    print(which, res[which], flush=True)
json.dump(res, open(f'ft_pointer_{tag}_summary.json', 'w'))
model.save_pretrained(f'ft_pointer_{tag}_adapter')
