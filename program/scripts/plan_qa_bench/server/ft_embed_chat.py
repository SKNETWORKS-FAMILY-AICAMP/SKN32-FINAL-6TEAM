# [v3 — AI Hub 일상 대화 잡담 정답 없음 + 점수 상하한] 서버에서: Qwen3-Embedding-0.6B 를 우리 과제 전용으로 LoRA 미세조정(양방향 인코더 판 — 항목 벡터는 일정마다 한 번만, 질문마다 질문 벡터만 계산).
#  손실 = 문제 하나의 항목들(정답 + 어려운 오답 + 무작위 오답) 중 정답의 유사도 소프트맥스 교차 엔트로피(정답 여럿이면 합).
#  정답 없는 문제(일정 밖·무관 문장)는 최대 유사도가 0.30 을 넘으면 벌점(가벼운 가중치) — 「없음」 판정 문턱을 벌려 놓는다.
# 사용: python ft_embed.py <이름> [에폭=2] [학습률=1e-4] [rank=16] → ft_<이름>_scores.json (키 ft/emb_<이름>: heavy·mix4 쌍 코사인), ft_<이름>_val.json
import json, os, random, sys, time
import torch
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import AutoModel, AutoTokenizer

tag = sys.argv[1]
epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 2
lr = float(sys.argv[3]) if len(sys.argv) > 3 else 1e-4
rank = int(sys.argv[4]) if len(sys.argv) > 4 else 16
name = os.environ.get('BASE', 'Qwen/Qwen3-Embedding-0.6B')
TASK = '고객이 여행 일정에 대해 묻는 질문이 주어지면, 그 질문이 가리키는 일정 항목을 찾는다'
data = json.load(open(os.environ.get('TRAIN', 'train_pairs.json'), encoding='utf-8'))      # TRAIN=train_pairs_v2.json 로 2판 자료
pairs = json.load(open('pairs.json', encoding='utf-8'))
tok = AutoTokenizer.from_pretrained(name, padding_side='left')
model = AutoModel.from_pretrained(name, torch_dtype=torch.float32).cuda()
model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05,
                                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']))


def enc(texts):
    b = tok(texts, padding=True, truncation=True, max_length=int(os.environ.get('MAXLEN', '128')), return_tensors='pt').to('cuda')
    with torch.autocast('cuda', dtype=torch.bfloat16):
        h = model(**b).last_hidden_state[:, -1, :]
    return F.normalize(h.float(), dim=-1)


def qtext(q):
    return f'Instruct: {TASK}\nQuery: {q}'


def groups(rows):
    g = {}
    for x in rows:
        g.setdefault(x['g'], {'q': x['q'], 'docs': [], 'lab': [], 'chat': bool(x.get('chat'))})
        g[x['g']]['docs'].append(x['doc'])
        g[x['g']]['lab'].append(x['label'])
    return list(g.values())


train, val = groups(data['train']), groups(data['val'])
opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
BS = int(os.environ.get('BS', '2'))      # 문제(그룹) 수 — 처음 8 은 16GB GPU 에서 메모리 부족(2026-09-30)
steps = epochs * (len(train) // BS)
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 20) * max(0.05, 1 - s / max(steps, 1)))
random.seed(2)
model.train()
t0 = time.time()
step = 0
TAU = 0.05
HW = float(os.environ.get('HW', '5'))               # 점수 하한·상한 벌점 가중(0.1 어긋나면 손실 0.5)
POS_FLOOR = float(os.environ.get('POS_FLOOR', '0.40'))
CHAT_CEIL = float(os.environ.get('CHAT_CEIL', '0.10'))
for ep in range(epochs):
    random.shuffle(train)
    for k in range(0, len(train) - BS + 1, BS):
        batch = train[k:k + BS]
        qv = enc([qtext(g['q']) for g in batch])
        alld = [d for g in batch for d in g['docs']]
        dv = enc(alld)
        loss = 0.0
        off = 0
        for gi, g in enumerate(batch):
            n = len(g['docs'])
            s = dv[off:off + n] @ qv[gi]
            off += n
            lab = torch.tensor(g['lab'], device='cuda', dtype=torch.bool)
            if lab.any():
                lp = torch.log_softmax(s / TAU, 0)
                loss = loss - torch.logsumexp(lp[lab], 0)
                loss = loss + HW * F.relu(POS_FLOOR - s[lab].max())          # 정답 점수 하한(0.40 미만이면 벌점)
            elif g.get('chat'):
                loss = loss + HW * F.relu(s.max() - CHAT_CEIL)               # 실제 잡담 점수 상한(0.10 초과면 벌점)
            else:
                loss = loss + 0.5 * F.relu(s.max() - 0.30) / TAU * 0.1
        loss = loss / BS
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad()
        step += 1
        if step % 100 == 0:
            print(f'step {step}/{steps} loss {loss.item():.4f} {time.time() - t0:.0f}s', flush=True)
model.eval()


@torch.no_grad()
def batched(texts):
    out = []
    for k in range(0, len(texts), 64):
        out.append(enc(texts[k:k + 64]))
    return torch.cat(out)


hit = n = 0
none_max, pos_top = [], []
for g in val:
    qv = batched([qtext(g['q'])])[0]
    dv = batched(g['docs'])
    s = (dv @ qv).tolist()
    if any(g['lab']):
        n += 1
        hit += g['lab'][max(range(len(s)), key=s.__getitem__)]
        pos_top.append(max(s))
    else:
        none_max.append(max(s))
json.dump({'top1_acc_on_unseen_places': hit / n, 'n_pos_questions': n, 'none_max_sim_mean': sum(none_max) / max(1, len(none_max)),
           'pos_top_sim_mean': sum(pos_top) / len(pos_top)}, open(f'ft_{tag}_val.json', 'w'))
print('검증(처음 보는 장소) 1위 정확도', f'{hit / n:.3f}', flush=True)
qs = sorted({p['q'] for p in pairs})
ds = sorted({p['doc'] for p in pairs})
qv, dv = batched([qtext(q) for q in qs]), batched(ds)
qi, di = {q: i for i, q in enumerate(qs)}, {d: i for i, d in enumerate(ds)}
sc = [float((qv[qi[p['q']]] * dv[di[p['doc']]]).sum()) for p in pairs]
json.dump({f'ft/emb_{tag}': sc}, open(f'ft_{tag}_scores.json', 'w'))
model.save_pretrained(f'ft_{tag}_adapter')          # 새 세트(mix5)를 같은 모델로 잴 수 있게 가중치 저장
if os.path.exists('pairs_mix5.json'):
    p5 = json.load(open('pairs_mix5.json', encoding='utf-8'))
    q5, d5 = sorted({p['q'] for p in p5}), sorted({p['doc'] for p in p5})
    qv5, dv5 = batched([qtext(q) for q in q5]), batched(d5)
    i5, j5 = {q: i for i, q in enumerate(q5)}, {d: i for i, d in enumerate(d5)}
    json.dump({f'ft/emb_{tag}': [float((qv5[i5[p['q']]] * dv5[j5[p['doc']]]).sum()) for p in p5]}, open(f'ft_{tag}_mix5_scores.json', 'w'))
    print('mix5 쌍 점수 저장', len(p5))
print('heavy·mix4 쌍 점수 저장', len(sc), f'{time.time() - t0:.0f}s')
