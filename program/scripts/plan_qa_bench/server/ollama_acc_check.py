# [정확도 확인판] 서버에서: 올라마 모델이 같은 질의문(처리량 시험과 같은 prompt())에서 정답 항목을 맞히는지 세 세트 앞 N문제로 확인한다 — 어댑터가 서버에서 제대로 붙었는지 보는 용도(처리량 시험은 속도만 잰다).
# 서버에서: 올라마 모델의 「앞부분(일정 목록) 캐시」와 「동시 요청」이 처리 속도를 얼마나 바꾸는지 잰다 — 비용 비교에서 API 쪽 캐시 할인과 같은 조건으로 자체 GPU 를 비교하려는 용도.
#  A. 같은 일정 연달아(앞부분 캐시가 맞는 순서) vs B. 일정이 매번 바뀌는 순서(캐시가 안 맞음) — 한 번에 한 건
#  C. B 순서로 동시 요청 1·2·4·8 (올라마가 OLLAMA_NUM_PARALLEL 만큼 병렬로 받아야 효과가 있다)
# 사용: MODEL=gemma4:e4b-it-qat N=40 python3 cache_conc_bench.py   → cache_conc_bench.json (작업 폴더에 mix8~12.json 이 있어야 한다)
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

MODEL, N = os.environ.get('MODEL', 'gemma4:e4b-it-qat'), int(os.environ.get('N', '40'))
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
sets = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
jobs = {s: json.load(open(f'{s}.json', encoding='utf-8'))['sets'][s] for s in sets}


def prompt(job, x):
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    return (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n" + '\n'.join(lab(i) for i in items) + f"\n\n{hist}"
            f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")



def ask_content(text):
    b = {'model': MODEL, 'stream': False, 'format': S, 'options': {'temperature': 0}, 'think': False, 'messages': [{'role': 'user', 'content': text}]}
    r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
    d = json.loads(urllib.request.urlopen(r, timeout=900).read())
    return d['message']['content'], d.get('total_duration', 0) / 1e9


res = {'model': MODEL, 'sets': {}}
tot_ok = tot_n = 0
for s in ('mix10', 'mix11', 'mix12'):
    ok = n = errs = 0
    for q in jobs[s]['qs']:
        if q.get('type') == 'compound_intent':
            continue
        try:
            c, sec = ask_content(prompt(jobs[s], q))
            pick = json.loads(c).get('item')
        except Exception:
            errs += 1
            pick = '__err__'
        n += 1
        ok += pick == q['gold']
    res['sets'][s] = {'n': n, 'ok': ok, 'errors': errs}
    tot_ok += ok
    tot_n += n
    print(s, ok, '/', n, '오류', errs, flush=True)
res['total'] = {'ok': tot_ok, 'n': tot_n}
json.dump(res, open('acc_check.json', 'w'), ensure_ascii=False, indent=1)
print('ACC_DONE', tot_ok, tot_n, flush=True)
