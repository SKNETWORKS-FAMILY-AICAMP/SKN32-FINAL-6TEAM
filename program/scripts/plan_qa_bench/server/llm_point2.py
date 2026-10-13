# 서버에서: 모델마다 같은 질의문으로 「일정 번호 하나 또는 null」만 받는다. 값은 쓰지 않는다.
# 사용: python3 llm_point2.py --sets test50,hard40 모델...   (hf-local:<허깅페이스 id> 는 torch 로 직접 돌린다)
import json, os, re, sys, time, urllib.request
from datetime import date

args = sys.argv[1:]
SETS = None
if args and args[0] == '--sets':
    SETS = args[1].split(',')
    args = args[2:]
job = json.load(open('job.json', encoding='utf-8'))
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(),
                                       headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{"item": null}'}, 'error': str(e)[:200]}
            time.sleep(5)


class HFLocal:
    def __init__(self, name):
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(name)
        self.m = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.bfloat16, device_map='cuda').eval()

    def ask(self, text):
        msgs = [{'role': 'user', 'content': text + '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'}]
        # transformers 5: apply_chat_template 은 dict 형태(BatchEncoding)를 돌려준다 — 텐서로 바로 쓰면 shape 오류
        enc = self.tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors='pt', return_dict=True).to('cuda')
        with self.torch.no_grad():
            out = self.m.generate(**enc, max_new_tokens=24, do_sample=False)
        s = self.tok.decode(out[0, enc['input_ids'].shape[1]:], skip_special_tokens=True)
        m = re.search(r'"item"\s*:\s*(null|\d+)', s)
        return {'message': {'content': '{"item": %s}' % (m.group(1) if m else 'null')}}


out = json.load(open('llm_out.json')) if os.path.exists('llm_out.json') and os.path.getsize('llm_out.json') else {}
for model in args:
    hf = HFLocal(model.split(':', 1)[1]) if model.startswith('hf-local:') else None
    res = {}
    errors = 0
    nq = 0
    t0 = time.time()
    for name, st in job['sets'].items():
        if SETS and name not in SETS:
            continue
        items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
        days = sorted({i['date'] for i in items})
        ids = {i['id'] for i in items}

        def lab(i):
            d = date.fromisoformat(i['date'])
            return (f"{days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} "
                    f"[{i['kind']}] {i['title']} @ {i['place']}")

        plan = '\n'.join(f"{i['id']}. {lab(i)}" for i in items)
        picks = []
        for x in st['qs']:
            text = (f"오늘은 {st['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n"
                    f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                    "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
            if hf:
                r = hf.ask(text)
            else:
                b = {'model': model, 'stream': False, 'format': S, 'options': {'temperature': 0},
                     'messages': [{'role': 'user', 'content': text}]}
                b['think'] = 'low' if 'gpt-oss' in model else False
                if os.environ.get('PLAIN'):
                    # 형식 강제 없이 짧게: 이 모델은 형식을 강제하면 답이 비어 나왔다(Muse 0/90). 번호만 정규식으로 읽는다
                    del b['format']
                    b['options']['num_predict'] = 24
                    b['messages'][0]['content'] = text + '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'
                r = post(b)
            errors += 'error' in r
            try:
                v = json.loads(r['message']['content']).get('item')
            except Exception:  # noqa: BLE001
                v = None
                if os.environ.get('PLAIN'):
                    m = re.search(r'"item"\s*:\s*(null|\d+)', r['message'].get('content') or '')
                    v = int(m.group(1)) if (m and m.group(1) != 'null') else None
            picks.append(v if v in ids else None)
            nq += 1
        res[name] = picks
    res['_sec_per_q'] = (time.time() - t0) / max(nq, 1)
    res['_errors'] = errors
    out[model + ('#plain' if os.environ.get('PLAIN') else '')] = res
    tmp = 'llm_out.json.tmp'
    json.dump(out, open(tmp, 'w'), ensure_ascii=False)
    os.replace(tmp, 'llm_out.json')
    print(model, f"{res['_sec_per_q']:.2f}s/q errors={errors}", flush=True)
    if hf:
        del hf
