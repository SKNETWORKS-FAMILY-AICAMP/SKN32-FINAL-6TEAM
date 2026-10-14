"""성공한 앱 출력 계약의 동시 처리·장시간 안정성을 별도로 관측한다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def gate(rows, budget):
    selected = [r for r in rows if r.get('budget') == budget]
    identities = {(r.get('case'), r.get('history'), r.get('repeat')) for r in selected}
    conditions = {(r.get('case'), r.get('history')) for r in selected}
    if (len(selected) != 24 or len(identities) != 24 or len(conditions) != 12
            or {r.get('repeat') for r in selected} != {1, 2}
            or not all(r.get('parsed') and r.get('correct') and not r.get('error') for r in selected)):
        raise ValueError('해당 출력 한도 선행 계약 12조건·2반복이 전부 통과하지 않았습니다')
    return selected


def aggregate(rows):
    return dict(attempted=len(rows), correct=sum(bool(r.get('correct')) for r in rows),
                failed=sum(not r.get('correct') for r in rows),
                transport_errors=sum(bool(r.get('error')) for r in rows),
                not_independent_accuracy=True)


def call(row, endpoint, inspector):
    start = time.monotonic()
    try:
        req = urllib.request.Request(endpoint + '/v1/chat/completions',
            data=json.dumps(row['payload']).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = json.load(response)
        result = inspector(raw, row['gold'])
        result['raw_response'] = raw
    except Exception as error:
        result = dict(parsed=False, correct=False, error=type(error).__name__)
    result.update(seconds=time.monotonic() - start, case=row['case'], history=row['history'])
    return result


def main():
    spec = json.loads(Path(os.environ['PROMPTS']).read_text())[0]
    previous = [json.loads(line) for line in Path(spec['prerequisite_answers']).read_text().splitlines()]
    gate(previous, spec["output_budget"])
    source = json.loads(Path(spec['payloads']).read_text())
    # 각 고유 질문·이력의 800토큰 조건 하나만 순환한다. 반복은 독립 정확도가 아니다.
    cases = [r for r in source if r['repeat'] == 1 and r['payload']['max_tokens'] == spec['output_budget']]
    if len(cases) != 12:
        raise ValueError('고정 고유 조건 수 불일치')
    module_spec = importlib.util.spec_from_file_location('inspector', spec['inspector'])
    module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
    endpoint = 'http://127.0.0.1:' + os.environ['PORT']
    command = [os.environ['LLAMA_SERVER'], '-m', os.environ['GGUF'], '-ngl', '99',
               '-t', '4', '-tb', '4', '-c', '8192', '-np', '2', '--jinja',
               '--host', '127.0.0.1', '--port', os.environ['PORT']]
    if os.environ.get('LORA'):
        command += ['--lora', os.environ['LORA']]
    env = dict(os.environ, LD_LIBRARY_PATH=str(Path(os.environ['LLAMA_SERVER']).parent))
    with Path('engine.log').open('x') as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        results = []; stop = 'duration_completed'; consecutive_failures = 0
        try:
            for _ in range(180):
                if process.poll() is not None:
                    raise RuntimeError('안정성 모델 기동 실패')
                try:
                    with urllib.request.urlopen(endpoint + '/health', timeout=2) as reply:
                        if reply.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError('안정성 모델 준비 시간 초과')
            started = time.monotonic(); deadline = started + spec['duration_seconds']; index = 0; last_resource = -60
            with Path('observations.jsonl').open('x') as output, ThreadPoolExecutor(2) as pool:
                while time.monotonic() < deadline:
                    # 시간대별 1·2 동시 접수 교대. 기존 모델 정확도 순위 시험과 구분한다.
                    concurrency = 1 + (int((time.monotonic() - started) // spec['phase_seconds']) % 2)
                    selected = [cases[(index + k) % len(cases)] for k in range(concurrency)]
                    futures = [pool.submit(call, row, endpoint, module.inspect_response) for row in selected]
                    for future in futures:
                        result = future.result(); result.update(i=index, concurrency=concurrency,
                            observed_at_utc=datetime.now(timezone.utc).isoformat())
                        index += 1; results.append(result)
                        consecutive_failures = 0 if result['correct'] else consecutive_failures + 1
                        output.write(json.dumps(result, ensure_ascii=False) + '\n'); output.flush()
                    if time.monotonic() - started - last_resource >= 60:
                        status = Path('/proc/' + str(process.pid) + '/status').read_text().splitlines()
                        memory = {line.split(':')[0]:int(line.split()[1])*1024 for line in status if line.startswith(('VmRSS:', 'VmHWM:'))}
                        memory.update(observed_at_utc=datetime.now(timezone.utc).isoformat(), concurrency=concurrency)
                        memory['gpu_memory_mib'] = subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip()
                        with Path('resources.jsonl').open('a') as resource:
                            resource.write(json.dumps(memory) + '\n')
                        last_resource = time.monotonic() - started
                    summary = dict(aggregate(results), elapsed_seconds=time.monotonic() - started,
                                   concurrency=concurrency, phase_seconds=spec['phase_seconds'])
                    temp = Path('progress.tmp'); temp.write_text(json.dumps(summary)); temp.replace('progress.json')
                    if consecutive_failures >= spec['consecutive_failure_limit']:
                        stop = 'consecutive_failure_limit'; break
            summary = dict(aggregate(results), elapsed_seconds=time.monotonic() - started, stop=stop,
                unique_conditions=len(cases), independent_accuracy=False,
                slots=2, context_total=8192, latency_scope='co-running host; within-job concurrency phases only')
            Path('summary.json').write_text(json.dumps(summary, indent=2))
            final = dict(i=0, parsed=True, correct=summary['failed'] == 0, pick=summary,
                         error='stability_failure' if summary['failed'] else None)
            Path('d_test_' + os.environ['TAG'] + '.jsonl').write_text(json.dumps(final) + '\n')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()


if __name__ == '__main__':
    main()
