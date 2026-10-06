# 서버에서: 작은 한국어(다국어) 인코더를 여행 고객 메시지 네 가지 라벨(의도 · 감정 · 긴급도 · 대상 종류)로 한 번에 학습·평가한다 — 공유 인코더 + 머리 4개.
#  자료: train.jsonl(Claude 작성·Codex 교차 확인), test_cx.jsonl(Codex 작성·Claude 교차 확인 — 출제자가 학습 자료와 다름), test_g96.jsonl(서비스 평가 자료 golden 72+holdout 24, Claude 초안 라벨).
#  라벨 −1 = 교차 라벨러와 어긋나 쓰지 않는 칸(학습 손실·평가 모두 제외). 시드 3개 평균. CPU(스레드 4) 한 건 지연도 잰다.
# 사용: python train_cls.py <모델이름> [--epochs 8] [--lr 3e-5] [--seeds 3] [--maxlen 96] [--bs 32]   → cls_result_<모델>.json
import json, os, random, sys, time
import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

NAME = sys.argv[1]
a = sys.argv[2:]
opt = lambda k, d, c=float: c(a[a.index(k) + 1]) if k in a else d
EPOCHS, LR, SEEDS, MAXLEN, BS = opt('--epochs', 8, int), opt('--lr', 3e-5), opt('--seeds', 3, int), opt('--maxlen', 96, int), opt('--bs', 32, int)
TAG = opt('--tag', '', str)
SAVE = opt('--save', '', str)   # 첫 시드의 최고 개발 점수 가중치를 이 폴더에 저장한다(model.pt · meta.json) — 모델 조합 시험(chain_e2e.py)이 불러 쓴다   # 같은 모델을 다른 설정(에폭·학습률)으로 다시 돌릴 때 결과 파일 이름 뒤에 붙인다
HEADS = {'intent': ['itinerary_submit', 'incident_report', 'confirm_request', 'adjust_reject', 'other'],
         'sentiment': ['positive', 'neutral', 'negative'], 'severity': ['low', 'medium', 'high', 'critical'],
         'case_type': ['activity', 'dining', 'mobility', 'booking', 'lodging', 'flight', 'other']}
W = '/root/work/cls'


def load(f):
    rows = [json.loads(l) for l in open(os.path.join(W, f), encoding='utf-8')]
    return rows


def enc_labels(r):
    return [HEADS[h].index(r[h]) if r.get(h) in HEADS[h] and not r.get('mask_' + h) else -1 for h in HEADS]


train_all, test_cx, test_g = load('train.jsonl'), load('test_cx.jsonl'), load('test_g96.jsonl')
dev_ids = set(random.Random(7).sample(range(len(train_all)), int(len(train_all) * 0.15)))
tr = [r for i, r in enumerate(train_all) if i not in dev_ids]
dev = [r for i, r in enumerate(train_all) if i in dev_ids]
tok = AutoTokenizer.from_pretrained(NAME)


class Model(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = AutoModel.from_pretrained(NAME, dtype=torch.float32)
        h = self.enc.config.hidden_size
        self.drop = nn.Dropout(0.1)
        self.heads = nn.ModuleList([nn.Linear(h, len(v)) for v in HEADS.values()])

    def forward(self, **kw):
        kw.pop('token_type_ids', None) if 'roberta' in NAME.lower() or 'e5' in NAME.lower() or 'bge' in NAME.lower() or 'mmbert' in NAME.lower() or 'A.X' in NAME else None
        out = self.enc(**kw).last_hidden_state
        m = kw['attention_mask'].unsqueeze(-1).to(out.dtype)
        pooled = (out * m).sum(1) / m.sum(1).clamp(min=1)
        return [h(self.drop(pooled)) for h in self.heads]


def batches(rows, shuffle, rng=None):
    idx = list(range(len(rows)))
    if shuffle:
        rng.shuffle(idx)
    for i in range(0, len(idx), BS):
        b = [rows[j] for j in idx[i:i + BS]]
        x = tok([r['message'] for r in b], padding=True, truncation=True, max_length=MAXLEN, return_tensors='pt')
        y = torch.tensor([enc_labels(r) for r in b])
        yield x, y


def evaluate(model, rows):
    model.eval()
    preds = [[] for _ in HEADS]
    gold = [[] for _ in HEADS]
    with torch.no_grad():
        for x, y in batches(rows, False):
            logits = model(**{k: v.cuda() for k, v in x.items()})
            for k, lg in enumerate(logits):
                preds[k] += lg.argmax(-1).cpu().tolist()
                gold[k] += y[:, k].tolist()
    res = {}
    for k, h in enumerate(HEADS):
        p, g = np.array(preds[k]), np.array(gold[k])
        ok = g >= 0
        acc = float((p[ok] == g[ok]).mean()) if ok.any() else None
        f1s = []
        for c in range(len(HEADS[h])):
            tp = ((p == c) & (g == c) & ok).sum(); fp = ((p == c) & (g != c) & ok).sum(); fn = ((p != c) & (g == c) & ok).sum()
            if (g[ok] == c).any():
                f1s.append(2 * tp / max(1, 2 * tp + fp + fn))
        res[h] = {'acc': acc, 'macro_f1': float(np.mean(f1s)) if f1s else None, 'n': int(ok.sum())}
    return res


results = {'model': NAME + TAG, 'epochs': EPOCHS, 'lr': LR, 'runs': []}
for seed in range(SEEDS):
    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    rng = random.Random(seed)
    model = Model().cuda()
    steps = EPOCHS * ((len(tr) + BS - 1) // BS)
    optim = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(optim, int(0.1 * steps), steps)
    ce = nn.CrossEntropyLoss(ignore_index=-1)
    best, best_state = -1, None
    t0 = time.time()
    for ep in range(EPOCHS):
        model.train()
        for x, y in batches(tr, True, rng):
            with torch.autocast('cuda', dtype=torch.bfloat16):
                logits = model(**{k: v.cuda() for k, v in x.items()})
            loss = sum(ce(lg.float(), y[:, k].cuda()) for k, lg in enumerate(logits))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step(); sched.step(); optim.zero_grad(set_to_none=True)
        d = evaluate(model, dev)
        score = float(np.mean([v['macro_f1'] or 0 for v in d.values()]))
        if score > best:
            best, best_state = score, {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    if SAVE and seed == 0:
        os.makedirs(SAVE, exist_ok=True)
        torch.save({k: v.cpu() for k, v in best_state.items()}, os.path.join(SAVE, 'model.pt'))
        json.dump({'name': NAME, 'heads': HEADS, 'epochs': EPOCHS, 'lr': LR, 'maxlen': MAXLEN, 'dev_macro_f1': round(best, 4)}, open(os.path.join(SAVE, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    run = {'seed': seed, 'train_s': round(time.time() - t0), 'dev_macro_f1': round(best, 4), 'cx': evaluate(model, test_cx), 'g96': evaluate(model, test_g)}
    results['runs'].append(run)
    if seed == 0:   # CPU(스레드 4) 한 건 지연 — 첫 시드 모델로
        model_cpu = Model(); model_cpu.load_state_dict({k: v.cpu() for k, v in best_state.items()}); model_cpu.eval()
        torch.set_num_threads(4)
        msgs = [r['message'] for r in test_cx[:60]]
        lat = []
        with torch.no_grad():
            for m in msgs:
                x = tok([m], return_tensors='pt', truncation=True, max_length=MAXLEN)
                t1 = time.perf_counter(); model_cpu(**x); lat.append((time.perf_counter() - t1) * 1000)
        results['params_M'] = round(sum(p.numel() for p in model_cpu.parameters()) / 1e6, 1)
        results['cpu_ms_median'] = round(float(np.median(lat[5:])), 1)
        results['cpu_ms_p95'] = round(float(np.percentile(lat[5:], 95)), 1)
        del model_cpu
    del model, optim
    torch.cuda.empty_cache()


def mean(k, h, m):
    v = [r[k][h][m] for r in results['runs'] if r[k][h][m] is not None]
    return round(float(np.mean(v)), 4), round(float(np.std(v)), 4)


results['summary'] = {k: {h: {'acc': mean(k, h, 'acc'), 'macro_f1': mean(k, h, 'macro_f1')} for h in HEADS} for k in ('cx', 'g96')}
json.dump(results, open(f"/root/work/cls_result_{NAME.replace('/', '_')}{TAG}.json", 'w', encoding='utf-8'), ensure_ascii=False)
print(NAME, 'params', results.get('params_M'), 'cpu_ms', results.get('cpu_ms_median'))
for k in ('cx', 'g96'):
    print('  ', k, ' '.join(f"{h}={results['summary'][k][h]['acc'][0]:.3f}/{results['summary'][k][h]['macro_f1'][0]:.3f}" for h in HEADS), flush=True)
