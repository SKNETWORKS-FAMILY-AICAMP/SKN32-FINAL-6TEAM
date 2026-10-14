"""고정 item/null 계약으로 Saluki를 순차 평가한다. 기존 GPU worker가 소유한다."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.request

ROOT = Path('/tmp/tripilot-saluki-20261009')
SHA = '4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb'
REVISION = '1336c0b5d74dfe6ad7f793577092f5effd9f97c6'
TAG = os.environ['TAG']
MODEL = Path(os.environ['GGUF'])
PROMPTS = Path(os.environ['PROMPTS'])
ENGINE = os.environ['LLAMA_SERVER']
PORT = int(os.environ['PORT'])
SMOKE = 'saluki_smoke' in TAG
MARKER = ROOT/'SMOKE_PASS.json'


def memory():
    p = Path('/sys/fs/cgroup/memory')
    limit = int((p/'memory.limit_in_bytes').read_text())
    used = int((p/'memory.usage_in_bytes').read_text())
    return dict(limit=limit, used=used, headroom=limit-used)


def post(endpoint, body, timeout=60):
    request = urllib.request.Request(f'http://127.0.0.1:{PORT}/'+endpoint,
                                    data=json.dumps(body).encode(),
                                    headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(request, timeout=timeout).read())


def main():
    assert not os.environ.get('LORA'), 'Publisher original only'
    assert MODEL.is_file() and MODEL.stat().st_size == 7898369152
    assert hashlib.file_digest(MODEL.open('rb'), 'sha256').hexdigest() == SHA
    assert memory()['headroom'] >= 4*1024**3, 'Preserve running workload memory reserve'
    if not SMOKE:
        passed = json.loads(MARKER.read_text())
        assert passed['model_sha256'] == SHA and passed['parsed'] == passed['expected'] == 12
        assert passed['errors'] == 0
    items = sorted(json.loads(PROMPTS.read_text(encoding='utf-8')), key=lambda x: (x['set'], x['qi']))
    assert len({x['i'] for x in items}) == len(items)
    output = Path(f'd_test_{TAG}.jsonl')
    assert not output.exists(), 'Preserve existing attempt; do not automatically restart'
    command = ['taskset', '-c', os.environ.get('CORES', '0-5'), ENGINE, '-m', str(MODEL),
               '-t', '4', '-ngl', '99', '-c', '4096', '-np', '1', '--port', str(PORT),
               '--host', '127.0.0.1', '--jinja']
    env = dict(os.environ, LD_LIBRARY_PATH=str(Path(ENGINE).parent)+':'+os.environ.get('LD_LIBRARY_PATH', ''))
    contract = dict(model_revision=REVISION, model_sha256=SHA,
                    prompt_sha256=hashlib.sha256(PROMPTS.read_bytes()).hexdigest(),
                    runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    engine_sha256=hashlib.sha256(Path(ENGINE).read_bytes()).hexdigest(),
                    engine_version=subprocess.check_output([ENGINE, '--version'], env=env,
                        text=True, stderr=subprocess.STDOUT).strip(), command=command,
                    our_training=False, context=4096, max_tokens=16, temperature=0,
                    enable_thinking=False, memory_before_load=memory(), repetitions=1,
                    expected=len(items), GPU_owner='existing queue worker', final_ranking=False)
    with Path('saluki_contract.json').open('x') as f:
        json.dump(contract, f, indent=2)
    log = Path(f'dtest_server_{TAG}.log').open('x')
    server = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    stop = threading.Event()
    def resources():
        with Path('saluki_resources.jsonl').open('x') as samples:
            while not stop.is_set():
                sample = dict(timestamp=time.time(), memory=memory(),
                              gpu=subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu',
                                  '--format=csv,noheader'], text=True).strip())
                samples.write(json.dumps(sample)+'\n')
                samples.flush()
                stop.wait(5)
    monitor = threading.Thread(target=resources, daemon=True)
    monitor.start()
    records = []
    lengths = []
    try:
        healthy = False
        for _ in range(600):
            if server.poll() is not None:
                raise RuntimeError('Model load failed; preserve engine log and prepare a new attempt')
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3)
                healthy = True
                break
            except Exception:
                time.sleep(3)
        assert healthy, 'Model health timeout; no automatic restart'
        # The same installed engine parses both template-validation and generation bodies.
        for item in items:
            body = {'messages': [{'role': 'user', 'content': item['prompt']}],
                    'max_tokens': 16, 'temperature': 0, 'cache_prompt': True,
                    'chat_template_kwargs': {'enable_thinking': False}}
            template = post('apply-template', body)['prompt']
            tokens = post('tokenize', {'content': template, 'add_special': True, 'parse_special': True})['tokens']
            lengths.append({'i': item['i'], 'prompt_tokens': len(tokens), 'fits': len(tokens)+16 <= 4096})
        with Path('context_lengths.json').open('x') as f:
            json.dump(dict(expected=len(items), checked=len(lengths),
                           max_tokens=max(x['prompt_tokens'] for x in lengths),
                           oversize=sum(not x['fits'] for x in lengths), rows=lengths), f, indent=2)
        assert all(x['fits'] for x in lengths), 'No prompt truncation allowed; isolate a matched new protocol'
        with output.open('x', encoding='utf-8') as answers:
            for index, item in enumerate(items):
                body = {'messages': [{'role': 'user', 'content': item['prompt']}],
                        'max_tokens': 16, 'temperature': 0, 'cache_prompt': True,
                        'chat_template_kwargs': {'enable_thinking': False}}
                if os.environ.get('LOGPROBS') == '1':
                    body.update(logprobs=True, top_logprobs=20)
                record = {k: item[k] for k in ['i', 'set', 'qi', 'type', 'gold']}
                start = time.perf_counter()
                try:
                    response = post('v1/chat/completions', body, timeout=900)
                    text = response['choices'][0]['message'].get('content') or ''
                    match = re.search(r'"item"\s*:\s*(null|\d+)', text)
                    record.update(content=text, parsed=bool(match),
                                  pick=None if not match or match.group(1)=='null' else int(match.group(1)),
                                  usage=response.get('usage'),
                                  ms=round((time.perf_counter()-start)*1000))
                    for token in (response['choices'][0].get('logprobs') or {}).get('content') or []:
                        if token['token'].strip() == 'null' or token['token'].strip().isdigit():
                            alts = token.get('top_logprobs') or []
                            pn = sum(math.exp(a['logprob']) for a in alts if a['token'].strip()=='null')
                            pi = sum(math.exp(a['logprob']) for a in alts if a['token'].strip().isdigit())
                            record.update(p_null=round(pn/(pn+pi), 6) if pn+pi else None,
                                          p_mass=round(pn+pi, 4))
                            break
                except Exception as exc:
                    record['error'] = repr(exc)
                answers.write(json.dumps(record, ensure_ascii=False)+'\n')
                answers.flush()
                records.append(record)
                if (index+1) % 100 == 0 or SMOKE:
                    print(TAG, index+1, '/', len(items), flush=True)
        summary = dict(saved=len(records), expected=len(items),
                       parsed=sum(bool(r.get('parsed')) for r in records),
                       errors=sum(bool(r.get('error')) for r in records),
                       correct=sum(bool(r.get('parsed')) and not r.get('error') and r['pick']==r['gold'] for r in records),
                       model_sha256=SHA, memory_after_requests=memory(),
                       max_prompt_tokens=max(x['prompt_tokens'] for x in lengths), smoke=SMOKE)
        with Path('saluki_summary.json').open('x') as f:
            json.dump(summary, f, indent=2)
        if SMOKE:
            assert summary['parsed'] == summary['expected'] == 12 and summary['errors']==0, 'Format/load gate failed; preserve raw responses'
            with MARKER.open('x') as f:
                json.dump(summary, f, indent=2)
            # The existing worker skips the five comparison jobs until this symlink exists.
            (ROOT/'smoke_verified_model.gguf').symlink_to(MODEL.resolve())
        print(json.dumps(summary), flush=True)
    finally:
        stop.set()
        monitor.join(timeout=10)
        server.terminate()
        try:
            server.wait(timeout=60)
        except subprocess.TimeoutExpired:
            # Only this attempt's child engine is owned by this runner.
            server.kill()
            server.wait()
        log.close()


if __name__ == '__main__':
    main()
