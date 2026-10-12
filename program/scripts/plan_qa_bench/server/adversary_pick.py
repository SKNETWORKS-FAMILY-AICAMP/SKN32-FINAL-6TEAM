# 서버에서: 적대적 검토(반론 담당) — 짚은 항목에 대해 같은 질의 안에서 「틀렸다고 보고 다른 항목을 대 보라」고 시키고, 다른 항목이 나오면 A·B 대결(순서를 바꿔 두 번)로 가린다.
#  단계 1 반론: {"alternative": 번호|null}  — 짚은 항목과 다른 번호가 나오면 도전으로 본다.
#  단계 2 대결: 짚은 항목과 도전 항목을 A·B 로 보여 주고 {"winner": "A"|"B"|"neither"} — 위치 편향을 줄이려 A·B 를 바꿔 두 번 묻는다.
#  입력: <세트>.json + llm_<세트>_out.json 의 <PICKER> 키 picks(항목을 짚은 문제만). 출력: adv_<세트>_<반론 모델>.json = {qi: {"pick":…, "alt":…, "duel": ["pick"|"alt"|"neither", 두 번째]}}
# 사용: SETS=mix8,mix9 PICKER=gemma4:e4b-it-qat python3 adversary_pick.py <반론 모델>
import json, os, sys, time, urllib.request
from datetime import date

adv = sys.argv[1]
picker = os.environ.get('PICKER', 'gemma4:e4b-it-qat')
W = '월화수목금토일'
SA = {'type': 'object', 'properties': {'alternative': {'type': ['integer', 'null']}}, 'required': ['alternative']}
SD = {'type': 'object', 'properties': {'winner': {'type': 'string', 'enum': ['A', 'B', 'neither']}}, 'required': ['winner']}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{}'}, 'error': str(e)[:200]}
            time.sleep(3)


def ask(schema, text):
    r = post({'model': adv, 'stream': False, 'format': schema, 'think': False, 'options': {'temperature': 0}, 'messages': [{'role': 'user', 'content': text}]})
    try:
        return json.loads(r['message']['content'])
    except Exception:  # noqa: BLE001
        return {}


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'{name}.json', encoding='utf-8'))['sets'][name]
    picks = json.load(open(f'llm_{name}_out.json'))[picker]['picks']
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    byid = {i['id']: i for i in items}

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    plan = '\n'.join(lab(i) for i in items)
    out, t0, n1, n2 = {}, time.time(), 0, 0
    for qi, x in enumerate(job['qs']):
        p = picks[qi]
        if p is None or p not in byid:
            continue
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        base = f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}고객 질문: {x['q']}\n\n"
        a = ask(SA, base + f"한 모델이 이 질문이 가리키는 항목으로 다음을 골랐다: {lab(byid[p])}\n\n당신은 반론 담당이다. 이 선택이 틀렸다고 보고, 질문이 오히려 가리키는 다른 항목이 일정에 있으면 그 번호를 alternative 에 넣어라. 이 선택이 맞거나 더 나은 다른 항목이 없으면 null.")
        n1 += 1
        alt = a.get('alternative')
        row = {'pick': p, 'alt': alt if (alt in byid and alt != p) else None, 'duel': None}
        if row['alt'] is not None:
            res = []
            for first, second in ((p, row['alt']), (row['alt'], p)):
                d = ask(SD, base + f"두 모델이 이 질문이 가리키는 항목으로 서로 다른 것을 골랐다.\nA: {lab(byid[first])}\nB: {lab(byid[second])}\n\n질문이 가리키는 항목은 어느 쪽인가? A, B, 둘 다 아니면 neither 를 winner 에 넣어라.")
                n2 += 1
                w_ = d.get('winner')
                res.append('neither' if w_ not in ('A', 'B') else (('pick' if first == p else 'alt') if w_ == 'A' else ('pick' if second == p else 'alt')))
            row['duel'] = res
        out[str(qi)] = row
    tag = adv.replace(':', '_').replace('/', '_')
    json.dump({'rows': out, 'picker': picker, '_sec': time.time() - t0}, open(f'adv_{name}_{tag}.json', 'w'), ensure_ascii=False)
    print(name, adv, len(out), '문제 · 반론', n1, '· 대결', n2, f'{time.time() - t0:.0f}s', flush=True)
