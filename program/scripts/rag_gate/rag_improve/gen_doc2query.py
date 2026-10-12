# 규정 조각마다 「이 조각이 답이 되는 고객 질문」을 모델이 미리 만들어 둔다(doc2query) — 색인 쪽 보강. 평가 질문(A·B)은 이 단계에서 보지 않는다.
#  모델: x600 서버 Ollama 의 gemma4:12b(제품 기본 모델 · 생각 끔 · 온도 0.7 · 조각마다 질문 6개). 결과는 results/rag_improve/doc2query.json — 조각 번호 → 질문 목록.
# 사용: python gen_doc2query.py [모델] [개수]
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.request

from retr_lib import CH, OLLAMA, OUT

MODEL = sys.argv[1] if len(sys.argv) > 1 else 'gemma4:12b'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
DST = os.path.join(OUT, 'doc2query.json' if MODEL == 'gemma4:12b' else f"doc2query_{MODEL.replace(':', '_').replace('/', '_')}.json")
sys.stdout.reconfigure(encoding='utf-8')
SYSTEM = ('당신은 여행 서비스 고객입니다. 아래 안내문 한 조각을 읽고, 이 안내가 **답이 되는** 고객의 질문을 한국어로 씁니다. '
          '규칙: ① 실제 고객이 채팅에 치듯 짧고 구어체로(10~25자) ② 안내문에 나온 낱말을 그대로 베끼지 말고 일상어로 바꿔 쓴다(예: 위약금 → 얼마 떼요, 순연 → 미룰 수 있나요) '
          '③ 서로 다른 상황·표현으로 쓴다 ④ 이 안내가 직접 답하지 못하는 질문은 쓰지 않는다. 출력은 JSON 한 줄: {"questions": ["...", ...]}')


def one(c):
    user = f"문서: {c['doc_title']}\n절: {c['section']}\n고객에게 보이는 문장: {c['line'] or ''}\n직원용 본문: {c['content'][:700]}\n\n질문 {N}개."
    body = {'model': MODEL, 'stream': False, 'think': False, 'format': 'json', 'options': {'temperature': 0.7, 'seed': 20261006},
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}
    for attempt in range(3):
        try:
            req = urllib.request.Request(OLLAMA + '/api/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            r = json.loads(urllib.request.urlopen(req, timeout=600).read())
            qs = json.loads(r['message']['content'])['questions']
            qs = [q.strip() for q in qs if isinstance(q, str) and 4 <= len(q.strip()) <= 60]
            if qs:
                return c['source'], qs[:N]
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:100]
            time.sleep(2)
    return c['source'], []


done = json.load(open(DST, encoding='utf-8')) if os.path.exists(DST) else {}
todo = [c for c in CH if c['source'] not in done]
t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=3) as ex:
    for k, (s, qs) in enumerate(ex.map(one, todo), 1):
        done[s] = qs
        if k % 10 == 0:
            json.dump(done, open(DST, 'w', encoding='utf-8'), ensure_ascii=False)
            print(k, '/', len(todo), round(time.time() - t0), '초', flush=True)
json.dump(done, open(DST, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
empty = [s for s, q in done.items() if not q]
print('끝', len(done), '조각 · 질문 없는 조각', len(empty), round(time.time() - t0), '초')
