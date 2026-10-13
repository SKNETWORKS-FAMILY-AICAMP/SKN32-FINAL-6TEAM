# 서버에서: 작은 모델 전문가 호출 — gate2(일정 관련 여부) · anchor(기준 항목) · point(대상 절이 가리키는 항목) · verify(짚은 항목이 문장과 정말 맞는지)를 모델마다 돌린다.
# 값은 만들지 않고 번호·true/false 만 받는다. 이미 있는 anchor/point 는 재사용하고 --redo 로 지정한 모델은 전부 다시 잰다.
# 사용: python3 llm_tasks.py <job 이름> [--redo 모델,...] 모델...   → llm_tasks_out_<job>.json
import json, os, sys, time, urllib.request
from datetime import date

args = sys.argv[1:]
redo = set()
if '--redo' in args:
    k = args.index('--redo')
    redo = set(args[k + 1].split(','))
    del args[k:k + 2]
job = args[0]
models = args[1:]
T = json.load(open(f'tasks_{job}.json', encoding='utf-8'))
items = sorted(T['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})
ids = {i['id'] for i in items}
W = '월화수목금토일'


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


plan = '\n'.join(lab(i) for i in items)
ITEM = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
GATE = {'type': 'object', 'properties': {'in_scope': {'type': 'boolean'}}, 'required': ['in_scope']}
VERIFY = {'type': 'object', 'properties': {'same': {'type': 'boolean'}}, 'required': ['same']}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{}'}, 'error': str(e)[:200]}
            time.sleep(5)


def ask(model, fmt, text):
    r = post({'model': model, 'stream': False, 'format': fmt, 'think': False, 'options': {'temperature': 0}, 'messages': [{'role': 'user', 'content': text}]})
    try:
        return json.loads(r['message']['content']), 'error' in r
    except Exception:  # noqa: BLE001
        return {}, True


def hist(h):
    if not h:
        return ''
    return '앞 대화:\n' + '\n'.join(f"{'고객' if t['role'] == 'customer' else '서비스'}: {t['text']}" for t in h) + '\n\n'


head = f"오늘은 {T['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n"
GATE_Q = ("\n\n이 메시지가 위 여행 일정의 특정 항목(장소·식당·숙소·이동·시각·순서)에 대해 묻거나 확인하거나 바꾸려는 것이면 in_scope=true. "
          "인사·감사·잡담, 일반 정보(요금·시세·날씨·환율·규정), 일반 추천 요청, 코드·번역이면 false. 일정에 없는 장소를 짚어 묻는 것은 true.")
ANCHOR_Q = "\n\n이 글에 이름이나 설명으로 언급된 일정 항목 번호 하나를 item 에 넣어라. 언급된 항목이 없으면 null."
POINT_Q = ("\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
           "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
VERIFY_Q = ("\n\n이 메시지가 후보 항목 자체(같은 장소·식당·활동·숙소·이동)에 대해 묻거나 바꾸려는 것이면 same=true. "
            "단어만 비슷할 뿐 다른 장소이거나(예: 유람선과 피크닉), 요금·시세·추천 같은 일반 정보를 묻는 것이면 false. 앞 대화가 있으면 반영하라.")

out = json.load(open(f'llm_tasks_out_{job}.json')) if os.path.exists(f'llm_tasks_out_{job}.json') else {}
for model in models:
    prev = {} if model in redo else out.get(model, {})
    res = {'gate2': [], 'anchor_tt': [], 'anchor_excl': [], 'point': [], 'verify': [], 'errors': 0}
    for k in ('anchor_tt', 'anchor_excl', 'point'):
        if len(prev.get(k, [])) == len(T['qs']):
            res[k] = prev[k]
    t0 = time.time()
    for n, q in enumerate(T['qs']):
        h = hist(q['history'])
        v, e = ask(model, GATE, head + h + f"고객 메시지: {q['full']}" + GATE_Q)
        res['gate2'].append(bool(v.get('in_scope', True)))
        res['errors'] += e
        if len(res['anchor_tt']) <= n:
            for key, txt in (('anchor_tt', q['tt']), ('anchor_excl', q['excl'])):
                if txt is None:
                    res[key].append(None)
                    continue
                v, e = ask(model, ITEM, head + f"글: {txt}" + ANCHOR_Q)
                x = v.get('item')
                res[key].append(x if x in ids else None)
                res['errors'] += e
        if len(res['point']) <= n:
            v, e = ask(model, ITEM, head + h + f"고객 질문: {q['tt']}" + POINT_Q)
            x = v.get('item')
            res['point'].append(x if x in ids else None)
            res['errors'] += e
        pid = res['point'][n]
        if pid is None:
            res['verify'].append(None)
        else:
            it = next(i for i in items if i['id'] == pid)
            v, e = ask(model, VERIFY, h + f"고객 메시지: {q['tt']}\n후보 항목: {it['title']} @ {it['place']} ({it['start']})" + VERIFY_Q)
            res['verify'].append(bool(v.get('same', True)))
            res['errors'] += e
    res['sec_per_q'] = (time.time() - t0) / len(T['qs'])
    out[model] = res
    tmp = f'llm_tasks_out_{job}.json.tmp'
    json.dump(out, open(tmp, 'w'), ensure_ascii=False)
    os.replace(tmp, f'llm_tasks_out_{job}.json')
    print(model, f"{res['sec_per_q']:.2f}s/q errors={res['errors']}", flush=True)
