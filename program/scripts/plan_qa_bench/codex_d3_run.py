# D3(합성 잡담 240 + 정답 있는 질문 120)를 Codex(gpt-6-sol 등)로 문제마다 한 번씩 풀어 오지목을 잰다 — 구독 CLI(API 아님), 동시 3, 실패는 한 번 다시.
#  모델에게 주는 것은 D 시험과 같은 질의문(일정 + 고객 질문 + 지시) · 출력 스키마 {"item": 정수|null}. ★CLI 는 에이전트 세션이라 지연이 API 보다 길다.
# 사용: python codex_d3_run.py <모델> <프롬프트.json> <결과.jsonl>
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')
from codex_percall import call  # noqa: E402

model, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
SCHEMA = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
items = json.load(open(src, encoding='utf-8'))
done = set()
if os.path.exists(dst):
    for line in open(dst, encoding='utf-8'):
        r = json.loads(line)
        if 'error' not in r:
            done.add(r['i'])
todo = [it for it in items if it['i'] not in done]
print(model, '남은', len(todo), '/', len(items), flush=True)
f = open(dst, 'a', encoding='utf-8')
t0 = time.time()


def one(it):
    val, sec, err = call(model, it['prompt'] + '\n\n(파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라.)', SCHEMA)
    if val is None:
        return {'i': it['i'], 'type': it['type'], 'gold': it['gold'], 'error': err, 'sec': round(sec, 1)}
    return {'i': it['i'], 'type': it['type'], 'gold': it['gold'], 'pick': val.get('item'), 'sec': round(sec, 1)}


with ThreadPoolExecutor(3) as ex:
    for k, rec in enumerate(ex.map(one, todo)):
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()
        if (k + 1) % 50 == 0:
            print(model, k + 1, '/', len(todo), round(time.time() - t0), '초', flush=True)
print('끝', model, round(time.time() - t0), '초', flush=True)
