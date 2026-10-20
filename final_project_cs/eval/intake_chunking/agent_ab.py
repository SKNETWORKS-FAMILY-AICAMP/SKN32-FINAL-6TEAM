# -*- coding: utf-8 -*-
"""읽기 에이전트 — 같은 긴 계획을 한 번에 받기(2번) · 조금씩 받기(1번)로 보내 답이 같은지 본다(4회차 확인). `python eval/intake_chunking/agent_ab.py L4` — 재현 Ollama 주소는 URL."""
import json, os, sys, time
from datetime import date
sys.path.insert(0, '.')
from eval.intake_diverse.run_current import _DUMMY_ENV
for k, v in _DUMMY_ENV.items():
    os.environ.setdefault(k, v)
sys.stdout.reconfigure(encoding='utf-8')
import httpx
from app.domains.travel_ops.components.intake import agent_read
from eval.intake_chunking.cases import all_cases

URL = 'http://127.0.0.1:11535'
case = {c['case_id']: c for c in all_cases()}[sys.argv[1] if len(sys.argv) > 1 else 'L4']
text = case['text']
system = agent_read.system_for(date(2026, 10, 16), '')
out = {}
for mode in ('plain', 'stream', 'plain'):
    payload = {'model': 'tripilot-pointer:e4b-ft', 'stream': mode == 'stream', 'think': False, 'format': agent_read.SCHEMA,
               'keep_alive': '30m', 'options': {'temperature': 0, 'num_ctx': 8192, 'num_predict': 3072},
               'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': text}]}
    t = time.perf_counter()
    if mode == 'plain':
        body = httpx.post(URL + '/api/chat', json=payload, timeout=300).json()
        content, evc, reason = body['message']['content'], body.get('eval_count'), body.get('done_reason')
    else:
        parts, tail = [], {}
        with httpx.stream('POST', URL + '/api/chat', json=payload, timeout=300) as r:
            for line in r.iter_lines():
                if line:
                    p = json.loads(line)
                    parts.append((p.get('message') or {}).get('content') or '')
                    if p.get('done'):
                        tail = p
        content, evc, reason = ''.join(parts), tail.get('eval_count'), tail.get('done_reason')
    secs = time.perf_counter() - t
    try:
        raw = json.loads(content)
        got = agent_read.ground(raw, text.splitlines())
        n_items, n_raw = len(got.items), len(raw.get('items') or [])
    except ValueError:
        n_items = n_raw = None
    print(mode, 'sec', round(secs, 1), 'eval', evc, 'done', reason, 'raw_items', n_raw, 'grounded', n_items, 'chars', len(content))
    out.setdefault(mode, []).append(content)
print('same plain', out['plain'][0] == out['plain'][1], 'plain==stream', out['plain'][0] == out['stream'][0])
print(out['stream'][0][:600])
