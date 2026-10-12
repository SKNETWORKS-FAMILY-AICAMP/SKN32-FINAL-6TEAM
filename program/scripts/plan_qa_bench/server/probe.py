import json, sys, time, urllib.request

model = sys.argv[1]
job = json.load(open('job.json', encoding='utf-8'))
st = job['sets']['test50']
items = st['items']
q = st['qs'][0]['q']
plan = '\n'.join(f"{i['id']}. {i['date']} {i['start']} {i['title']} @ {i['place']}" for i in items)
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
b = {'model': model, 'stream': False, 'format': S, 'think': False, 'options': {'temperature': 0, 'num_predict': 40},
     'messages': [{'role': 'user', 'content': f"일정:\n{plan}\n\n질문: {q}\n번호 하나를 item 에 넣어라."}]}
t = time.time()
try:
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(),
                                 headers={'content-type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=170).read())
    print('응답', round(time.time() - t, 1), '초', r['message']['content'][:80],
          {k: r.get(k) for k in ('prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration')})
except Exception as e:  # noqa: BLE001
    print('실패', round(time.time() - t, 1), '초', repr(e)[:150])
