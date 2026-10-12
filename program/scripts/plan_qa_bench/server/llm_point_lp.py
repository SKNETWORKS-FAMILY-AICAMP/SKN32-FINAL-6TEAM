# 서버에서: 작은 모델의 직접 짚기에 올라마 로그확률(logprobs)로 「확신도」를 함께 얻는다 — 한 모델 자신의 토큰 확률이며 투표·합의가 아니다.
#  형식은 llm_point_heavy.py 와 같다({"item": 번호|null}). 답 토큰들(숫자 또는 null)의 로그확률 합 = 답 전체의 확률 → conf.
#  사용: JOB=heavy python3 llm_point_lp.py 모델...   → llm_<JOB>_lp_out.json (모델 → {picks, conf, top2})
import json, math, os, sys, time, urllib.request
from datetime import date

JOB = os.environ.get('JOB', 'heavy')
models = sys.argv[1:]
job = json.load(open(f'{JOB}.json', encoding='utf-8'))['sets'][JOB]
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})
ids = {i['id'] for i in items}
plan = '\n'.join(f"{i['id']}. {days.index(i['date']) + 1}일차 {date.fromisoformat(i['date']).month}/{date.fromisoformat(i['date']).day}({W[date.fromisoformat(i['date']).weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}" for i in items)
OUTF = f'llm_{JOB}_lp_out.json'
out = json.load(open(OUTF)) if os.path.exists(OUTF) else {}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=600).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'error': str(e)[:200]}
            time.sleep(3)


for model in models:
    picks, conf, top2, errs = [], [], [], 0
    t0 = time.time()
    for x in job['qs']:
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
                f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
        r = post({'model': model, 'stream': False, 'format': S, 'think': False, 'logprobs': True, 'top_logprobs': 3,
                  'options': {'temperature': 0}, 'messages': [{'role': 'user', 'content': text}]})
        errs += 'error' in r
        try:
            v = json.loads(r['message']['content']).get('item')
        except Exception:  # noqa: BLE001
            v = None
        toks = r.get('logprobs') or []
        # 「item」 값 부분의 토큰만: 콜론 뒤 ~ 닫는 중괄호 앞
        s = ''.join(t.get('token', '') for t in toks)
        k = s.find(':')
        acc, lp = '', 0.0
        for t in toks:
            piece = t.get('token', '')
            if k >= 0 and len(acc) > k and '}' not in piece and piece.strip():
                lp += t.get('logprob', 0.0)
            acc += piece
        picks.append(v if v in ids else None)
        conf.append(math.exp(lp) if toks else None)
        top2.append(None)
    out[model] = {'picks': picks, 'conf': conf, 'errors': errs, 'sec_per_q': (time.time() - t0) / len(job['qs'])}
    json.dump(out, open(OUTF + '.tmp', 'w'), ensure_ascii=False)
    os.replace(OUTF + '.tmp', OUTF)
    print(model, f"{out[model]['sec_per_q']:.2f}s/q errors={errs} conf 있는 문제 {sum(c is not None for c in conf)}/{len(conf)}", flush=True)
