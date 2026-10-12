# 짚기 모델이 고른 항목이 맞는지 「짧은 확인 질문」(고객 말 + 고른 일정 항목 한 줄)으로 검토자 모델에게 묻는다 — YES/NO 한 단어와 YES 확률(첫 토큰 logprob).
#  입력 verify_inputs.json(build_verify_inputs.py) · 출력 verify_<TAG>.jsonl. 일정 전체를 다시 읽히지 않으므로 건당 약 150토큰이다. 이어 돌리기 가능.
# 사용: GGUF=<검토자 gguf> TAG=<이름> PORT=8240 [LLAMA_SERVER=…] [CORES=0-5] python3 verify_llama.py
import json
import math
import os
import subprocess
import sys
import time
import urllib.request

GGUF, TAG = os.environ['GGUF'], os.environ['TAG']
PORT = int(os.environ.get('PORT', '8240'))
SRV = os.environ.get('LLAMA_SERVER', '/workspace/deciders/bin/llama-server')
CORES = os.environ.get('CORES', '0-5')
dst = f'verify_{TAG}.jsonl'
items = json.load(open(os.environ.get('INPUT', 'verify_inputs.json'), encoding='utf-8'))
done = set()
if os.path.exists(dst):
    for line in open(dst, encoding='utf-8'):
        done.add(json.loads(line)['key'])
todo = [x for x in items if x['key'] not in done]
print(TAG, '남은', len(todo), '/', len(items), flush=True)
env = dict(os.environ, LD_LIBRARY_PATH=os.path.dirname(SRV) + ':' + os.environ.get('LD_LIBRARY_PATH', ''))
srv = subprocess.Popen(['taskset', '-c', CORES, SRV, '-m', GGUF, '-t', '4', '-ngl', '99', '-c', '2048', '-np', '1', '--port', str(PORT), '--host', '127.0.0.1', '--jinja'], env=env, stdout=open(f'verify_server_{TAG}.log', 'w'), stderr=subprocess.STDOUT)
for _ in range(600):
    if srv.poll() is not None:
        print('서버가 시작하지 못했다', flush=True)
        sys.exit(2)
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3)
        break
    except Exception:  # noqa: BLE001
        time.sleep(3)
PROMPT = '고객이 여행 일정 안내 챗봇에게 이렇게 말했다: "{q}"\n챗봇이 이 말이 가리키는 일정 항목으로 아래를 골랐다.\n{line}\n고객의 말이 정말 이 일정 항목에 대한 질문 · 요청인가? 일상 대화 · 잡담이거나 이 항목과 무관하면 NO. 반드시 YES 또는 NO 한 단어로만 답하라.'
f = open(dst, 'a', encoding='utf-8')
t0 = time.time()
try:
    for k, x in enumerate(todo):
        body = {'messages': [{'role': 'user', 'content': PROMPT.format(q=x['q'], line=x['line'])}], 'max_tokens': 4, 'temperature': 0, 'logprobs': True, 'top_logprobs': 10, 'chat_template_kwargs': {'enable_thinking': False}}
        try:
            req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            r = json.loads(urllib.request.urlopen(req, timeout=300).read())
            txt = (r['choices'][0]['message'].get('content') or '').strip()
            lp = (r['choices'][0].get('logprobs') or {}).get('content') or []
            py = pn = 0.0
            for tk in lp[:1]:
                for a in tk.get('top_logprobs', []):
                    t = a['token'].strip().upper()
                    if t in ('YES', 'Y'):
                        py += math.exp(a['logprob'])
                    elif t in ('NO', 'N'):
                        pn += math.exp(a['logprob'])
            rec = {'key': x['key'], 'content': txt[:12], 'p_yes': round(py / (py + pn), 5) if (py + pn) > 0 else None}
        except Exception as e:  # noqa: BLE001
            rec = {'key': x['key'], 'error': repr(e)[:80]}
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()
        if (k + 1) % 500 == 0:
            print(TAG, k + 1, '/', len(todo), round(time.time() - t0), '초', flush=True)
finally:
    srv.terminate()
print('끝', TAG, round(time.time() - t0), '초', flush=True)
