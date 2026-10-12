# 서버에서: OpenDecider(small 4B · nano 0.4B) — 선택지(Choice)로 「이 질문이 가리키는 일정 항목」을 고르고 선택지별 확률을 저장한다.
# 선택지에 「해당 없음」을 직접 넣는다(이 모델에는 「없음」 선택지가 따로 없다). 사용법: python od_run.py <모델> [--probe]
import json, os, sys, time
from datetime import date

name = sys.argv[1]
probe = '--probe' in sys.argv
from opendecider import load, Choice  # noqa: E402

job = json.load(open('job.json', encoding='utf-8'))['sets']
W = '월화수목금토일'
model = load(name)
NONE = '일정에 이 질문이 가리키는 항목이 없다'
res = {}
t0 = time.time()
n = 0
raw_first = None
for sname, st in job.items():
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
    ids = [i['id'] for i in items]

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"item {i['id']}: {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"

    options = [lab(i) for i in items] + [NONE]
    rows = []
    for x in st['qs']:
        r = model.system_one({'message': x['q'], 'today': st['today']},
                             {'target': Choice('Which itinerary item is the customer message about?', options)})
        a = r['answers']['target']
        if raw_first is None:
            raw_first = json.dumps(a, ensure_ascii=False)[:600]
            print('첫 응답 구조:', raw_first, flush=True)
        probs = a.get('probabilities')
        if isinstance(probs, dict):
            vec = [float(probs.get(o, 0.0)) for o in options]
        else:
            vec = [float(v) for v in probs]
        rows.append(vec)
        n += 1
        if probe and n >= 3:
            break
    res[sname] = {'ids': ids, 'probs': rows}
    if probe:
        break
res['_sec_per_q'] = (time.time() - t0) / max(n, 1)
res['_n'] = n
tag = name.split('/')[-1] + ('_probe' if probe else '')
json.dump(res, open(f'od_out_{tag}.json', 'w'), ensure_ascii=False)
print(name, f"{res['_sec_per_q']:.2f}s/q n={n}", flush=True)
