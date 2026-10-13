# 서버에서: 모델마다 같은 질의문으로 「일정 번호 하나 또는 null」만 받는다. 값은 쓰지 않는다.
import json, os, sys, time, urllib.request
from datetime import date

job = json.load(open('job.json', encoding='utf-8'))
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(),
                                       headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=900).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{"item": null}'}, 'error': str(e)}
            time.sleep(5)


out = json.load(open('llm_out.json')) if os.path.exists('llm_out.json') else {}
for model in sys.argv[1:]:
    res = {}
    errors = 0
    t0 = time.time()
    for name, st in job['sets'].items():
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
            b = {'model': model, 'stream': False, 'think': False, 'format': S, 'options': {'temperature': 0},
                 'messages': [{'role': 'user', 'content':
                               f"오늘은 {st['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n"
                               f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                               "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null."}]}
            r = post(b)
            errors += 'error' in r
            try:
                v = json.loads(r['message']['content']).get('item')
            except Exception:  # noqa: BLE001
                v = None
            picks.append(v if v in ids else None)
        res[name] = picks
    n = sum(len(s['qs']) for s in job['sets'].values())
    res['_sec_per_q'] = (time.time() - t0) / n
    res['_errors'] = errors
    out[model] = res
    json.dump(out, open('llm_out.json', 'w'), ensure_ascii=False)
    print(model, f"{res['_sec_per_q']:.2f}s/q errors={errors}", flush=True)
