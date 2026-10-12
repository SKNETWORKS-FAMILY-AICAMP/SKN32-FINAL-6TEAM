# Hopper 12B(HopitAI/hopper 브랜치 hopper-12b: 얼린 google/gemma-4-12B-it + LoRA r32 어댑터, Apache-2.0)를 우리 문제에 푼다.
#  원 레시피: hopper-serve --base-loader gemma-4-12b-it(bf16 24GB). 이 서버 GPU 는 16GB 라 **기본 모델 적재만** 바꿨다 — bitsandbytes 8비트(MODE=q8) 위에 어댑터를 얹고(합치지 않음, 원본과 같은 방식),
#  프롬프트·글자 읽기·26개 초과 선택지의 토너먼트(시드 고정, k=10)·읽기 보정 지도는 레시피 코드(hopper_decisions.frozen.FrozenDecider) 그대로 쓴다.
# 사용: MODE=q8 TAG=hopper12b SETS=mix9,mix8 python hopper12b_run.py   (LIMIT=2 스모크)
import json, os, sys, time
from datetime import date
from pathlib import Path
sys.path.insert(0, '/root/repos_h/hopper')
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
from hopper_decisions import frozen

MODE = os.environ.get('MODE', 'q8')
TAG = os.environ['TAG']
LIMIT = int(os.environ.get('LIMIT', '0'))
ADAPTER = 'HopitAI/hopper'
AREV = '4b605f25eb903c2cf4d121040ffb097240b3bc37'
READOUT = '/root/repos_h/hopper/hopper_decisions/maps/hopper-12b-trained-readout.json'
t0 = time.time()
tok = AutoTokenizer.from_pretrained(frozen.BASE, revision=frozen.REVISION)
kw = dict(revision=frozen.REVISION, dtype=torch.bfloat16, attn_implementation='sdpa', low_cpu_mem_usage=True)
if MODE == 'q8':
    kw.update(quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map={'': 0})
else:
    kw.update(device_map='auto', max_memory={0: '7GiB', 'cpu': '42GiB'}, offload_folder='/root/offload')
base = AutoModelForCausalLM.from_pretrained(frozen.BASE, **kw)
model = PeftModel.from_pretrained(base, ADAPTER, revision=AREV)
dec = frozen.FrozenDecider(model, tok, READOUT, name='hopper-12b', device='cuda:0')
print('모델 적재', f'{time.time() - t0:.0f}초', MODE, 'GPU GiB', round(torch.cuda.memory_allocated() / 2 ** 30, 1), flush=True)
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
        req = {'state': state, 'questions': {'q': {'type': 'choice', 'instructions': '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.', 'criteria': crit}}}
        try:
            r = dec.decide(req)
            a = r['answers']['q'] if 'answers' in r else r
            pr = a.get('probabilities') or a.get('probs')
            rows.append({'probs': {k: float(v) for k, v in pr.items()}, 'confidence': a.get('confidence')})
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
