# 새 서버(A4000 16GB)에서 pplx-decider-v1-27b(자체 PyTorch 코드, GGUF 변환 불가)를 bitsandbytes 4비트(NF4)로 올려 mix9·mix8 을 Jev 와 같은 요청으로 푼다.
#  모델 코드(autojev/model.py)를 읽어 적재 부분만 바꿔 쓴다(4비트 양자화 + GPU/RAM 분할, readout 은 GPU) — 모델 가중치·프롬프트·읽기 방식은 그대로.
import json, os, sys, time
from datetime import date
sys.path.insert(0, '/root/pplx27b/source/src')
import torch
import transformers

SRC = open('/root/pplx27b/source/src/autojev/model.py', encoding='utf-8').read()
old_load = 'self.backbone = Qwen3_5Model.from_pretrained(str(checkpoint), dtype=dtype, attn_implementation="sdpa")'
assert old_load in SRC
SRC = SRC.replace(old_load, 'self.backbone = Qwen3_5Model.from_pretrained(str(checkpoint), dtype=dtype, attn_implementation="sdpa", quantization_config=transformers.BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, llm_int8_enable_fp32_cpu_offload=True), device_map={"visual": "cpu", "language_model.embed_tokens": "cpu", "language_model.layers": 0, "language_model.norm": 0, "language_model.rotary_emb": 0})')
assert 'self.to(self.device_name)' in SRC
SRC = SRC.replace('self.to(self.device_name)', 'self.readout.to("cuda:0")')
old_fwd = 'hidden: torch.Tensor = self.backbone(**batch.inputs, use_cache=False).last_hidden_state[:, -1]'
assert old_fwd in SRC
SRC = SRC.replace(old_fwd, 'hidden: torch.Tensor = self.backbone(**batch.inputs, use_cache=False).last_hidden_state[:, -1].to(self.readout.weight.device)')
ns = {'__name__': 'autojev.model_q4', 'transformers': transformers}
exec(compile(SRC, 'model_q4', 'exec'), ns)
DecisionModel = ns['DecisionModel']
W = '월화수목금토일'
t0 = time.time()
model = DecisionModel(checkpoint='/root/pplx27b', device='cuda')
# 임베딩(2.4GiB)을 GPU 로 올리면 4비트 층(약 13GiB)과 합쳐 16GB 를 넘어 메모리가 부족하다 — 임베딩만 CPU 에서 조회하고 결과를 GPU 로 보낸다(가중치는 체크포인트 그대로).
from safetensors import safe_open
INSTR = '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.'
if os.environ.get('RULE'):          # 정의 명시: 올라마 직접 짚기 --proto·Claude --proto 와 같은 문장을 지시문 끝에 덧붙인다
    INSTR += ' 한 문장에 항목이 여럿 나오면 가장 먼저 언급된 항목 하나만 고른다. 「그거·거기·방금 바꾼 것」 같은 말은 앞 대화에서 가리키는 항목으로 푼다. 앞 대화가 없어 대상을 알 수 없으면 null 이다.'
with safe_open('/root/pplx27b/model-00001-of-00011.safetensors', framework='pt') as _f:
    _EW = _f.get_tensor('language_model.embed_tokens.weight')


class CPUEmbed(torch.nn.Module):
    def __init__(self, w):
        super().__init__()
        self.w = w
        self.embedding_dim = w.shape[1]

    def forward(self, ids):
        return torch.nn.functional.embedding(ids.cpu(), self.w).to('cuda:0')


model.backbone.language_model.embed_tokens = CPUEmbed(_EW)
print('모델 적재', f'{time.time() - t0:.0f}초', 'GPU 사용 GiB', round(torch.cuda.memory_allocated() / 2 ** 30, 1), flush=True)
LIMIT = int(os.environ.get('LIMIT', '0'))


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'/root/work/{name}.json', encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    ids = [i['id'] for i in items]
    keys = [f'item_{i}' for i in ids] + ['none']
    rows, t1, errs = [], time.time(), 0
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    for qi, x in enumerate(qs):
        crit = {f"item_{i['id']}": lab(i) for i in items}
        crit['none'] = '이 일정에는 고객 문장이 가리키는 항목이 없다'
        state = {'today': job['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        question = {'type': 'choice', 'instructions': INSTR, 'criteria': crit}
        try:
            probs = model.predict([{'state': state, 'question': question}], batch_size=1)[0]
            rows.append({'probs': dict(zip(keys, map(float, probs))), 'confidence': None})
        except Exception as e:  # noqa: BLE001
            errs += 1
            rows.append({'probs': {}, 'confidence': None})
            if errs <= 3:
                import traceback; traceback.print_exc(); print('오류', qi, str(e)[:200], flush=True)
        if qi % 10 == 0:
            print(name, qi, f'{(time.time() - t1) / (qi + 1):.1f}초/문제', flush=True)
    res = {name: {'ids': ids, 'rows': rows, 'keys': keys[:-1]}, '_sec_per_q': (time.time() - t1) / max(1, len(rows)), '_n': len(rows), '_errors': errs, '_tag': 'pplx27b-nf4'}
    json.dump(res, open(f'/root/work/dec_pplx27b_{name}.json' if not LIMIT else f'/root/work/dec_pplx27b_{name}_smoke.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"pplx27b {name} {len(rows)}문제 {res['_sec_per_q']:.1f}초/문제 오류 {errs}", flush=True)
