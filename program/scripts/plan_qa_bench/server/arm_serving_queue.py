"""ARM 실환경에서 여행 질의 정확도와 연속 서빙 안정성을 함께 기록한다.

별도 manifest의 준비된 작업을 한 개씩 실행한다. 반복 soak 결과는
독립 정확도 표본으로 합치지 않는다. 프로세스 잠금과 저장된 문항으로 재개한다.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
import urllib.request


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, value, backup=False):
    if backup and path.exists():
        dst = path.parent / '_backup' / 'state_history'
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst / f'{time.time_ns()}_{path.name}')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def host_ticks():
    v = [int(x) for x in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
    return sum(v), v[3] + v[4], v[7]


def resources(root, stop):
    previous = host_ticks()
    cgroup = next(x.split(':', 2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    group = Path('/sys/fs/cgroup') / cgroup.lstrip('/')
    usage = lambda: int(dict(x.split() for x in (group / 'cpu.stat').read_text().splitlines())['usage_usec'])
    prior_usage, prior_time = usage(), time.monotonic()
    with (root / 'resources.jsonl').open('a', encoding='utf-8') as out:
        while not stop.wait(5):
            current = host_ticks()
            delta = current[0] - previous[0]
            current_usage, current_time = usage(), time.monotonic()
            mem = dict((a.rstrip(':'), int(b.split()[0])) for a, b in
                       (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines()))
            row = dict(at=now(), window_s=current_time-prior_time,
                       host_cpu_busy_pct=100*(delta-(current[1]-previous[1])-(current[2]-previous[2]))/delta,
                       host_steal_pct=100*(current[2]-previous[2])/delta,
                       workload_cpu_pct_of_two_cores=100*(current_usage-prior_usage)/1e6/(current_time-prior_time)/2,
                       workload_memory_bytes=int((group/'memory.current').read_text()),
                       host_available_bytes=mem['MemAvailable']*1024)
            out.write(json.dumps(row)+'\n')
            out.flush()
            previous, prior_usage, prior_time = current, current_usage, current_time


def ask(it, job, port):
    start = time.monotonic()
    row = {k: it[k] for k in ('i', 'set', 'type', 'gold')}
    try:
        body = dict(messages=[dict(role='user', content=it['prompt'])], max_tokens=16,
                    temperature=0, seed=job['seed'], cache_prompt=job['cache_prompt'],
                    chat_template_kwargs={'enable_thinking': False})
        req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',
                                     data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=job['request_timeout_s']) as res:
            value = json.load(res)
        content = value['choices'][0]['message'].get('content') or ''
        match = re.search(r'"item"\s*:\s*(null|\d+)', content)
        pick = None if not match or match[1] == 'null' else int(match[1])
        row.update(parsed=bool(match), pick=pick, content=content, timings=value.get('timings', {}))
        row['correct'] = bool(match) and pick == it['gold']
    except Exception as exc:
        row.update(error=repr(exc), parsed=False, correct=False)
    row.update(wall_s=time.monotonic()-start, at=now())
    return row


def run(root, manifest, job, folder):
    prompts = Path(job['prompts'])
    if digest(prompts) != job['prompt_sha256']:
        raise ValueError('고정 입력 해시가 바뀌었습니다')
    items = json.loads(prompts.read_text(encoding='utf-8'))
    expected = {x['i'] for x in items}
    if len(expected) != len(items):
        raise ValueError('입력 문항 ID 중복')
    output = folder / 'answers.jsonl'
    saved = [json.loads(x) for x in output.read_text(encoding='utf-8').splitlines()] if output.exists() else []
    done = {x['i'] for x in saved}
    if len(done) != len(saved) or not done <= expected:
        raise ValueError('답안 중복 또는 입력 불일치')
    if done == expected:
        return summarize(saved, len(items))
    cmd = [manifest['engine'], '-m', job['model'], '-t', '2', '-tb', '2', '-ngl', '0',
           '-c', str(job['context_per_slot']*job['slots']), '-np', str(job['slots']),
           '--cache-ram', '256', '--port', str(manifest['port']), '--host', '127.0.0.1', '--jinja']
    if job.get('lora'):
        cmd += ['--lora', job['lora']]
    attempt = dict(at=now(), command=cmd, job=job, engine_sha256=digest(manifest['engine']),
                   model_sha256=digest(job['model']), worker_sha256=digest(__file__),
                   engine_version=subprocess.check_output([manifest['engine'], '--version'], stderr=subprocess.STDOUT, text=True).strip())
    (folder / f'attempt_{time.time_ns()}.json').write_text(json.dumps(attempt, ensure_ascii=False, indent=2), encoding='utf-8')
    with (folder / 'engine.log').open('a', encoding='utf-8') as log:
        engine = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(240):
                if engine.poll() is not None:
                    raise RuntimeError(f'모델 실행기 종료: {engine.returncode}')
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{manifest['port']}/health", timeout=2) as res:
                        if res.status == 200:
                            break
                except Exception:
                    time.sleep(2)
            else:
                raise TimeoutError('모델 준비 제한 시간 초과')
            atomic(root / 'active.json', dict(at=now(), job_id=job['id'], engine_pid=engine.pid, expected=len(items), saved=len(saved)))
            pending = [x for x in items if x['i'] not in done]
            with output.open('a', encoding='utf-8') as out, ThreadPoolExecutor(job['clients']) as pool:
                # 한 묶음만 대기시켜 실제 동시 접수 수를 고정한다.
                for offset in range(0, len(pending), job['clients']):
                    futures = [pool.submit(ask, x, job, manifest['port']) for x in pending[offset:offset+job['clients']]]
                    for future in futures:
                        row = future.result()
                        out.write(json.dumps(row, ensure_ascii=False)+'\n')
                        out.flush()
                        saved.append(row)
                    atomic(root / 'active.json', dict(at=now(), job_id=job['id'], engine_pid=engine.pid, expected=len(items), saved=len(saved)))
                    if engine.poll() is not None:
                        raise RuntimeError('추론 중 실행기 종료: 완료 문항은 보존했습니다')
        finally:
            if engine.poll() is None:
                engine.terminate()
                try:
                    engine.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    engine.kill()
                    engine.wait()
    return summarize(saved, len(items))


def summarize(rows, expected):
    latencies = sorted(x['wall_s'] for x in rows)
    positives = [x for x in rows if x['gold'] is not None]
    negatives = [x for x in rows if x['gold'] is None]
    return dict(expected=expected, saved=len(rows), correct=sum(x['correct'] for x in rows),
                normal_correct=sum(x['correct'] for x in positives), normal_total=len(positives),
                null_correct=sum(x['correct'] for x in negatives), null_total=len(negatives),
                false_positive=sum(x.get('parsed', False) and x.get('pick') is not None for x in negatives),
                errors_or_unparsed=sum(not x.get('parsed', False) or bool(x.get('error')) for x in rows),
                latency_p50_s=latencies[len(latencies)//2],
                latency_p95_s=latencies[min(len(latencies)-1, int(len(latencies)*.95))] if len(rows)>=59 else None,
                latency_max_s=max(latencies), repeated_soak_not_independent_accuracy=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    root = Path(ap.parse_args().root).resolve()
    import fcntl
    with (root/'queue.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('ALREADY_RUNNING', flush=True)
            return
        state_path = root/'state.json'
        state = json.loads(state_path.read_text()) if state_path.exists() else {'jobs': {}, 'cycle': 0}
        stop = threading.Event()
        monitor = threading.Thread(target=resources, args=(root, stop), daemon=True)
        monitor.start()
        try:
            while True:
                manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
                if shutil.disk_usage(root).free < manifest['min_free_bytes']:
                    atomic(root/'active.json', dict(at=now(), status='waiting_for_space'))
                    time.sleep(30)
                    continue
                if not monitor.is_alive():
                    raise RuntimeError('자원 기록이 중단됐습니다: 자원 로그와 journal을 확인하세요')
                unfinished = [v['job'] for v in state['jobs'].values() if v['status']=='running']
                ready = unfinished or [j for j in manifest['jobs'] if j['id'] not in state['jobs']]
                if not ready:
                    # 연속 시험은 별도 cycle로 보존하고 실패한 작업은 자동 반복하지 않는다.
                    completed = [j for j in manifest['jobs'] if state['jobs'].get(j['id'], {}).get('status')=='completed']
                    if not completed or not manifest['continuous_soak']:
                        time.sleep(30)
                        continue
                    cycle = state['cycle']
                    template = completed[cycle % len(completed)]
                    job = dict(template, id=f"soak_{cycle:06d}_{template['id']}")
                    state['cycle'] += 1
                else:
                    job = ready[0]
                folder = root/job['id']
                folder.mkdir(exist_ok=True)
                state['jobs'][job['id']] = dict(status='running', job=job, started=now())
                atomic(state_path, state, backup=True)
                print('START', job['id'], flush=True)
                try:
                    result = run(root, manifest, job, folder)
                    atomic(folder/'summary.json', result)
                    status = 'completed_with_errors' if result['errors_or_unparsed'] else 'completed'
                    state['jobs'][job['id']] = dict(status=status, job=job, finished=now(), **result)
                except Exception as exc:
                    state['jobs'][job['id']] = dict(status='failed', job=job, finished=now(), reason=repr(exc))
                atomic(state_path, state, backup=True)
                print('FINISH', job['id'], state['jobs'][job['id']]['status'], flush=True)
        finally:
            stop.set()
            monitor.join(timeout=10)


if __name__ == '__main__':
    main()
