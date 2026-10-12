# 서버에서: WoS 지시어 묶음(wos.json 의 모든 세트)을 올라마 직접 짚기로 푼다 — llm_point_heavy.py 와 같은 질의문·형식 강제(끝 지시 없음).
#  결과 llm_wos_out.json = {모델: {'picks': [세트 순서대로 이어 붙인 문제별 답], ...}} — 문제 순서는 wos.json 의 세트 이름 순, 세트 안 순서.
# 사용: python3 llm_point_wos.py 모델...
import json, os, sys, time, urllib.request
from datetime import date

models = sys.argv[1:]
sets = json.load(open('wos.json', encoding='utf-8'))['sets']
OUTF = 'llm_wos_out.json'
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{"item": null}'}, 'error': str(e)[:200]}
            time.sleep(5)


out = json.load(open(OUTF)) if os.path.exists(OUTF) and os.path.getsize(OUTF) else {}
for model in models:
    picks, errors, t0 = [], 0, time.time()
    for name in sorted(sets):
        job = sets[name]
        items_all = sorted(job['items'], key=lambda i: (i['date'], i['start']))
        days = sorted({i['date'] for i in items_all})
        ids_all = {i['id'] for i in items_all}

        def lab(i):
            d = date.fromisoformat(i['date'])
            return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
        plan = '\n'.join(lab(i) for i in items_all)
        for x in job['qs']:
            hist = ''
            if x.get('history'):
                hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
            text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
                    f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                    "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
            b = {'model': model, 'stream': False, 'format': S, 'options': {'temperature': 0}, 'think': False, 'messages': [{'role': 'user', 'content': text}]}
            r = post(b)
            errors += 'error' in r
            try:
                v = json.loads(r['message']['content']).get('item')
            except Exception:  # noqa: BLE001
                v = None
            picks.append(v if v in ids_all else None)
    out[model] = {'picks': picks, '_sec_per_q': (time.time() - t0) / max(1, len(picks)), '_errors': errors}
    tmp = OUTF + '.tmp'
    json.dump(out, open(tmp, 'w'), ensure_ascii=False)
    os.replace(tmp, OUTF)
    print(model, f"{out[model]['_sec_per_q']:.2f}s/q errors={errors}", flush=True)
