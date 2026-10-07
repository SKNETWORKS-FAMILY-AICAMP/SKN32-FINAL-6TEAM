# 서버 A(RTX 2000 Ada) llama.cpp GPU 실행에서 가르친 E4B(어댑터)의 「같은 일정 연달아 · 일정이 매번 바뀜」 순차 처리량과 동시 요청(슬롯 1·2·4) 처리량을 잰다. 질의문 틀은 cpu_eval_gguf.py 와 같다.
# (이 줄 아래 설명은 cpu_eval_gguf.py 의 것을 이어 쓴 머리말이다)
# 서버에서: GGUF 로 바꾼 「가르친 E4B」를 GPU 없이 CPU 4코어로 llama-server 에 올려 같은 문제를 풀고 정확도와 질문당 시간을 같이 잰다.
#  - 질의문은 qlora_eval.py 의 build() 와 글자 하나까지 같다(학습·평가와 같은 문장 + 형식 한 줄). 대화 틀은 GGUF 에 들어 있는 것을 llama-server 가 적용한다.
#  - 세트마다 일정이 하나라 앞부분이 같다 → 프롬프트 캐시(cache_prompt)로 첫 질문만 일정 전체를 읽고 다음 질문부터는 새 문장만 읽는다(실제 서비스에서 한 여행에 여러 질문을 받는 모양과 같다).
#  - 이 서버 CPU 는 x86 이라 ARM 4코어(Neoverse N1 급)보다 빠르다 → 시간은 「상한(낙관)」이고, 서버가 다른 일을 하는 중이라 흔들릴 수 있다.
# 사용: GGUF=/…/model.gguf CORES=56-59 TAG=e4bt_q8 SETS=mix10,mix11,mix12,mix8,mix9 [LIMIT=6] python3 cpu_eval_gguf.py   → cpu_eval_<TAG>_<세트>.json
import json, os, re, subprocess, sys, time, urllib.request
from datetime import date

GGUF, CORES, TAG, SETS = os.environ['GGUF'], os.environ.get('CORES', '56-59'), os.environ['TAG'], os.environ['SETS']
LIMIT = int(os.environ.get('LIMIT', '0'))
PORT = int(os.environ.get('PORT', '8170'))
SRV = os.environ.get('LLAMA_SERVER', '/workspace/deciders/bin/llama-server')
W = '월화수목금토일'
SFX = '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'


def build(job, x):
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    return (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n" + '\n'.join(lab(i) for i in items) + f"\n\n{hist}"
            f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
            "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null." + SFX), {i['id'] for i in items}



import threading
from concurrent.futures import ThreadPoolExecutor

NP = int(os.environ.get('NP', '4'))
N = int(os.environ.get('N', '60'))
LORA = os.environ.get('LORA', '')
env = dict(os.environ, LD_LIBRARY_PATH=os.path.dirname(SRV) + ':' + os.environ.get('LD_LIBRARY_PATH', ''))
cmd = ['taskset', '-c', CORES, SRV, '-m', GGUF, '-t', '4', '-ngl', '99', '-c', str(4096 * NP), '-np', str(NP), '--port', str(PORT), '--host', '127.0.0.1', '--jinja']
if LORA:
    cmd += ['--lora', LORA]
srv = subprocess.Popen(cmd, env=env, stdout=open(f'conc_server_{TAG}.log', 'w'), stderr=subprocess.STDOUT)
for _ in range(600):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3)
        break
    except Exception:  # noqa: BLE001
        time.sleep(3)


def ask(prompt):
    body = {'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 16, 'temperature': 0, 'cache_prompt': True, 'chat_template_kwargs': {'enable_thinking': False}}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=1800))


def run(prompts, workers):
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(ask, prompts))
    el = time.time() - t0
    return {'n': len(prompts), 'workers': workers, 'sec_per_q': el / len(prompts), 'q_per_hour': 3600 * len(prompts) / el}


try:
    jobs = {s: json.load(open(f'{s}.json', encoding='utf-8'))['sets'][s] for s in ('mix8', 'mix9', 'mix10', 'mix11', 'mix12')}
    order = list(jobs)
    same = [build(jobs['mix12'], x)[0] for x in jobs['mix12']['qs'][:N]]
    mixed = [build(jobs[order[i % 5]], jobs[order[i % 5]]['qs'][i // 5])[0] for i in range(N)]
    for p in same[:2] + mixed[:2]:
        ask(p)
    out = {'tag': TAG, 'np': NP, 'A_same_itinerary_sequential': run(same, 1), 'B_changing_itinerary_sequential': run(mixed, 1), 'C_concurrency': {}}
    print(json.dumps(out, ensure_ascii=False), flush=True)
    for w in (2, 4):
        out['C_concurrency'][w] = run(mixed, w)
        print('동시', w, json.dumps(out['C_concurrency'][w], ensure_ascii=False), flush=True)
    json.dump(out, open(f'conc_bench_{TAG}.json', 'w'), ensure_ascii=False, indent=1)
    print('CONC_DONE', flush=True)
finally:
    srv.terminate()
