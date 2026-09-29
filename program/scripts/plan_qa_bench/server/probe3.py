import json, sys, time, urllib.request

model = sys.argv[1]
mode = sys.argv[2]  # plain | think_off_opt | format
job = json.load(open('job.json', encoding='utf-8'))
st = job['sets']['test50']
items = st['items']
q = st['qs'][0]['q']
plan = '\n'.join(f"{i['id']}. {i['date']} {i['start']} {i['title']} @ {i['place']}" for i in items)
ask = 'JSON 한 줄로만 답하라. 예: {"item": 3} 또는 {"item": null}'
b = {'model': model, 'stream': False, 'options': {'temperature': 0, 'num_predict': 24},
     'messages': [{'role': 'user', 'content': f"일정:\n{plan}\n\n질문: {q}\n\n이 질문이 가리키는 일정 번호 하나. {ask}"}]}
if mode == 'format':
    b['format'] = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
if mode in ('format', 'think_false'):
    b['think'] = False
t = time.time()
try:
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(),
                                 headers={'content-type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=170).read())
    m = r['message']
    print(mode, round(time.time() - t, 1), '초 | 내용', repr(m['content'][:100]), '| 생각', repr((m.get('thinking') or '')[:60]),
          '| 토큰', r.get('eval_count'), '| 정답 기대', st['qs'][0]['gold'])
except Exception as e:  # noqa: BLE001
    print(mode, '실패', round(time.time() - t, 1), repr(e)[:150])
