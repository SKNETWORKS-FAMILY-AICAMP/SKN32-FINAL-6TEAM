# Jev-Omni(akhilaaa3, Gemma-4-12B 합병 + 256갈래 결정 머리, Apache) 를 우리 문제에 푼다 — 원본 로더(jev_omni.py)의 JevOmni·머리·프롬프트를 그대로 쓰고
#  적재만 16GB GPU 에 맞게 바꾼다(원본은 bf16 24GB 를 GPU 한 장에 올린다): MODE=q8(bitsandbytes 8비트, 기본) · off(bf16 + 램 오프로드).
# 선택지는 「1. 설명 2. 설명 …」 번호 목록(머리가 번호 칸을 읽는다). 선택지 43개 > 20개 — 저자는 20개 초과 품질을 보증하지 않는다(머리는 256 지원).
# 사용: MODE=q8 TAG=jevomni SETS=mix9,mix8 python jev_omni_run.py   (LIMIT=2 스모크)
import json, os, sys, time
from datetime import date
from pathlib import Path
import torch
import transformers
from huggingface_hub import snapshot_download
from transformers import AutoConfig, AutoProcessor, BitsAndBytesConfig

MODE = os.environ.get('MODE', 'q8')
TAG = os.environ['TAG']
LIMIT = int(os.environ.get('LIMIT', '0'))
path = snapshot_download('akhilaaa3/Jev-Omni', allow_patterns=['config.json', 'generation_config.json', 'model*.safetensors*', 'processor_config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja', 'decision_config.json', 'head.pt', 'jev_omni.py'])
sys.path.insert(0, path)
import jev_omni as jo

t0 = time.time()
config = AutoConfig.from_pretrained(path)
cls = getattr(transformers, config.architectures[0])
if MODE == 'q8':
    model = cls.from_pretrained(path, dtype=torch.bfloat16, quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map={'': 0}).eval()
else:
    model = cls.from_pretrained(path, dtype=torch.bfloat16, device_map='auto', max_memory={0: '7GiB', 'cpu': '42GiB'}, offload_folder='/root/offload').eval()
decision = json.loads((Path(path) / 'decision_config.json').read_text())
head = jo._Head256(decision['hidden_size']).to('cuda:0').eval()
head.load_state_dict(torch.load(Path(path) / 'head.pt', map_location='cuda:0', weights_only=True))
_, decoder = jo._find_backbone(model)
clf = jo.JevOmni(model, head, AutoProcessor.from_pretrained(path), decoder, 'cuda:0')
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
        options = [lab(i) for i in items] + ['이 일정에는 고객 문장이 가리키는 항목이 없다']
        state = {'today': job['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        try:
            r = clf.predict(state=json.dumps(state, ensure_ascii=False, indent=1), question='고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 마지막 선택지.', options=options)
            pr = [r['probabilities'][o] for o in options]
            rows.append({'probs': dict(zip(keys, map(float, pr))), 'confidence': r['confidence']})
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
