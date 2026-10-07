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


GPU = os.environ.get('GPU') == '1'   # [2026-10-07] 1 이면 GPU 에 전부 올려(-ngl 99) 서버 A 의 GPU 로 잰다(기본은 CPU 전용)
LORA = os.environ.get('LORA', '')      # 어댑터 GGUF 경로(있으면 --lora) — 기반 GGUF 와 따로 올린다
env = dict(os.environ, LD_LIBRARY_PATH=os.path.dirname(SRV) + ':' + os.environ.get('LD_LIBRARY_PATH', ''))
if not GPU:
    env['CUDA_VISIBLE_DEVICES'] = ''
cmd = ['taskset', '-c', CORES, SRV, '-m', GGUF, '-t', '4', '-ngl', '99' if GPU else '0', '-c', '4096', '-np', '1', '--port', str(PORT), '--host', '127.0.0.1', '--jinja']
if LORA:
    cmd += ['--lora', LORA]
srv = subprocess.Popen(cmd, env=env, stdout=open(f'cpu_server_{TAG}.log', 'w'), stderr=subprocess.STDOUT)
t0 = time.time()
for _ in range(600):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3)
        break
    except Exception:  # noqa: BLE001
        time.sleep(3)
print('서버 준비', f'{time.time() - t0:.0f}초', flush=True)


def ask(prompt):
    body = {'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 16, 'temperature': 0, 'cache_prompt': True}
    if os.environ.get('NOTHINK') == '1':      # [2026-10-07 §92-11] Gemma-4 생각 모드가 켜져 있으면 작은 max_tokens 에서 content 가 비어 나온다 — 끈다
        body['chat_template_kwargs'] = {'enable_thinking': False}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=1800))


try:
    for s in SETS.split(','):
        job = json.load(open(f'{s}.json', encoding='utf-8'))['sets'][s]
        qs = job['qs'][:LIMIT] if LIMIT else job['qs']
        picks, rows, errs, ok = [], [], 0, 0
        for n, x in enumerate(qs):
            prompt, valid = build(job, x)
            t1 = time.time()
            r = ask(prompt)
            wall = time.time() - t1
            txt = r['choices'][0]['message']['content'] or ''
            m = re.search(r'"item"\s*:\s*(null|\d+)', txt)
            if m:
                v = None if m.group(1) == 'null' else int(m.group(1))
                v = v if v in valid else None
            else:
                v, errs = None, errs + 1
            picks.append(v)
            tm = r.get('timings', {})
            rows.append({'wall_s': round(wall, 2), 'prompt_n': tm.get('prompt_n'), 'cache_n': tm.get('cache_n'), 'prompt_ms': tm.get('prompt_ms'),
                         'predicted_n': tm.get('predicted_n'), 'predicted_ms': tm.get('predicted_ms'), 'raw': txt[:40]})
            ok += (v == x['gold'])
            if n < 3 or (n + 1) % 20 == 0:
                print(f'{s} {n + 1}/{len(qs)} 맞음 {ok} · 이번 {wall:.1f}초 (새로 읽은 {tm.get("prompt_n")} · 캐시 {tm.get("cache_n")} 토큰)', flush=True)
        warm = [r['wall_s'] for r in rows[1:]]
        res = {'picks': picks, 'rows': rows, '_errors': errs, '_cold_s': rows[0]['wall_s'], '_warm_mean_s': round(sum(warm) / max(1, len(warm)), 2), '_tag': TAG, '_cores': CORES,
               '_correct': ok, '_n': len(qs)}
        json.dump(res, open(f'cpu_eval_{TAG}_{s}{"_smoke" if LIMIT else ""}.json', 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'{TAG} {s}: 맞음 {ok}/{len(qs)} · 읽기실패 {errs} · 첫 질문 {res["_cold_s"]}초 · 다음 질문 평균 {res["_warm_mean_s"]}초', flush=True)
finally:
    srv.terminate()
print('CPU_EVAL_DONE', TAG, flush=True)
