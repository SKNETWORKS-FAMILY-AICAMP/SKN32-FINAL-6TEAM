# decider-ai 라이브러리(Mapika/decider-*)로 mix9·mix8 을 Jev 와 같은 요청으로 푼다 — 16GB GPU 에 안 들어가는 모델용.
# 양자화하지 않고(bf16 그대로) 앞쪽 층만 GPU 에 두고 나머지 층은 램에 두었다가 층마다 GPU 로 가져와 계산한다(accelerate 오프로드).
# 질문을 BATCH 개씩 묶어 한 번에 넣어 가중치 이동 비용을 나눠 낸다. 프롬프트·읽는 방식·온도는 라이브러리 그대로.
# 사용: MODEL=Mapika/decider-35b-a3b TAG=decider35bl SETS=mix9,mix8 GPU_GIB=12 CPU_GIB=42 BATCH=8 python dec_lib_run_off.py   (LIMIT=3 이면 스모크)
# 컨테이너 램 한도(약 58GiB)보다 큰 모델(35B 69GB 등)은 CPU_GIB 를 낮춰 나머지를 디스크로 보낸다.
import json, os, sys, time
from datetime import date
import torch
import torch.nn.functional as F
import decider.model as dm
import decider.infer as di
from decider import temperature as TT
from decider.systemone import assemble
from decider.model import cap_logits
from decider.prompt import MAX_OPTIONS
INSTR = '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.'
if os.environ.get('RULE'):          # 정의 명시: 올라마 직접 짚기 --proto·Claude --proto 와 같은 문장을 지시문 끝에 덧붙인다
    INSTR += ' 한 문장에 항목이 여럿 나오면 가장 먼저 언급된 항목 하나만 고른다. 「그거·거기·방금 바꾼 것」 같은 말은 앞 대화에서 가리키는 항목으로 푼다. 앞 대화가 없어 대상을 알 수 없으면 null 이다.'

W = '월화수목금토일'
MODEL, TAG = os.environ['MODEL'], os.environ['TAG']
GPU_GIB = os.environ.get('GPU_GIB', '7')
BATCH = int(os.environ.get('BATCH', '8'))
LIMIT = int(os.environ.get('LIMIT', '0'))

_orig = dm.AutoModelForCausalLM.from_pretrained


CPU_GIB = os.environ.get('CPU_GIB', '40')      # 컨테이너 메모리 한도(약 58GiB) 안에서 램에 둘 양 — 넘치는 층은 디스크에 두고 필요할 때 읽는다
OFFLOAD_DIR = os.environ.get('OFFLOAD_DIR', '/root/offload')


def _off(name, dtype=None, **k):
    return _orig(name, dtype=dtype, device_map='auto', max_memory={0: f'{GPU_GIB}GiB', 'cpu': f'{CPU_GIB}GiB'}, offload_folder=OFFLOAD_DIR, **k)


dm.AutoModelForCausalLM = type('AMO', (), {'from_pretrained': staticmethod(_off)})
dm.DecisionModel.to = lambda self, *a, **k: self      # 오프로드된 가중치는 옮기지 않는다(옮기면 meta 텐서 오류)


def slot_logits(self, input_ids, attention_mask, slot_idx, slot_batch, nopts):
    h = self.lm.model(input_ids=input_ids.to('cuda:0'), attention_mask=attention_mask.to('cuda:0')).last_hidden_state
    hs = h[slot_batch.to(h.device), slot_idx.to(h.device)]
    full = self.lm.lm_head(hs)                          # lm_head 가 램에 있으면 훅이 GPU 로 가져온다
    lg = cap_logits(self, full[:, self.letters.to(full.device)].float())
    ar = torch.arange(MAX_OPTIONS, device=lg.device)[None, :]
    return lg.masked_fill(ar >= nopts.to(lg.device)[:, None], float('-inf'))


dm.DecisionModel.slot_logits = slot_logits

t0 = time.time()
d = di.Decider(MODEL, device='cuda', use_graphs=False, dtype=torch.bfloat16)
print('모델 적재', f'{time.time() - t0:.0f}초', 'GPU 사용 GiB', round(torch.cuda.memory_allocated() / 2 ** 30, 1), 'layout', d.layout, 'schema_first', d.schema_first, flush=True)
try:
    from collections import Counter
    print('장치 분포', Counter(str(v) for v in d.m.lm.hf_device_map.values()), flush=True)
except Exception as e:  # noqa: BLE001
    print('장치 분포 확인 실패', e, flush=True)


def lab(i):
    dd = date.fromisoformat(i['date'])
    return f"{dd.month}/{dd.day}({W[dd.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'/root/work/{name}.json', encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    ids = [i['id'] for i in items]
    keys = [f'item_{i}' for i in ids] + ['none']
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    ONLY = os.environ.get('ONLY')          # 'heavy:32,33;mix4:0,1' 처럼 일부 문제만 다시 풀 때(앞 실행에서 GPU 메모리 부족으로 비어 온 문제)
    sub = None
    if ONLY:
        om = {k: [int(x) for x in v.split(',')] for k, v in (e.split(':') for e in ONLY.split(';'))}
        if name not in om:
            continue
        sub = om[name]
        qs = [job['qs'][i] for i in sub]
    rows, errs, t1 = [], 0, time.time()
    for s in range(0, len(qs), BATCH):
        chunk = qs[s:s + BATCH]
        built = []
        for x in chunk:
            crit = {f"item_{i['id']}": lab(i) for i in items}
            crit['none'] = '이 일정에는 고객 문장이 가리키는 항목이 없다'
            state = {'today': job['today'], 'customer_message': x['q']}
            if x.get('history'):
                state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
            question = {'type': 'choice', 'instructions': INSTR, 'criteria': crit}
            built.append(d._system_one_items(state, {'q': question}, True, 32768, None, None))
        flat_items = [it for _, _, its in built for it in its]
        try:
            mx = max(len(it['ids']) for it in flat_items)
            flatp = d._system_one_probs(flat_items, d.schema_first and 'schema_first' or 'state_first', max(1, BATCH) * mx, TT.for_items(d.T, d.T_by_type, flat_items))
            c = 0
            for rqs, index, its in built:
                ans = assemble(rqs, index, flatp[c:c + len(its)])['q']
                c += len(its)
                rows.append({'probs': {k: float(v) for k, v in ans['probabilities'].items()}, 'confidence': ans.get('confidence')})
        except Exception as e:  # noqa: BLE001
            errs += len(chunk)
            rows += [{'probs': {}, 'confidence': None} for _ in chunk]
            if errs <= 3 * BATCH:
                import traceback; traceback.print_exc(); print('오류', s, str(e)[:300], flush=True)
        print(name, len(rows), f'{(time.time() - t1) / max(1, len(rows)):.2f}초/문제', flush=True)
    res = {name: {'ids': ids, 'rows': rows, 'keys': keys[:-1], 'sub': sub}, '_sec_per_q': (time.time() - t1) / max(1, len(rows)), '_n': len(rows), '_errors': errs, '_tag': TAG}
    json.dump(res, open(f'/root/work/dec_{TAG}_{name}.json' if not (LIMIT or sub) else (f'/root/work/dec_{TAG}_{name}_sub.json' if sub else f'/root/work/dec_{TAG}_{name}_smoke.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"{TAG} {name} {len(rows)}문제 {res['_sec_per_q']:.2f}초/문제 오류 {errs}", flush=True)
