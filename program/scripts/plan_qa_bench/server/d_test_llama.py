# D 시험(혼합 트래픽 2,735문제 — 일정 질문 · 잡담 · 관광지 질문 · 요청 둘)을 서버 A(RTX 2000 Ada)의 llama.cpp GPU 실행으로 풀어 d_test_ollama.py 와 같은 모양의 결과(jsonl)를 만든다 — 생각 끔 · 온도 0 · 상용 API 없음.
#  프롬프트는 연결 시험이 쓴 것과 같은 파일(all_prompts.json — AI Hub 문장이 들어 있어 git 밖, 작업 폴더에 올려 둔다). 질의문 끝 지시와 형식은 파일에 이미 들어 있다. 일정이 이어지는 문제는 (세트, 문제 번호) 순서로 보내 앞부분 캐시가 맞는다. 이어 돌리기 가능.
# 사용: GGUF=<기반 gguf> [LORA=<어댑터 gguf>] TAG=<이름> PORT=8176 [LLAMA_SERVER=…] [CORES=0-5] python3 d_test_llama.py   → d_test_<TAG>.jsonl
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

GGUF, TAG = os.environ['GGUF'], os.environ['TAG']
LORA = os.environ.get('LORA', '')
CORES = os.environ.get('CORES', '0-5')
PORT = int(os.environ.get('PORT', '8176'))
SRV = os.environ.get('LLAMA_SERVER', '/workspace/deciders/bin/llama-server')
dst = f'd_test_{TAG}.jsonl'
items = sorted(json.load(open(os.environ.get('PROMPTS', 'all_prompts.json'), encoding='utf-8')), key=lambda x: (x['set'], x['qi']))     # PROMPTS=all_prompts_d2.json 이면 새 잡담 보류 세트(D2)
done = set()
if os.path.exists(dst):
    for line in open(dst, encoding='utf-8'):
        done.add(json.loads(line)['i'])
todo = [it for it in items if it['i'] not in done]
print(TAG, '남은 문제', len(todo), '/', len(items), flush=True)
env = dict(os.environ, LD_LIBRARY_PATH=os.path.dirname(SRV) + ':' + os.environ.get('LD_LIBRARY_PATH', ''))
cmd = ['taskset', '-c', CORES, SRV, '-m', GGUF, '-t', '4', '-ngl', '99', '-c', '4096', '-np', '1', '--port', str(PORT), '--host', '127.0.0.1', '--jinja']
if LORA:
    cmd += ['--lora', LORA]
srv = subprocess.Popen(cmd, env=env, stdout=open(f'dtest_server_{TAG}.log', 'w'), stderr=subprocess.STDOUT)
for _ in range(600):
    if srv.poll() is not None:      # [2026-10-07] 서버가 모델을 못 올리고 죽었으면 30분 기다리지 않고 바로 끝낸다(qwen3.5 GGUF 로 GPU 를 30분 놀린 일)
        print(TAG, '서버가 시작하지 못했다 — dtest_server 로그 확인', flush=True)
        sys.exit(2)
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3)
        break
    except Exception:  # noqa: BLE001
        time.sleep(3)
f = open(dst, 'a', encoding='utf-8')
t0 = time.time()
try:
    for k, it in enumerate(todo):
        body = {'messages': [{'role': 'user', 'content': it['prompt']}], 'max_tokens': 16, 'temperature': 0, 'cache_prompt': True, 'chat_template_kwargs': {'enable_thinking': False}}
        if os.environ.get('LOGPROBS') == '1':     # [2026-10-07] 답 자리 토큰의 「없음」 대 숫자 확률을 같이 남긴다 — 「없음」 확률 문턱 · 거부권 결합을 오프라인으로 계산하려고
            body['logprobs'] = True
            body['top_logprobs'] = 20
        t1 = time.perf_counter()
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            r = json.loads(urllib.request.urlopen(req, timeout=900).read())
            txt = (r['choices'][0]['message'].get('content') or '')
            mm = re.search(r'"item"\s*:\s*(null|\d+)', txt)
            rec = {'i': it['i'], 'set': it['set'], 'qi': it['qi'], 'type': it['type'], 'gold': it['gold'], 'content': txt[:60], 'parsed': bool(mm),
                   'pick': None if (not mm or mm.group(1) == 'null') else int(mm.group(1)), 'ms': round((time.perf_counter() - t1) * 1000)}
            if os.environ.get('LOGPROBS') == '1':
                import math
                lp = (r['choices'][0].get('logprobs') or {}).get('content') or []
                for tk in lp:
                    t = tk['token'].strip()
                    if t == 'null' or t.isdigit():              # 값 자리의 첫 토큰
                        alts = tk.get('top_logprobs') or []
                        pn = sum(math.exp(a['logprob']) for a in alts if a['token'].strip() == 'null')
                        pi = sum(math.exp(a['logprob']) for a in alts if a['token'].strip().isdigit())
                        rec['p_null'] = round(pn / (pn + pi), 6) if (pn + pi) > 0 else None
                        rec['p_mass'] = round(pn + pi, 4)
                        break
        except Exception as e:  # noqa: BLE001
            rec = {'i': it['i'], 'set': it['set'], 'qi': it['qi'], 'type': it['type'], 'gold': it['gold'], 'error': repr(e)[:100]}
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()
        if (k + 1) % 500 == 0:
            print(TAG, k + 1, '/', len(todo), round(time.time() - t0), '초', flush=True)
finally:
    srv.terminate()
print('끝', TAG, round(time.time() - t0), '초', flush=True)
