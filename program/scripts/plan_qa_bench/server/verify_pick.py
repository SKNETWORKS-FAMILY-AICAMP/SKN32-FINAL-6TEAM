# 서버에서: 모델이 고른 항목을 같은 질의문 맥락에서 한 번 더 「이 항목이 질문이 가리키는 것이 맞나」로 확인(IsRel 식 비평)하고 답 토큰 확률 p_true 를 저장한다.
#  입력: <세트>.json(일정·문제) + llm_<세트>_out.json 의 <PICKER> 키 picks. 항목을 고르지 않은(null) 문제는 건너뛴다.
#  출력: verify_<세트>_<확인 모델>.json = {'p': {문제번호: p_true}} — 항목 번호는 짚기와 같다.
# 사용: SETS=heavy,mix4,mix5,mix6,mix7 PICKER=gemma4:e4b-it-qat python3 verify_pick.py <확인 모델>
import json, math, os, sys, time, urllib.request
from datetime import date

verifier = sys.argv[1]
picker = os.environ.get('PICKER', 'gemma4:e4b-it-qat')
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'matches': {'type': 'boolean'}}, 'required': ['matches']}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{}'}, 'error': str(e)[:200]}
            time.sleep(3)


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
    out, t0 = {}, time.time()
    for qi, x in enumerate(job['qs']):
        p = picks[qi]
        if p is None or p not in byid:
            continue
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}고객 질문: {x['q']}\n\n"
                f"한 모델이 이 질문이 가리키는 항목으로 다음을 골랐다: {lab(byid[p])}\n\n"
                "이 항목이 정말 고객 질문이 가리키는 항목입니까? 질문이 일정의 다른 항목을 가리키거나 이 일정에 없는 것을 묻거나 일정과 무관하면 false, 이 항목이 맞으면 true. JSON {\"matches\": true|false}")
        r = post({'model': verifier, 'stream': False, 'format': S, 'think': False, 'options': {'temperature': 0}, 'logprobs': True, 'top_logprobs': 2, 'messages': [{'role': 'user', 'content': text}]})
        try:
            v = bool(json.loads(r['message']['content']).get('matches'))
        except Exception:  # noqa: BLE001
            continue
        pt = None
        for t in (r.get('logprobs') or []):
            piece = t.get('token', '').strip().lower()
            if piece in ('true', 'false'):
                q = math.exp(t.get('logprob', 0.0))
                pt = q if piece == 'true' else 1 - q
                break
        out[str(qi)] = pt if pt is not None else (1.0 if v else 0.0)
    tag = verifier.replace(':', '_').replace('/', '_')
    json.dump({'p': out, 'picker': picker, '_sec': time.time() - t0}, open(f'verify_{name}_{tag}.json', 'w'))
    print(name, verifier, len(out), '개 확인', f'{time.time() - t0:.0f}s', flush=True)
