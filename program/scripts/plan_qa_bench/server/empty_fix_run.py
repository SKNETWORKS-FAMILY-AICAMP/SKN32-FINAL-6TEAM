# 서버에서: 섞은 시험 세트 2,735문제를 「생각 모드 끄기」(chat_template_kwargs enable_thinking=false)로 가르친 E4B(llama.cpp)에 다시 불러 결과를 남긴다.
#  연결 시험(chain_e2e.py e4b_stage)과 같은 호출(max_tokens 16 · 온도 0 · cache_prompt)에서 생각 모드만 끈 것이다. 문제를 세트 순서대로 조각(shard)으로 나눠 서버 여러 개에 돌린다.
# 사용: python empty_fix_run.py <포트> <조각번호> <조각수> <프롬프트.json> <결과.jsonl> [thinking_on]
import json
import re
import sys
import time
import urllib.request

port, shard, nsh, src, dst = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
think_on = len(sys.argv) > 6 and sys.argv[6] == 'thinking_on'
items = json.load(open(src, encoding='utf-8'))
mine = [it for k, it in enumerate(sorted(items, key=lambda x: (x['set'], x['qi']))) if k % nsh == shard]
done = set()
try:
    for line in open(dst, encoding='utf-8'):
        done.add(json.loads(line)['i'])
except FileNotFoundError:
    pass
f = open(dst, 'a', encoding='utf-8')
t0 = time.time()
n = 0
for it in mine:
    if it['i'] in done:
        continue
    body = {'messages': [{'role': 'user', 'content': it['prompt']}], 'max_tokens': 16, 'temperature': 0, 'cache_prompt': True}
    if not think_on:
        body['chat_template_kwargs'] = {'enable_thinking': False}
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t1 = time.perf_counter()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=900))
        m = r['choices'][0]['message']
        txt = m.get('content') or ''
        rec = {'i': it['i'], 'set': it['set'], 'qi': it['qi'], 'content': txt[:60], 'reasoning_len': len(m.get('reasoning_content') or ''), 'finish': r['choices'][0].get('finish_reason'), 'ms': round((time.perf_counter() - t1) * 1000)}
        mm = re.search(r'"item"\s*:\s*(null|\d+)', txt)
        rec['pick'] = None if (not mm or mm.group(1) == 'null') else int(mm.group(1))
        rec['parsed'] = bool(mm)
    except Exception as e:  # noqa: BLE001
        rec = {'i': it['i'], 'set': it['set'], 'qi': it['qi'], 'error': repr(e)[:100]}
    f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    f.flush()
    n += 1
    if n % 50 == 0:
        print(shard, n, '/', len(mine), round(time.time() - t0), '초', flush=True)
print('끝', shard, n, round(time.time() - t0), '초')
