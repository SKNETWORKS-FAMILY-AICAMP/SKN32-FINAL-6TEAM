# [둘 다 찾기(C) 판] 서버에서: 답을 번호 배열(items)로 받는다 — 항목이 하나면 하나, 말한 항목이 여럿이면 전부, 없으면 빈 배열. 결과 키 = 모델#multi, 파일 llm_<JOB>_multi_out.json
# (원본 설명) 무거운 세트(heavy.json)를 Gemma 계열로 푼다. llm_point2.py 와 같은 질의문에 「앞 대화」를 더한다.
#  --nohist : 앞 대화를 빼고 푼다(앞 대화가 얼마나 필요한지 재는 용도)
#  --pool   : 문제마다 규칙(날짜·시간대 등)으로 좁힌 후보 id(pool 필드)만 일정에 보여 준다(후보 줄이기)
#  --proto  : 위 정의를 질의문에 덧붙인다(모든 모델에 같은 문장)
# 사용: python3 llm_point_heavy.py [--nohist] [--pool] [--proto] 모델...   → llm_heavy_out.json (키: 모델#옵션 → 문제별 답 배열)
import json, os, sys, time, urllib.request
from datetime import date

args = sys.argv[1:]
nohist, usepool = '--nohist' in args, '--pool' in args
PROTO = '--proto' in args   # 문제 정의(먼저 말한 항목이 정답·지시어는 앞 대화로 품)를 질의문에 명시
RULE = '한 문장에 항목이 여럿 나오면 가장 먼저 언급된 항목 하나만 고른다. 「그거·거기·방금 바꾼 것」 같은 말은 앞 대화에서 가리키는 항목으로 푼다. 앞 대화가 없어 대상을 알 수 없으면 null 이다.'
models = [a for a in args if not a.startswith('--')]
JOB = os.environ.get('JOB', 'heavy')     # 세트 이름(heavy·mix4 …): <JOB>.json 을 읽고 llm_<JOB>_out.json 에 쓴다
job = json.load(open(f'{JOB}.json', encoding='utf-8'))['sets'][JOB]
OUTF = f'llm_{JOB}_multi_out.json'
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'integer'}}}, 'required': ['items']}
items_all = sorted(job['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items_all})
ids_all = {i['id'] for i in items_all}


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


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
    for x in job['qs']:
        pool = set(x.get('pool') or ids_all) if usepool else ids_all
        plan = '\n'.join(lab(i) for i in items_all if i['id'] in pool)
        hist = ''
        if x.get('history') and not nohist:
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
                f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호를 items 배열에 모두 넣어라. 항목이 하나면 하나만, 질문이 여러 항목을 말하면 말한 순서대로 전부 넣는다. "
                "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 빈 배열. 확실하지 않으면 빈 배열." + (' ' + RULE if PROTO else ''))
        b = {'model': model, 'stream': False, 'format': S, 'options': {'temperature': 0}, 'think': False,
             'messages': [{'role': 'user', 'content': text}]}
        r = post(b)
        errors += 'error' in r
        try:
            v = json.loads(r['message']['content']).get('items')
        except Exception:  # noqa: BLE001
            v = None
        picks.append([i for i in v if i in ids_all] if isinstance(v, list) else [])
    key = model + '#multi' + ('#nohist' if nohist else '') + ('#pool' if usepool else '') + ('#proto' if PROTO else '')
    out[key] = {'picks': picks, '_sec_per_q': (time.time() - t0) / len(job['qs']), '_errors': errors}
    tmp = OUTF + '.tmp'
    json.dump(out, open(tmp, 'w'), ensure_ascii=False)
    os.replace(tmp, OUTF)
    print(key, f"{out[key]['_sec_per_q']:.2f}s/q errors={errors}", flush=True)
