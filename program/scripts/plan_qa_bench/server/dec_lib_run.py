# decider-ai 라이브러리(Mapika/decider-*)로 mix9·mix8 을 Jev 와 같은 요청(state + choice criteria)으로 푼다 — 모델 가중치·프롬프트·읽기 방식은 라이브러리 그대로.
# 사용: MODEL=Mapika/decider-4b TAG=decider4bl SETS=mix9,mix8 python dec_lib_run.py   (LIMIT=3 이면 스모크)
import json, os, sys, time
from datetime import date
import torch
from decider.infer import Decider

W = '월화수목금토일'
MODEL, TAG = os.environ['MODEL'], os.environ['TAG']
t0 = time.time()
kw = {}
if os.environ.get('NO_GRAPHS'):
    kw['use_graphs'] = False
if os.environ.get('DTYPE'):
    kw['dtype'] = getattr(torch, os.environ['DTYPE'])
if os.environ.get('Q4'):
    # 12B 는 bf16(약 24GB)이 16GB GPU 에 안 들어가 가중치만 bitsandbytes 4비트(NF4)로 올린다 — 프롬프트·읽는 방식은 라이브러리 그대로.
    import transformers
    import decider.model as _dm
    _orig = _dm.AutoModelForCausalLM.from_pretrained

    def _q4(name, dtype=None, **k):
        return _orig(name, dtype=dtype, quantization_config=transformers.BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16), device_map={'': 0}, **k)
    _dm.AutoModelForCausalLM = type('AMQ', (), {'from_pretrained': staticmethod(_q4)})
    kw['use_graphs'] = False
d = Decider(MODEL, **kw)
print('모델 적재', f'{time.time() - t0:.0f}초', 'GPU 사용 GiB', round(torch.cuda.memory_allocated() / 2 ** 30, 1), flush=True)
LIMIT = int(os.environ.get('LIMIT', '0'))


def lab(i):
    dd = date.fromisoformat(i['date'])
    return f"{dd.month}/{dd.day}({W[dd.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


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
        question = {'type': 'choice', 'instructions': '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.', 'criteria': crit}
        try:
            ans = d.system_one(state, {'q': question})['answers']['q']
            rows.append({'probs': {k: float(v) for k, v in ans['probabilities'].items()}, 'confidence': ans.get('confidence')})
        except Exception as e:  # noqa: BLE001
            errs += 1
            rows.append({'probs': {}, 'confidence': None})
            if errs <= 3:
                import traceback; traceback.print_exc(); print('오류', qi, str(e)[:200], flush=True)
        if qi % 20 == 0:
            print(name, qi, f'{(time.time() - t1) / (qi + 1):.2f}초/문제', flush=True)
    res = {name: {'ids': ids, 'rows': rows, 'keys': keys[:-1]}, '_sec_per_q': (time.time() - t1) / max(1, len(rows)), '_n': len(rows), '_errors': errs, '_tag': TAG}
    json.dump(res, open(f'/root/work/dec_{TAG}_{name}.json' if not LIMIT else f'/root/work/dec_{TAG}_{name}_smoke.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"{TAG} {name} {len(rows)}문제 {res['_sec_per_q']:.2f}초/문제 오류 {errs}", flush=True)
