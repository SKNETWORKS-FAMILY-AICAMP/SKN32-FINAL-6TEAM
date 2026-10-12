# D 시험(혼합 트래픽 2,735문제)을 x600 Ollama 의 모델로 돌려 일정 항목 번호(또는 「없음」)를 받는다 — 생각 끔 · 온도 0 · 상용 API 없음.
#  프롬프트는 연결 시험이 쓴 것과 같은 파일(results/empty_probe/all_prompts.json — AI Hub 문장이 들어 있어 git 밖). 출력 형식은 JSON 스키마로 강제한다({"item": 정수|null}).
#  같은 일정이 이어지는 문제는 올라마가 앞부분을 다시 쓰도록 (세트, 문제 번호) 순서로 보낸다. 이어 돌리기: 같은 결과 파일에 있는 문제는 건너뛴다.
# 사용: python d_test_ollama.py <모델 태그> <결과.jsonl> [동시 호출 수=1]
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
model, dst = sys.argv[1], sys.argv[2]
par = int(sys.argv[3]) if len(sys.argv) > 3 else 1
base = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
items = sorted(json.load(open(os.path.join(HERE, 'results', 'empty_probe', 'all_prompts.json'), encoding='utf-8')), key=lambda x: (x['set'], x['qi']))
if os.environ.get('DT_ONLY769') == '1':        # 일정 관련 합성 질문 769문제만(잡담 · 관광지 질문 · 요청 둘 제외)
    items = [it for it in items if it['type'] not in ('chitchat', 'tourist_synth_in', 'tourist_synth_out', 'compound_intent')]
done = set()
if os.path.exists(dst):
    for line in open(dst, encoding='utf-8'):
        done.add(json.loads(line)['i'])
todo = [it for it in items if it['i'] not in done]
print(model, '남은 문제', len(todo), '/', len(items), flush=True)
SCHEMA = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
f = open(dst, 'a', encoding='utf-8')
t0 = time.time()


def one(it):
    body = {'model': model, 'stream': False, 'think': False, 'format': SCHEMA, 'options': {'temperature': 0, 'num_predict': 16},
            'messages': [{'role': 'user', 'content': it['prompt']}]}
    t1 = time.perf_counter()
    try:
        req = urllib.request.Request(base + '/api/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        r = json.loads(urllib.request.urlopen(req, timeout=900).read())
        txt = (r.get('message') or {}).get('content') or ''
        mm = re.search(r'"item"\s*:\s*(null|\d+)', txt)
        rec = {'i': it['i'], 'set': it['set'], 'qi': it['qi'], 'type': it['type'], 'gold': it['gold'], 'content': txt[:60], 'parsed': bool(mm),
               'pick': None if (not mm or mm.group(1) == 'null') else int(mm.group(1)), 'ms': round((time.perf_counter() - t1) * 1000),
               'prompt_eval': r.get('prompt_eval_count'), 'eval': r.get('eval_count')}
    except Exception as e:  # noqa: BLE001
        rec = {'i': it['i'], 'set': it['set'], 'qi': it['qi'], 'type': it['type'], 'gold': it['gold'], 'error': repr(e)[:100]}
    return rec


with ThreadPoolExecutor(par) as ex:
    for k, rec in enumerate(ex.map(one, todo)):
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()
        if (k + 1) % 100 == 0:
            print(model, k + 1, '/', len(todo), round(time.time() - t0), '초', flush=True)
print('끝', model, round(time.time() - t0), '초')
