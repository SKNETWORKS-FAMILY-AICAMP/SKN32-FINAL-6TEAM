# mix12 의 대상 절(tt)·제외 절(excl) 항목별 점수용 쌍(pairs_mix12.json) + 과제(tasks_mix12.json).
import json, os
from datetime import date
from clauses import analyze
HERE = os.path.dirname(os.path.abspath(__file__))
W = '월화수목금토일'
st = json.load(open(os.path.join(HERE, 'fixtures', 'mix12.json'), encoding='utf-8'))['sets']['mix12']
items = sorted(st['items'], key=lambda i: (i['date'], i['start']))


def doc(i):
    d = date.fromisoformat(i['date'])
    return f"{d.month}월 {d.day}일({W[d.weekday()]}) {i['start']} {i['title']} — 장소 {i['place']} — 종류 {i['kind']}"


pairs, tasks = [], []
for kind in ('tt', 'excl'):
    for qi, x in enumerate(st['qs']):
        a = analyze(x['q'])
        text = a['tt'] if kind == 'tt' else a['excl']
        if text is None:
            continue
        for it in items:
            pairs.append({'set': f'mix12_{kind}', 'qi': qi, 'item': it['id'], 'q': text, 'doc': doc(it)})
for x in st['qs']:
    a = analyze(x['q'])
    tasks.append({'full': x['q'], 'tt': a['tt'], 'excl': a['excl'], 'history': x.get('history') or []})
json.dump(pairs, open(os.path.join(HERE, 'fixtures', 'pairs_mix12.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump({'today': st['today'], 'items': st['items'], 'qs': tasks}, open(os.path.join(HERE, 'fixtures', 'tasks_mix12.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('mix12 쌍', len(pairs), '· 과제', len(tasks))
