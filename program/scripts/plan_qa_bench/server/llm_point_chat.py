# 서버에서: 잡담 표본을 일정 짚기 질문처럼 올라마 모델에게 풀게 해 「항목을 잘못 짚는」 비율(정답은 항상 없음)을 잰다 — 앞단 없이 직접 짚기와 같은 질의문·형식 강제.
# 사용: SET=mix7 [IDXFILE=번호목록.json] [N=300] python3 llm_point_chat.py <잡담 JSON> 모델... → chat_llm_<세트>_<모델>.json = {'picks': {번호: 항목|null}}
import json, os, sys, time, urllib.request
from datetime import date

chat = json.load(open(sys.argv[1], encoding='utf-8'))
models = sys.argv[2:]
SET = os.environ.get('SET', 'mix7')
job = json.load(open(f'{SET}.json', encoding='utf-8'))['sets'][SET]
idx = json.load(open(os.environ['IDXFILE'])) if os.environ.get('IDXFILE') else list(range(int(os.environ.get('N', len(chat)))))
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})
ids = {i['id'] for i in items}
plan = '\n'.join(f"{i['id']}. {days.index(i['date']) + 1}일차 {date.fromisoformat(i['date']).month}/{date.fromisoformat(i['date']).day}({W[date.fromisoformat(i['date']).weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}" for i in items)


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{"item": null}'}, 'error': str(e)[:200]}
            time.sleep(5)


for model in models:
    picks, t0, errs = {}, time.time(), 0
    for k in idx:
        text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n고객 질문: {chat[k]}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
        r = post({'model': model, 'stream': False, 'format': S, 'options': {'temperature': 0}, 'think': False, 'messages': [{'role': 'user', 'content': text}]})
        errs += 'error' in r
        try:
            v = json.loads(r['message']['content']).get('item')
        except Exception:  # noqa: BLE001
            v = None
        picks[str(k)] = v if v in ids else None
    name = model.replace(':', '_').replace('/', '_')
    json.dump({'picks': picks, '_sec_per_q': (time.time() - t0) / len(idx), '_errors': errs}, open(f'chat_llm_{SET}_{name}.json', 'w'))
    print(model, f"{(time.time() - t0) / len(idx):.2f}s/q errors={errs} 항목답 {sum(v is not None for v in picks.values())}/{len(idx)}", flush=True)
