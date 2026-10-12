# 재순위 공용 함수 — exp3_rerank.py 와 같은 지시문 · 같은 호출 · 같은 캐시 키(모델 + 질문 + 후보 번호)를 쓴다.
import hashlib
import json
import os
import time
import urllib.request

from retr_lib import CH, OLLAMA, OUT

CACHE_PATH = os.path.join(OUT, 'rerank_cache.json')
SYSTEM = ('당신은 여행 서비스의 규정 검색 재순위 담당입니다. 고객 질문과 후보 안내 문장들이 주어집니다. '
          '각 후보는 서비스가 고객에게 그대로 보여 줄 안내 문장입니다. 고객 질문에 **직접 답이 되는** 문장만 골라 가장 알맞은 순서로 번호를 적습니다. '
          '관련 주제여도 질문이 묻는 구체 내용에 답하지 않는 문장은 고르지 않습니다. 직접 답하는 문장이 없으면 빈 목록입니다. 최대 3개. '
          '출력은 JSON 한 줄: {"ranking":[번호,...]}')


def load_cache():
    return json.load(open(CACHE_PATH, encoding='utf-8')) if os.path.exists(CACHE_PATH) else {}


def save_cache(cache):
    json.dump(cache, open(CACHE_PATH, 'w', encoding='utf-8'), ensure_ascii=False)


def llm_rank(model, q, cand, cache):
    """후보 조각 번호 목록 cand 에서 모델이 「직접 답하는 줄」로 고른 번호(최대 3, 순서대로). 캐시에 있으면 그대로."""
    key = hashlib.sha1(('\n'.join([model, q, ','.join(map(str, cand))])).encode('utf-8')).hexdigest()
    if key in cache:
        return cache[key]
    lines = '\n'.join(f"{k + 1}. [{CH[c]['section']}] {CH[c]['line'] or CH[c]['content'][:120]}" for k, c in enumerate(cand))
    body = {'model': model, 'stream': False, 'think': False, 'format': 'json', 'options': {'temperature': 0},
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': f'고객 질문: {q}\n\n후보 안내 문장:\n{lines}'}]}
    out = None
    for _ in range(3):
        try:
            req = urllib.request.Request(OLLAMA + '/api/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            r = json.loads(urllib.request.urlopen(req, timeout=600).read())
            rk = json.loads(r['message']['content']).get('ranking', [])
            out = [cand[int(n) - 1] for n in rk if isinstance(n, int) and 1 <= n <= len(cand)]
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    cache[key] = out if out is not None else []
    return cache[key]
