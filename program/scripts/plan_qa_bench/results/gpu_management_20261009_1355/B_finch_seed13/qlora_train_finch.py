# 별도 연구 실험판: FINCH식 손실 적응 학습률 / 동일 최대 학습률 코사인 대조군. 기존 대기열 학습 코드는 수정하지 않는다.
# 서버에서: 증류 파일럿 — 학생 모델(Gemma 4 E4B)을 4비트(NF4)로 올리고 LoRA 만 학습한다(QLoRA). 정답 토큰에만 손실을 준다.
#  입력: train.jsonl(prompt · completion) — 로컬 distill_assemble.py 가 만든 것. 모델은 HF 형식 폴더.
#  메모리: 어휘가 26만이라 전 위치에 로짓을 만들면 2GB 가 넘는다 → 정답이 끝에 있으므로 logits_to_keep 으로 끝 몇 토큰만 만든다.
# 사용: python3 qlora_train2.py <모델폴더> <train.jsonl> <어댑터 출력 폴더> [--epochs 2] [--lr 2e-4] [--rank 16] [--accum 8] [--limit N] [--maxlen 3072] [--seed 20261005]
#       [--family gemma|qwen]  — qlora_train.py 의 일반화 판(2026-10-06). 기본(gemma)은 원본과 똑같이 동작한다. qwen: 끝 표지 <|im_end|> · 생각 끄기(enable_thinking=False) · 선형 주의 층 포함 LoRA 대상.
import json, math, os, random, sys, time, hashlib
from finch_schedule import LossAdaptiveRate
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL, TRAIN, OUT = sys.argv[1:4]
a = sys.argv[4:]


def opt(name, default, cast=float):
    return cast(a[a.index(name) + 1]) if name in a else default


FAMILY = opt('--family', 'gemma', str)
EPOCHS, LR, RANK, ACCUM, LIMIT, MAXLEN, SEED = opt('--epochs', 2, int), opt('--lr', 2e-4), opt('--rank', 16, int), opt('--accum', 8, int), opt('--limit', 0, int), opt('--maxlen', 3072, int), opt('--seed', 20261005, int)
SCHEDULE = opt('--schedule', 'finch', str)
BASE_RATE = opt('--finch-base-rate', 2e-5)
CAP = opt('--finch-cap', 5e-5)
ALPHA = opt('--finch-alpha', 0.9)
if SCHEDULE not in ('finch', 'cosine'):
    raise ValueError('schedule는 finch 또는 cosine')
if EPOCHS < 1 or ACCUM < 1:
    raise ValueError('epochs와 accum은 1 이상')
if os.path.exists(OUT):
    raise FileExistsError('기존 출력 폴더 보존: 새 이름을 사용하세요')
# 잘못된 FINCH 설정은 모델을 올리기 전에 거른다.
LossAdaptiveRate(1.0, BASE_RATE, CAP, ALPHA)
os.makedirs(OUT, exist_ok=False)
recipe = dict(schedule=SCHEDULE, seed=SEED, epochs=EPOCHS, rank=RANK,
              accum=ACCUM, maxlen=MAXLEN, limit=LIMIT, family=FAMILY,
              cosine_peak_lr=LR, finch_base_rate=BASE_RATE, finch_cap=CAP,
              finch_alpha=ALPHA, status='started',
              train_sha256=hashlib.sha256(open(TRAIN, 'rb').read()).hexdigest(),
              script_sha256=hashlib.sha256(open(__file__, 'rb').read()).hexdigest(),
              source='https://arxiv.org/html/2605.20005v1',
              adaptation='EMA batch is one optimizer accumulation window; initial loss is sequence mean')
with open(os.path.join(OUT, 'recipe.json'), 'x', encoding='utf-8') as f:
    json.dump(recipe, f, ensure_ascii=False, indent=2)
random.seed(SEED)
torch.manual_seed(SEED)
tok = AutoTokenizer.from_pretrained(MODEL)
rows = [json.loads(l) for l in open(TRAIN, encoding='utf-8')]
if LIMIT:
    rows = rows[:LIMIT]


EOS = {'gemma': '<turn|>', 'qwen': '<|im_end|>'}[FAMILY]
CHAT_KW = {'enable_thinking': False} if FAMILY == 'qwen' else {}
TARGETS = (r'.*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)' if FAMILY == 'gemma'
           else r'^(?!.*(visual|vision|audio)).*layers\.\d+\..*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj|in_proj_qkv|in_proj_z|out_proj)$')


def encode(r):
    p = tok.apply_chat_template([{'role': 'user', 'content': r['prompt']}], add_generation_prompt=True, tokenize=False, **CHAT_KW)
    pi = tok(p, add_special_tokens=False)['input_ids']
    ci = tok(r['completion'] + EOS, add_special_tokens=False)['input_ids']
    return pi, ci


data = []
for r in rows:
    pi, ci = encode(r)
    if len(pi) + len(ci) <= MAXLEN:
        data.append((pi, ci))
if not data:
    raise ValueError('길이 필터 후 학습 문제 0개')
recipe.update(input_rows=len(rows), used_rows=len(data), filtered_rows=len(rows)-len(data))
print(f'학습 문제 {len(data)}/{len(rows)} · 평균 길이 {sum(len(p) + len(c) for p, c in data) / len(data):.0f} 토큰 · 정답 토큰 평균 {sum(len(c) for p, c in data) / len(data):.1f}', flush=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb, dtype=torch.bfloat16, device_map={'': 0})
print('모델 올림', type(model).__name__, '· GPU 메모리', f'{torch.cuda.memory_allocated() / 2**30:.1f}GB', flush=True)
# prepare_model_for_kbit_training 은 양자화 안 된 매개변수를 fp32 로 올린다 — 26만×(42층×256) 짜리 층별 임베딩 표(약 5.6GB)가 11GB 가 되므로 쓰지 않는다.
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
model.enable_input_require_grads()
cfg = LoraConfig(r=RANK, lora_alpha=2 * RANK, lora_dropout=0.05, bias='none', task_type='CAUSAL_LM',
                 target_modules=TARGETS)
model = get_peft_model(model, cfg)
model.print_trainable_parameters()
params = [p for p in model.parameters() if p.requires_grad]
opt_ = torch.optim.AdamW(params, lr=LR, weight_decay=0.0, betas=(0.9, 0.999))
steps = math.ceil(len(data) * EPOCHS / ACCUM)
warm = max(1, int(0.05 * steps))
sched = torch.optim.lr_scheduler.LambdaLR(opt_, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, steps - warm))) * 0.9 + 0.1)
# 초기 손실은 평가 세트가 아니라 사용한 학습 자료 전체에서만 측정한다.
if SCHEDULE == 'finch':
    model.eval()
    initial_total = 0.0
    init_started = time.time()
    with torch.no_grad():
        for j, (pi, ci) in enumerate(data):
            ids = torch.tensor([pi + ci], device='cuda')
            out = model(input_ids=ids, logits_to_keep=len(ci) + 1)
            initial_total += torch.nn.functional.cross_entropy(
                out.logits[0, :-1].float(), torch.tensor(ci, device='cuda')).item()
            if (j + 1) % 100 == 0 or j + 1 == len(data):
                print(f'초기 손실 측정 {j + 1}/{len(data)}', flush=True)
    initial_loss = initial_total / len(data)
    adaptive = LossAdaptiveRate(initial_loss, BASE_RATE, CAP, ALPHA)
    recipe.update(initial_loss=initial_loss, initial_loss_seconds=time.time()-init_started)
    del out, ids
    torch.cuda.empty_cache()
    print(f'초기 손실 {initial_loss:.6f}', flush=True)
model.train()
window_loss, window_count = 0.0, 0
rate_trace = []
t0, done, run_loss, nlog = time.time(), 0, 0.0, 0
for ep in range(EPOCHS):
    order = list(range(len(data)))
    random.shuffle(order)
    for k, i in enumerate(order):
        pi, ci = data[i]
        ids = torch.tensor([pi + ci], device='cuda')
        keep = len(ci) + 1                       # 정답 첫 토큰을 맞히는 위치(프롬프트 마지막)부터 끝까지
        out = model(input_ids=ids, logits_to_keep=keep)
        logits = out.logits[0, :-1].float()      # 마지막 위치 로짓은 다음 토큰 예측이라 쓰지 않는다
        loss = torch.nn.functional.cross_entropy(logits, torch.tensor(ci, device='cuda'))
        (loss / ACCUM).backward()
        window_loss += loss.item()
        window_count += 1
        run_loss += loss.item()
        nlog += 1
        if (k + 1) % ACCUM == 0 or k == len(order) - 1:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            if SCHEDULE == 'finch':
                used_lr = adaptive.apply_before_step(opt_, window_loss / window_count)
            else:
                used_lr = opt_.param_groups[0]['lr']
            # 현재 갱신에 실제로 사용한 학습률을 기록한다.
            opt_.step()
            if SCHEDULE == 'cosine':
                sched.step()
            rate_trace.append(dict(step=done+1, loss=window_loss/window_count,
                                   lr=used_lr, ema=adaptive.ema if SCHEDULE == 'finch' else None))
            window_loss, window_count = 0.0, 0
            opt_.zero_grad(set_to_none=True)
            done += 1
            if done % 10 == 0 or done == steps:
                el = time.time() - t0
                print(f'ep {ep + 1} step {done}/{steps} loss {run_loss / nlog:.4f} lr {used_lr:.2e} {el / 60:.1f}분 · 남은 약 {el / done * (steps - done) / 60:.0f}분 · 최대 GPU {torch.cuda.max_memory_allocated() / 2**30:.1f}GB', flush=True)
                run_loss, nlog = 0.0, 0
model.save_pretrained(OUT)
recipe.update(status='completed', optimizer_steps=done,
              training_seconds=time.time()-t0, rate_trace=rate_trace,
              torch_version=torch.__version__)
with open(os.path.join(OUT, 'recipe_complete.json'), 'x', encoding='utf-8') as f:
    json.dump(recipe, f, ensure_ascii=False, indent=2)
print('저장', OUT, f'총 {(time.time() - t0) / 60:.1f}분', flush=True)
