import json, sys, time, random
from datetime import date
SP = sys.argv[1]
MODEL = sys.argv[2] if len(sys.argv) > 2 else 'gemma4:12b'
sys.path.insert(0, SP)
from recog_v2 import RecognizerV3, emb, post
cats = json.load(open(SP + '/kakao_cats.json', encoding='utf-8'))
cx = json.load(open(SP + '/codex_qset.json', encoding='utf-8'))
q2 = json.load(open(SP + '/codex_qset2.json', encoding='utf-8'))['questions']
items = sorted(cx['itinerary'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})
W = '월화수목금토일'


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
IDS = {i['id'] for i in items}


def ask(q, order):
    plan = '\n'.join(f"{i['id']}. {lab(i)}" for i in order)
    b = {'model': MODEL, 'stream': False, 'think': False, 'format': S, 'options': {'temperature': 0},
         'messages': [{'role': 'user', 'content':
                       f"오늘은 {cx['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n"
                       f"고객 질문: {q}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                       "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null."}]}
    v = json.loads(post('/api/chat', b)['message']['content']).get('item')
    return v if v in IDS else None


def consistent(q, pick):
    # 질문에 날짜·시간대·시각·종류가 적혀 있으면 고른 항목이 그 조건 안에 있어야 한다(순서 질문은 기준 항목이 달라 건너뛴다)
    import re as _re
    from recog_v2 import NEXT, PREV
    if pick is None or _re.search(NEXT, q, _re.I) or _re.search(PREV, q, _re.I):
        return True
    pool, sig = R.filt(q)
    return (not sig) or pick in {i['id'] for i in pool}


rng = random.Random(7)
shuffled = items[:]
rng.shuffle(shuffled)
R = RecognizerV3(cx['itinerary'], cats, date.fromisoformat(cx['today']), SP + '/alias_cache.json')
for name, QS in (('새 질문 40', q2), ('시험용 50', [x for n, x in enumerate(cx['questions']) if n % 2 == 1])):
    QV = emb([x['q'] for x in QS])
    t0 = time.time()
    a = [ask(x['q'], items) for x in QS]
    b = [ask(x['q'], shuffled) for x in QS]
    dt = (time.time() - t0) / (2 * len(QS))
    v3 = [R.pick(x['q'], qv, 0.55) for x, qv in zip(QS, QV)]
    top3 = [[c for _, c in R.rank(x['q'], qv)[0][:3]] for x, qv in zip(QS, QV)]
    variants = {
        'LLM 번호 짚기(1회)': a,
        'LLM 두 번(순서 바꿔) 같을 때만': [x if x == y else None for x, y in zip(a, b)],
        'LLM 두 번 + v3 후보3 안에 있을 때만': [x if (x == y and x in t) else None for x, y, t in zip(a, b, top3)],
        'v3(τ 0.55, 비교용)': v3,
        'LLM 두 번 + 규칙 되확인(날짜·시간대·종류)': [x if (x == y and consistent(x_q['q'], x)) else None for x, y, x_q in zip(a, b, QS)],
        'LLM 1회 + 규칙 되확인': [x if consistent(x_q['q'], x) else None for x, x_q in zip(a, QS)],
    }
    json.dump({'a': a, 'b': b}, open(SP + f'/llm_out_{name[:2]}.json', 'w'), ensure_ascii=False)
    nn = sum(x['gold'] is None for x in QS)
    for k, out in variants.items():
        ok = sum(o == x['gold'] for o, x in zip(out, QS))
        wrong = sum(o is not None and x['gold'] is not None and o != x['gold'] for o, x in zip(out, QS))
        fp = sum(o is not None and x['gold'] is None for o, x in zip(out, QS))
        miss = sum(o is None and x['gold'] is not None for o, x in zip(out, QS))
        print(f"[{name}] {MODEL} {k}: 맞음 {ok}/{len(QS)}={ok / len(QS):.0%} · 틀린 항목 {wrong} · 없는 질문 오짚음 {fp}/{nn} · 못 찾음 {miss}")
    print(f"   호출당 {dt:.1f}s")
    if name == '새 질문 40':
        for x, o, p in zip(QS, a, b):
            if o != x['gold']:
                print(f"    X {x['type']:<20} 정답 {x['gold']} · LLM {o}/{p} · {x['q']}")
