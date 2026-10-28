"""codex_percall.call 동시 호출 시험 — 같은 work 폴더를 여러 스레드가 함께 써도 각 호출이 자기 프롬프트 · 스키마로 답을 받는지 본다.
실제 Codex CLI 는 부르지 않는다: subprocess.run 을 「stdin 의 프롬프트와 스키마 파일을 읽어 그대로 되돌려 주는」 대역으로 바꾼다.
Windows 시계 눈금(약 15.6ms)을 흉내 내려고 time.time_ns 를 고정값으로 바꾼다 — 예전 (pid, time_ns) 이름이면 모든 호출이 같은 파일을 쓴다.
실행: python -m pytest program/scripts/eval_kit/test_codex_percall.py -q"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codex_percall as cp  # noqa: E402

N = 12


def _fake_codex(seen, lock):
    def run(args, stdin=None, **_kw):
        prompt = stdin.read().decode('utf-8')            # 실제 CLI 처럼 시작할 때 프롬프트를 읽는다
        sp, of = args[args.index('--output-schema') + 1], args[args.index('-o') + 1]
        schema = json.load(open(sp, encoding='utf-8'))    # 스키마도 시작할 때 읽는다
        with lock:
            seen.append(sp)
        time.sleep(0.05 + (int(prompt.split('#')[1]) % 4) * 0.02)   # 끝나는 순서를 섞는다
        enum = schema['properties']['pick']['enum']
        json.dump({'pick': enum[0], 'echo': prompt}, open(of, 'w', encoding='utf-8'))
        return SimpleNamespace(returncode=0, stderr=b'')
    return run


def test_concurrent_calls_sharing_work_dir_do_not_mix(tmp_path, monkeypatch):
    seen, lock = [], threading.Lock()
    monkeypatch.setattr(cp.subprocess, 'run', _fake_codex(seen, lock))
    monkeypatch.setattr(cp.time, 'time_ns', lambda: 1791310066097885800)   # 같은 눈금 안에서 시작한 호출
    gate = threading.Barrier(N)

    def one(i):
        schema = {'type': 'object', 'properties': {'pick': {'type': 'string', 'enum': [f'cand_{i}']}, 'echo': {'type': 'string'}}}
        gate.wait()
        return i, cp.call('fake-model', f'문제 #{i}# 에 답하라', schema, work=str(tmp_path), retries=0)

    with ThreadPoolExecutor(N) as ex:
        out = list(ex.map(one, range(N)))
    for i, (val, _sec, err) in out:
        assert err is None, (i, err)
        assert val['echo'] == f'문제 #{i}# 에 답하라', f'{i}번 호출이 다른 문제의 프롬프트로 답했다: {val["echo"]}'
        assert val['pick'] == f'cand_{i}', f'{i}번 호출이 다른 문제의 스키마(선택지)로 답했다: {val["pick"]}'
    assert len(set(seen)) == N, '동시 호출끼리 스키마 파일 이름이 겹쳤다'
    assert os.listdir(tmp_path) == [], '끝난 호출의 임시 파일이 남았다'
