"""규정 재순위 프롬프트(prompts.json)를 **제품의 OpenAI 대체 경로 그대로**(`llm_failover.OpenAIChat.json` · 서버용 키 · 모델 gpt-6-luna · 개인정보 가림 `masked`)로 한 건씩 보내
모델 답 · 지연 · 토큰 사용량을 남긴다. (2026-10-15 사용자 지시 「서버용 OpenAI 키 API(gpt-6-luna)로 902건, 시작 전 단가 확인, 하루 호출 상한 안에서」)

점수 계산은 여기서 하지 않는다 — `product_rerank_eval.py score --outputs <d_test_*.jsonl>` 가 한다 (Ollama 실행기 `product_rerank_runner.py` 와 같은 출력 모양).
호출 예산(스스로 거는 한도): 최대 호출 수 `--max-calls`(기본 902) · 하루 상한 2,000 의 절반 미만 · 누적 추정 비용 `--max-usd` 를 넘으면 멈춘다 · 연속 5번 실패하면 멈춘다 ·
재시도 없음(제품과 같다 — 실패는 분모에 남긴다). 동시 호출 `--workers`(기본 3).
사용: python product_rerank_openai_runner.py --prompts <prompts.json> --out <d_test_X.jsonl> [--limit N] [--max-calls 902] [--max-usd 0.40] [--workers 3]
키는 로컬 `final_project_cs/.env`(git 밖)의 `ACOP_OPENAI_API_KEY_SERVER` 에서 읽고 어디에도 찍지 않는다.
"""
import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CS = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', 'final_project_cs'))
sys.path[:0] = [CS]
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import dotenv_values  # noqa: E402

from app.core.redaction import masked  # noqa: E402
from app.infrastructure.llm_failover import OpenAIChat  # noqa: E402

PRICE_IN, PRICE_OUT = 0.10 / 1e6, 0.50 / 1e6          # 제3자 가격표(2026-10-11 기준, 공식 페이지 미확인) — 달러/토큰. 상한 계산용이다

ap = argparse.ArgumentParser()
ap.add_argument('--prompts', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--max-calls', type=int, default=902)
ap.add_argument('--max-usd', type=float, default=0.40)
ap.add_argument('--workers', type=int, default=3)
ap.add_argument('--model', default='gpt-6-luna')
args = ap.parse_args()

env = {**dotenv_values(os.path.join(CS, '.env.apikeys')), **dotenv_values(os.path.join(CS, '.env'))}
key = (env.get('ACOP_OPENAI_API_KEY_SERVER') or '').strip()
assert key, 'ACOP_OPENAI_API_KEY_SERVER 가 비어 있다'
rows = json.load(open(args.prompts, encoding='utf-8'))
done = {}
if os.path.exists(args.out):
    for line in open(args.out, encoding='utf-8'):
        r = json.loads(line)
        if not r.get('error'):
            done[r['i']] = r                                   # 이어 돌리기 — 성공한 건은 다시 안 부른다(실패 건만 다시)
todo = [r for r in rows if r['i'] not in done]
if args.limit:
    todo = todo[:args.limit]
todo = todo[:args.max_calls]
print('보낼 건', len(todo), '· 이미 성공', len(done), '· 모델', args.model, '· 동시', args.workers, flush=True)

chat = OpenAIChat(api_key=key, model=args.model, timeout=30.0)      # 연구용이라 제품의 8초보다 길게 둔다(지연 한도 판정은 따로)
local = threading.local()
client = chat._api()
orig = client.chat.completions.create


def wrapped(**kw):
    r = orig(**kw)
    local.usage = getattr(r, 'usage', None)
    return r


client.chat.completions.create = wrapped
lock = threading.Lock()
state = {'calls': 0, 'usd': 0.0, 'fail_streak': 0, 'stop': False, 'in': 0, 'out': 0}
stream = open(args.out, 'a', encoding='utf-8')


def one(row):
    with lock:
        if state['stop'] or state['calls'] >= args.max_calls or state['usd'] >= args.max_usd:
            return None
        state['calls'] += 1
    rec = {'i': row['i']}
    local.usage = None
    t0 = time.perf_counter()
    try:
        value = chat.json(row['system'], masked(row['user']))
        rec['raw'] = json.dumps(value, ensure_ascii=False)
        rec['parsed'] = isinstance(value.get('ranking'), list)
    except Exception as exc:                                    # noqa: BLE001 — 실패는 이유 이름만 남긴다(키·본문 안 싣는다)
        rec.update(parsed=False, error=type(exc).__name__ + ': ' + str(exc)[:80].replace(key, '***'))
    rec['seconds'] = round(time.perf_counter() - t0, 3)
    u = local.usage
    if u is not None:
        rec['prompt_tokens'], rec['eval_tokens'] = u.prompt_tokens, u.completion_tokens
    with lock:
        if u is not None:
            state['in'] += u.prompt_tokens
            state['out'] += u.completion_tokens
            state['usd'] = state['in'] * PRICE_IN + state['out'] * PRICE_OUT
        state['fail_streak'] = state['fail_streak'] + 1 if rec.get('error') else 0
        if state['fail_streak'] >= 5:
            state['stop'] = True
            print('연속 5번 실패 — 멈춘다', rec.get('error'), flush=True)
        stream.write(json.dumps(rec, ensure_ascii=False) + '\n')
        stream.flush()
        if state['calls'] % 50 == 0:
            print(state['calls'], '건 · 추정 비용 $%.4f · 토큰 %d/%d' % (state['usd'], state['in'], state['out']), flush=True)
    return rec


t_all = time.time()
with ThreadPoolExecutor(args.workers) as ex:
    list(ex.map(one, todo))
print('끝', state['calls'], '건 · 추정 비용 $%.4f · 입력 %d · 출력 %d 토큰 · %d초' % (state['usd'], state['in'], state['out'], time.time() - t_all), flush=True)
