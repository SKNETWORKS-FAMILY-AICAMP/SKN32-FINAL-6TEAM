"""같은 여행 입력으로 복수 항목 JSON 계약을 별도 평가한다. 기존 단일 계약과 합산하지 않는다."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def parse_items(content, allowed):
    """정확한 JSON만 인정하고 문자열·중복·없는 번호를 정답처럼 고치지 않는다."""
    try:
        obj = json.loads(content)
    except (ValueError, TypeError):
        return False, None
    if not isinstance(obj, dict) or set(obj) != {'items'} or not isinstance(obj['items'], list):
        return False, None
    xs = obj['items']
    if any(type(x) is not int or x not in allowed for x in xs) or len(set(xs)) != len(xs):
        return False, None
    return True, xs


def main():
    tag = os.environ['TAG']; prompts = Path(os.environ['PROMPTS'])
    rows = sorted(json.loads(prompts.read_text(encoding='utf-8')), key=lambda x: (x['set'], x['qi']))
    assert len({x['i'] for x in rows}) == len(rows)
    assert hashlib.sha256(prompts.read_bytes()).hexdigest() == rows[0]['file_source_prompt_sha'] or rows[0]['file_source_prompt_sha'] == 'derived_contract'
    output = Path(f'd_test_{tag}.jsonl'); assert not output.exists(), 'Use a separate attempt after inspecting any failure'
    port = os.environ['PORT']; engine = os.environ['LLAMA_SERVER']
    command = ['taskset', '-c', os.environ.get('CORES', '0-5'), engine, '-m', os.environ['GGUF'], '-t', '4', '-ngl', '99', '-c', '4096', '-np', '1', '--port', port, '--host', '127.0.0.1', '--jinja']
    if os.environ.get('LORA'): command += ['--lora', os.environ['LORA']]
    env = dict(os.environ, LD_LIBRARY_PATH=str(Path(engine).parent)+':'+os.environ.get('LD_LIBRARY_PATH', ''))
    contract = dict(contract='strict {items: integer[]} JSON; empty list for no selected item', max_tokens=64, temperature=0, context=4096, threads=4, gpu_layers=99, seed=0, enable_thinking=False, prompt_sha256=hashlib.sha256(prompts.read_bytes()).hexdigest(), output_schema_enforced=False, no_automatic_retry=True)
    with Path('multi_contract.json').open('x', encoding='utf-8') as f: json.dump(contract, f, ensure_ascii=False, indent=2)
    with Path(f'dtest_server_{tag}.log').open('x') as log:
        proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            healthy = False
            for _ in range(600):
                if proc.poll() is not None: raise RuntimeError('Model load failed; preserve this attempt')
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=3)
                    healthy = True; break
                except Exception: time.sleep(3)
            if not healthy: raise RuntimeError('Model health timeout')
            with output.open('x', encoding='utf-8') as f:
                for n, row in enumerate(rows, 1):
                    rec = {k: row[k] for k in ['i', 'set', 'qi', 'type', 'gold', 'gold_set']}
                    begin = time.perf_counter()
                    body = dict(messages=[dict(role='user', content=row['prompt'])], max_tokens=64, temperature=0, seed=0, cache_prompt=True, chat_template_kwargs=dict(enable_thinking=False))
                    try:
                        req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
                        result = json.loads(urllib.request.urlopen(req, timeout=900).read())
                        choice = result['choices'][0]; content = choice['message'].get('content') or ''
                        parsed, picks = parse_items(content, set(row['allowed_items']))
                        rec.update(content=content, parsed=parsed, pick=picks, usage=result.get('usage'), finish_reason=choice.get('finish_reason'))
                    except Exception as exc:
                        rec.update(parsed=False, pick=None, error=repr(exc))
                    rec['ms'] = round((time.perf_counter()-begin)*1000)
                    f.write(json.dumps(rec, ensure_ascii=False)+'\n'); f.flush()
                    if n % 100 == 0: print('SAVED', n, '/', len(rows), flush=True)
        finally:
            if proc.poll() is None: proc.terminate(); proc.wait(timeout=30)


if __name__ == '__main__':
    main()
