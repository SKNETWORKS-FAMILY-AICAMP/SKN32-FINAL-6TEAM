# 서버에서: 빈 답이 난 질문을 가르친 E4B(llama.cpp)에 다시 불러 응답 원문 전체를 본다 — 사용: python empty_probe_run.py <포트> <프롬프트.json> <결과.json> [max_tokens]
#  변형: a 연결 시험과 같은 호출(max_tokens 16 · cache_prompt) · b 앞 세 건만 긴 max_tokens · d 생각 모드 끄기(chat_template_kwargs enable_thinking=false). 응답 JSON 의 message 전체(content · reasoning_content)와 finish_reason · 사용 토큰을 그대로 남긴다.
import json
import sys
import time
import urllib.request

port, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
BIG = int(sys.argv[4]) if len(sys.argv) > 4 else 256
items = json.load(open(src, encoding='utf-8'))


def call(prompt, max_tokens, cache, kwargs=None):
    body = {'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens, 'temperature': 0, 'cache_prompt': cache}
    if kwargs is not None:
        body['chat_template_kwargs'] = kwargs
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    r = json.load(urllib.request.urlopen(req, timeout=900))
    return {'ms': round((time.perf_counter() - t0) * 1000), 'message': r['choices'][0]['message'], 'finish': r['choices'][0].get('finish_reason'), 'usage': r.get('usage')}


out = []
for i, it in enumerate(items):
    rec = {k: v for k, v in it.items() if k != 'prompt'}
    rec['a_as_chain'] = call(it['prompt'], 16, True)
    if i < 3:                                    # 긴 호출은 앞 세 건만(원문 확인용)
        rec['b_longer'] = call(it['prompt'], BIG, True)
    rec['d_nothink'] = call(it['prompt'], 16, True, {'enable_thinking': False})     # 생각 모드 끄기(요청 단위)
    out.append(rec)
    print(i, 'fail' if it['fail'] else 'ok', 'a=', repr(rec['a_as_chain']['message'].get('content'))[:30], 'reason_a', len(rec['a_as_chain']['message'].get('reasoning_content') or ''), '| d=', repr(rec['d_nothink']['message'].get('content'))[:30], 'reason_d', len(rec['d_nothink']['message'].get('reasoning_content') or ''), flush=True)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
print('끝')
