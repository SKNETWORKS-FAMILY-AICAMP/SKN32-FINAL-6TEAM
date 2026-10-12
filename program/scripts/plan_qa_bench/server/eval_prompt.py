# 서버에서: 프롬프트 틀 하나로 작은 모델의 「항목 짚기」 정확도를 잰다(GEPA식 프롬프트 최적화의 평가 단계).
#  틀 파일(JSON): {"template": "... {today} {plan} {hist} {q} ..."} — 자리표만 채우고 다른 값은 만들지 않는다.
#  세트: old(기존 178: mine38·dev50·test50·hard40 — 프롬프트 최적화용) · heavy(held 88) · mix4(88)
# 사용: python3 eval_prompt.py <모델> <틀.json> <세트: old_train|old_val|heavy|mix4> [--fails N]   → JSON 한 줄(정확도·틀린 문제 목록)
import json, os, random, sys, time, urllib.request
from datetime import date

model, tpl_file, which = sys.argv[1:4]
nfail = int(sys.argv[sys.argv.index('--fails') + 1]) if '--fails' in sys.argv else 12
DUMP = sys.argv[sys.argv.index('--dump') + 1] if '--dump' in sys.argv else None      # 세트의 모든 문제에 대한 답을 저장(종단 채점용)
tpl = json.load(open(tpl_file, encoding='utf-8'))['template']
W = '월화수목금토일'
ITEM = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}


def load_set():
    if which.startswith('old'):
        job = json.load(open('job_old.json', encoding='utf-8'))['sets']
        rows = [(st, x) for st in job.values() for x in st['qs']]
        rnd = random.Random(7)
        rnd.shuffle(rows)
        cut = int(len(rows) * 0.66)
        rows = rows[:cut] if which == 'old_train' else rows[cut:]
        return [(st, x) for st, x in rows]
    job = json.load(open(f'{which}.json', encoding='utf-8'))['sets'][which]
    return [(job, x) for x in job['qs'] if which != 'heavy' or x.get('split') == 'held' or DUMP]


def plan_of(st):
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    lines = []
    for i in items:
        d = date.fromisoformat(i['date'])
        lines.append(f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}")
    return '\n'.join(lines), {i['id'] for i in items}


def ask(text):
    b = {'model': model, 'stream': False, 'format': ITEM, 'think': False, 'options': {'temperature': 0}, 'messages': [{'role': 'user', 'content': text}]}
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(json.loads(urllib.request.urlopen(r, timeout=600).read())['message']['content']).get('item'), False
        except Exception:  # noqa: BLE001
            time.sleep(3)
    return None, True


rows = load_set()
ok = bad = miss = errs = 0
fails = []
preds_all = []
t0 = time.time()
for st, x in rows:
    plan, ids = plan_of(st)
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    text = tpl.replace('{today}', st['today']).replace('{plan}', plan).replace('{hist}', hist).replace('{q}', x['q'])   # format() 은 프롬프트 속 {"item"} 중괄호에서 오류가 나서 치환으로 바꿈
    pred, e = ask(text)
    errs += e
    pred = pred if pred in ids else None
    preds_all.append(pred)
    g = x['gold']
    ok += (pred == g)
    bad += (pred is not None and pred != g)
    miss += (pred is None and g is not None)
    if pred != g:
        fails.append({'q': x['q'], 'gold': g, 'pred': pred, 'type': x.get('type')})
random.Random(3).shuffle(fails)
if DUMP:
    json.dump({'picks': preds_all}, open(DUMP, 'w'))
print(json.dumps({'n': len(rows), 'ok': ok, 'bad': bad, 'miss': miss, 'errors': errs, 'acc': ok / len(rows), 'sec': time.time() - t0, 'fails': fails[:nfail]}, ensure_ascii=False))
