# 서버에서: Jev 의 「선택지별 확률」을 작은 LLM 으로 대신한다 — 앞단 상위 K개 후보마다 같은 모델이 「이 항목이 질문이 가리키는 것이 맞나」를 답하고 true 토큰 확률 p_true 를 저장한다.
#  입력: <세트>.json + topk_<세트>.json({문제번호: [후보 항목 번호…]}, 없으면 pairs_<세트>.json·ft_e16d_<세트>_scores.json 으로 상위 K개를 직접 만든다).
#  질의문은 verify_pick.py 와 같다(비평과 확률 눈금을 맞추려고). 출력: judge_<세트>_<모델>.json = {'p': {문제번호: {항목번호: p_true}}}
# 사용: SETS=mix8,mix7 K=5 python3 judge_topk.py <모델>
import json, math, os, sys, time, urllib.request
from datetime import date

model = sys.argv[1]
K = int(os.environ.get('K', '5'))
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
    if os.path.exists(f'topk_{name}.json'):
        topk = json.load(open(f'topk_{name}.json', encoding='utf-8'))
    else:
        pairs = json.load(open(f'pairs_{name}.json', encoding='utf-8'))
        sc = json.load(open(f'ft_e16d_{name}_scores.json'))['ft/emb_e16d']
        by = {}
        for p, v in zip(pairs, sc):
            if p['set'] == f'{name}_tt':
                by.setdefault(p['qi'], {})[p['item']] = v
        topk = {str(qi): sorted(d, key=d.get, reverse=True)[:K] for qi, d in by.items()}
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    byid = {i['id']: i for i in items}

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    plan = '\n'.join(lab(i) for i in items)
    out, t0, n = {}, time.time(), 0
    for qi, x in enumerate(job['qs']):
        cands = topk.get(str(qi))
        if not cands:
            continue
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        row = {}
        for c in cands[:K]:
            text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}고객 질문: {x['q']}\n\n"
                    f"한 모델이 이 질문이 가리키는 항목으로 다음을 골랐다: {lab(byid[c])}\n\n"
                    "이 항목이 정말 고객 질문이 가리키는 항목입니까? 질문이 일정의 다른 항목을 가리키거나 이 일정에 없는 것을 묻거나 일정과 무관하면 false, 이 항목이 맞으면 true. JSON {\"matches\": true|false}")
            r = post({'model': model, 'stream': False, 'format': S, 'think': False, 'options': {'temperature': 0}, 'logprobs': True, 'top_logprobs': 2, 'messages': [{'role': 'user', 'content': text}]})
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
            row[str(c)] = pt if pt is not None else (1.0 if v else 0.0)
            n += 1
        out[str(qi)] = row
    tag = model.replace(':', '_').replace('/', '_')
    json.dump({'p': out, 'K': K, '_sec': time.time() - t0}, open(f'judge_{name}_{tag}.json', 'w'))
    print(name, model, len(out), '문제', n, '호출', f'{time.time() - t0:.0f}s', flush=True)
