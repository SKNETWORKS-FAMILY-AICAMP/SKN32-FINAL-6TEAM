# Cygnet(blockbrain-ai/cygnet-recipe — 얼린 google/gemma-4-12B-it + 선택지 글자 읽기 + 온도 3.4)를 우리 문제에 푼다.
#  원 레시피는 vLLM 0.30.0 + shim 이다. 이 서버 GPU 는 16GB 라 vLLM bf16(24GB)이 안 올라가므로 **모델 호출 한 곳만** 바꿨다:
#   - 프롬프트(system + 사용자), 20개 초과 선택지의 묶음 읽기, 글자 확률 합산, 온도 p^(1/T) 재정규화는 레시피 코드(shim/decision_server.py) 그대로 쓴다.
#   - vLLM 의 `structured_outputs: choice`(선택지 글자만 허용) 는 「허용 글자 토큰만 남긴 log_softmax」로 같게 흉내 낸다.
#   - 모델은 bitsandbytes 8비트(MODE=q8, 기본)·bf16 오프로드(MODE=off)·4비트(MODE=q4) 중 고른다 — 원본은 bf16.
# 사용: MODE=q8 TAG=cygnet SETS=mix9,mix8 python cygnet_hf_run.py   (LIMIT=2 이면 스모크)
import json, os, sys, threading, time
from datetime import date

CY = os.environ.get('CYGNET_DIR', '/root/cygnet/shim')
sys.path.insert(0, CY)
os.environ.setdefault('SHIM_TEMPERATURE', '3.4')
os.environ['CYGNET_MAX_PARALLEL'] = '1'
os.environ.setdefault('CYGNET_ALLOW_NO_KEY', '1')
import torch
import torch.nn.functional as F
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import decision_server as ds

MODE = os.environ.get('MODE', 'q8')
TAG = os.environ['TAG']
LIMIT = int(os.environ.get('LIMIT', '0'))
NAME = 'google/gemma-4-12B-it'
t0 = time.time()
tok = AutoTokenizer.from_pretrained(NAME)
kw = dict(dtype=torch.bfloat16)
if MODE == 'q8':
    kw.update(quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map={'': 0})
elif MODE == 'q4':
    kw.update(quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16), device_map={'': 0})
else:
    kw.update(device_map='auto', max_memory={0: '7GiB', 'cpu': '42GiB'}, offload_folder='/root/offload')
model = AutoModelForCausalLM.from_pretrained(NAME, **kw).eval()
print('모델 적재', f'{time.time() - t0:.0f}초', MODE, 'GPU GiB', round(torch.cuda.memory_allocated() / 2 ** 30, 1), flush=True)

# 글자 → 그 글자로 디코딩되는 토큰 번호들(젬마 4 는 같은 글자가 토큰 둘이다 — 합산)
_letter_ids = {}
vocab = tok.get_vocab()
for tid in vocab.values():
    s = tok.decode([tid])
    if len(s) == 1 and s in ds.shim.LETTERS:
        _letter_ids.setdefault(s, []).append(tid)
print('글자 토큰', {k: len(v) for k, v in sorted(_letter_ids.items())}, flush=True)
_lock = threading.Lock()


def call_local(prompt_text, allowed_letters):
    msgs = [{'role': 'system', 'content': ds.shim.SYSTEM}, {'role': 'user', 'content': prompt_text}]
    enc = tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False, return_tensors='pt', return_dict=True)
    ids = {k: v.to('cuda:0') for k, v in enc.items()}
    with _lock, torch.no_grad():
        try:
            lg = model(**ids, logits_to_keep=1).logits[0, -1].float()
        except TypeError:
            lg = model(**ids).logits[0, -1].float()
    flat = []
    for L in allowed_letters:
        for tid in _letter_ids.get(L, []):
            flat.append((L, tid))
    sel = torch.tensor([t for _l, t in flat], device=lg.device)
    lp = F.log_softmax(lg[sel], dim=-1).tolist()
    top = [{'token': l, 'logprob': p} for (l, _t), p in zip(flat, lp)]
    return {'choices': [{'logprobs': {'content': [{'top_logprobs': top}]}}],
            'usage': {'prompt_tokens': int(ids['input_ids'].shape[1]), 'completion_tokens': 1}}


ds.shim.call_vllm = call_local
ds.shim.server_context = lambda: 16384
W = '월화수목금토일'


def lab(i):
    dd = date.fromisoformat(i['date'])
    return f"{dd.month}/{dd.day}({W[dd.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'/root/work/{name}.json', encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    ids_ = [i['id'] for i in items]
    keys = [f'item_{i}' for i in ids_] + ['none']
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    rows, errs, t1 = [], 0, time.time()
    for qi, x in enumerate(qs):
        crit = {f"item_{i['id']}": lab(i) for i in items}
        crit['none'] = '이 일정에는 고객 문장이 가리키는 항목이 없다'
        state = {'today': job['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        body = {'state': state, 'questions': {'q': {'type': 'choice', 'instructions': '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.', 'criteria': crit}}}
        try:
            obj = ds.evaluate(body)
            a = obj['answers']['q']
            rows.append({'probs': {k: float(v) for k, v in a['probabilities'].items()}, 'confidence': a.get('confidence')})
        except Exception as e:  # noqa: BLE001
            errs += 1
            rows.append({'probs': {}, 'confidence': None})
            if errs <= 3:
                import traceback; traceback.print_exc(); print('오류', qi, str(e)[:300], flush=True)
        if qi % 20 == 0:
            print(name, qi, f'{(time.time() - t1) / (qi + 1):.2f}초/문제', flush=True)
    res = {name: {'ids': ids_, 'rows': rows, 'keys': keys[:-1]}, '_sec_per_q': (time.time() - t1) / max(1, len(rows)), '_n': len(rows), '_errors': errs, '_tag': TAG, '_mode': MODE}
    json.dump(res, open(f'/root/work/dec_{TAG}_{name}.json' if not LIMIT else f'/root/work/dec_{TAG}_{name}_smoke.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"{TAG} {name} {len(rows)}문제 {res['_sec_per_q']:.2f}초/문제 오류 {errs}", flush=True)
