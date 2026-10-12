# 「짧은 확인 질문」 검토를 구독 CLI(Codex: gpt-6-astra · gpt-6.1-sol · gpt-6-luna)나 다른 호출 방식(OpenCode 무료 모델)으로 한 건씩 시험한다 — 같은 입력(verify_inputs.json) · 같은 질문문(verify_llama.py 와 글자까지 같음).
#  ★외부 서비스로는 **D3(Claude 가 새로 쓴 합성 문장) 항목만** 보낸다(--ds D3 기본). D · D2 의 AI Hub · KoCulture 문장은 보내지 않는다.
#  출력 verify_<태그>.jsonl 의 한 줄 = {key, content: YES|NO, p_yes: 0~1(모델이 말한 확신 — 확률이 아니라 말로 한 값), sec}. 이어 돌리기 가능.
# 사용: python verify_api_run.py <codex|opencode> <모델 id> <태그> [--input results/d_test/verify_inputs.json] [--ds D3] [--workers 3] [--limit N]
import argparse
import json
import os
import re
import subprocess
import tempfile
import threading
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
sys.stdout.reconfigure(encoding='utf-8')

ap = argparse.ArgumentParser()
ap.add_argument('kind', choices=['codex', 'opencode'])
ap.add_argument('model')
ap.add_argument('tag')
ap.add_argument('--input', default=os.path.join(HERE, 'results', 'd_test', 'verify_inputs.json'))
ap.add_argument('--ds', default='D3')
ap.add_argument('--workers', type=int, default=3)
ap.add_argument('--limit', type=int, default=0)
a = ap.parse_args()

PROMPT = '고객이 여행 일정 안내 챗봇에게 이렇게 말했다: "{q}"\n챗봇이 이 말이 가리키는 일정 항목으로 아래를 골랐다.\n{line}\n고객의 말이 정말 이 일정 항목에 대한 질문 · 요청인가? 일상 대화 · 잡담이거나 이 항목과 무관하면 NO. 반드시 YES 또는 NO 한 단어로만 답하라.'
SCHEMA = {'type': 'object', 'properties': {'verdict': {'type': 'string', 'enum': ['YES', 'NO']}, 'p_yes': {'type': 'number'}}}
EXTRA = '\n\n(파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라. verdict 는 YES 또는 NO. p_yes 는 「정답이 YES 일 확률」이다: 고객 말이 이 항목에 대한 말이 아니라고 확신하면 0.02 처럼 0 에 가깝게, 이 항목에 대한 말이라고 확신하면 0.98 처럼 1 에 가깝게. verdict 와 p_yes 가 서로 어긋나면 안 된다.)'
dst = os.path.join(HERE, 'results', 'd_test', f'verify_{a.tag}.jsonl')
items = [x for x in json.load(open(a.input, encoding='utf-8')) if x['ds'] in a.ds.split(',')]
if a.limit:
    items = items[:a.limit]
done = set()
if os.path.exists(dst):
    for line in open(dst, encoding='utf-8'):
        r = json.loads(line)
        if 'error' not in r:
            done.add(r['key'])
todo = [x for x in items if x['key'] not in done]
print(a.tag, a.model, '남은', len(todo), '/', len(items), flush=True)


def ask_codex(pr):
    from codex_percall import call
    val, sec, err = call(a.model, pr + EXTRA, SCHEMA, timeout=300)
    if val is None:
        return None, None, sec, err
    return val.get('verdict'), val.get('p_yes'), sec, None


_tls = threading.local()
OC_CFG = {"$schema": "https://opencode.ai/config.json", "autoupdate": False, "share": "disabled", "agent": {"build": {"permission": {"*": "ask"}}}}


def _oc_env():
    """작업 스레드마다 따로 쓰는 임시 폴더 · 설정 · 데이터 폴더(같은 폴더를 동시에 쓰면 무응답이 난다는 점검 결과 — 2026-10-07 확인 담당 보고)."""
    if not hasattr(_tls, 'dir'):
        base = tempfile.mkdtemp(prefix='ocw_')
        os.makedirs(os.path.join(base, 'work'), exist_ok=True)
        cfg = os.path.join(base, 'cfg.json')
        json.dump(OC_CFG, open(cfg, 'w'))
        _tls.dir = base
        _tls.env = dict(os.environ, OPENCODE_DISABLE_CLAUDE_CODE='1', OPENCODE_DISABLE_AUTOUPDATE='1', OPENCODE_CONFIG=cfg,
                        XDG_DATA_HOME=os.path.join(base, 'data'), XDG_STATE_HOME=os.path.join(base, 'state'), XDG_CACHE_HOME=os.path.join(base, 'cache'))
    return _tls.dir, _tls.env


def ask_opencode(pr):
    """OpenCode 무료 모델 한 건 호출. 도구는 권한 `ask` 로 자동 거절된다(도구를 아예 빼면 무료 구간이 403)."""
    t0 = time.perf_counter()
    exe = os.path.join(os.environ.get('APPDATA', ''), 'npm', 'node_modules', 'opencode-ai', 'bin', 'opencode.exe')
    msg = pr + '\n\n(도구를 쓰지 말고 JSON 한 줄로만 답하라: {"verdict": "YES" 또는 "NO", "p_yes": 0~1 숫자. p_yes 는 정답이 YES 일 확률 — 이 항목에 대한 말이 아니라고 확신하면 0 에 가깝게})'
    base, env = _oc_env()
    try:
        r = subprocess.run([exe, 'run', '-m', a.model, '--dir', os.path.join(base, 'work'), '--format', 'json', msg], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=150, env=env)
        txt = r.stdout.decode('utf-8', 'replace')
        parts = []
        for line in txt.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'text':
                v = (ev.get('part') or {}).get('text')
                if isinstance(v, str):
                    parts.append(v)
        body = ''.join(parts) or txt
        m = re.search(r'\{[^{}]*"verdict"[^{}]*\}', body, re.S)
        if m:
            o = json.loads(m.group(0))
            return o.get('verdict'), o.get('p_yes'), time.perf_counter() - t0, None
        w = re.search(r'\b(YES|NO)\b', body.upper())
        if w:
            return w.group(1), None, time.perf_counter() - t0, None
        return None, None, time.perf_counter() - t0, 'no verdict: ' + body[-120:]
    except Exception as e:  # noqa: BLE001
        return None, None, time.perf_counter() - t0, repr(e)[:100]


ask = ask_codex if a.kind == 'codex' else ask_opencode


def one(x):
    v, p, sec, err = ask(PROMPT.format(q=x['q'], line=x['line']))
    if v not in ('YES', 'NO'):
        return {'key': x['key'], 'error': err or f'bad verdict {v}', 'sec': round(sec, 1)}
    py = float(p) if isinstance(p, (int, float)) else (1.0 if v == 'YES' else 0.0)
    fixed = False
    if (v == 'NO' and py > 0.5) or (v == 'YES' and py < 0.5):   # 모델이 verdict 와 어긋난 값을 낸 경우 — 「verdict 에 대한 확신」으로 읽고 뒤집는다(원값은 p_raw 에 남김)
        py, fixed = 1.0 - py, True
    return {'key': x['key'], 'content': v, 'p_yes': round(py, 4), 'p_raw': p, 'fixed': fixed, 'sec': round(sec, 1)}


f = open(dst, 'a', encoding='utf-8')
t0 = time.time()
nerr = 0
with ThreadPoolExecutor(a.workers) as ex:
    for k, rec in enumerate(ex.map(one, todo)):
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()
        nerr += 'error' in rec
        if (k + 1) % 25 == 0:
            print(a.tag, k + 1, '/', len(todo), round(time.time() - t0), '초 · 오류', nerr, flush=True)
print('끝', a.tag, round(time.time() - t0), '초 · 오류', nerr, flush=True)
