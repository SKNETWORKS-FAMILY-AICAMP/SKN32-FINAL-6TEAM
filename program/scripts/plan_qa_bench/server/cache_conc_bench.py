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


def ask(text):
    b = {'model': MODEL, 'stream': False, 'format': S, 'options': {'temperature': 0}, 'think': False, 'messages': [{'role': 'user', 'content': text}]}
    r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
    d = json.loads(urllib.request.urlopen(r, timeout=900).read())
    return d.get('prompt_eval_count'), d.get('prompt_eval_duration'), d.get('eval_duration')


def run(texts, workers):
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(ask, texts))
    el = time.time() - t0
    pe = [r[0] for r in res if r[0] is not None]
    return {'n': len(texts), 'workers': workers, 'sec_per_q': el / len(texts), 'q_per_hour': 3600 * len(texts) / el, 'avg_prompt_tokens_evaluated': sum(pe) / max(1, len(pe))}


same = [prompt(jobs['mix12'], q) for q in jobs['mix12']['qs'][:N]]
mixed = [prompt(jobs[sets[i % 5]], jobs[sets[i % 5]]['qs'][i // 5]) for i in range(N)]
for t in same[:2] + mixed[:2]:
    ask(t)      # 모델 올리기·예열
out = {'model': MODEL, 'A_same_itinerary_sequential': run(same, 1), 'B_changing_itinerary_sequential': run(mixed, 1)}
print(json.dumps(out, ensure_ascii=False), flush=True)
out['C_concurrency'] = {}
for w in (2, 4, 8):
    out['C_concurrency'][w] = run(mixed, w)
    print('동시', w, json.dumps(out['C_concurrency'][w], ensure_ascii=False), flush=True)
json.dump(out, open('cache_conc_bench.json', 'w'), ensure_ascii=False, indent=1)
print('BENCH_DONE', flush=True)
