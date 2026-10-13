"""GPU 한 기계에서 준비된 평가를 하나씩 실행한다. 대기 작업은 manifest로 보충한다."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def coverage(output, prompts):
    expected = {row['i'] for row in json.loads(prompts.read_text(encoding='utf-8'))}
    records = {}
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if row['i'] in records:
                raise ValueError('동일 문항 중복: 원본을 확인하세요')
            records[row['i']] = row
    errors = sum(bool(r.get('error')) or not r.get('parsed', False) for r in records.values())
    return dict(saved=len(records), expected=len(expected),
                complete=set(records) == expected, failed_or_unparsed=errors)


def save_state(path, state):
    if path.exists():
        backup = path.parent / '_backup' / 'state_history'
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup / f'{time.time_ns()}_{path.name}')
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = (root / 'queue.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('ALREADY_RUNNING', flush=True)
        return
    state_path = root / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'jobs': {}}
    while True:
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        ready = []
        for job in manifest['jobs']:
            ident = job['id']
            if not re.fullmatch('[a-z0-9_]+', ident):
                raise ValueError('작업 id 형식 오류')
            if state['jobs'].get(ident, {}).get('status') in ('completed', 'completed_with_errors', 'failed'):
                continue
            if Path(job['model']).is_file() and Path(job['prompts']).is_file() and (not job.get('lora') or Path(job['lora']).is_file()):
                ready.append(job)
        if not ready:
            print('WAITING_FOR_READY_JOBS', flush=True)
            time.sleep(30)
            continue
        memory = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True)
        if int(memory.strip()) >= 1000:
            time.sleep(15)
            continue
        job = ready[0]
        ident = job['id']
        folder = root / ident
        folder.mkdir(exist_ok=True)
        prompts = Path(job['prompts'])
        output = folder / f"d_test_{job['tag']}.jsonl"
        before = coverage(output, prompts)
        if before['complete']:
            state['jobs'][ident] = dict(status='completed_with_errors' if before['failed_or_unparsed'] else 'completed', **before)
            save_state(state_path, state)
            continue
        # 과거 시작 흔적이 있으면 자동으로 덮거나 재실행하지 않는다.
        if (folder / 'started.json').exists():
            state['jobs'][ident] = dict(status='failed', reason='previous start is incomplete; preserve logs and prepare explicit resume')
            save_state(state_path, state)
            continue
        env = dict(os.environ, GGUF=job['model'], LORA=job.get('lora', ''),
                   TAG=job['tag'], PROMPTS=job['prompts'], LOGPROBS=job.get('logprobs', '1'),
                   PORT=str(job['port']), LLAMA_SERVER=manifest['engine'], CORES='0-5')
        script = Path(job['script'])
        metadata = dict(job=job, started=datetime.now(timezone.utc).isoformat(),
                        prompt_sha256=hashlib.sha256(prompts.read_bytes()).hexdigest(),
                        script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
                        engine_version=subprocess.check_output([manifest['engine'], '--version'], env=dict(env, LD_LIBRARY_PATH=str(Path(manifest['engine']).parent)), text=True, stderr=subprocess.STDOUT).strip())
        (folder / 'started.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        with (folder / 'job.log').open('x', encoding='utf-8') as log:
            proc = subprocess.Popen([sys.executable, str(script)], cwd=folder, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
            state['jobs'][ident] = dict(status='running', pid=proc.pid, expected=before['expected'], saved=before['saved'])
            save_state(state_path, state)
            print('STARTED', ident, proc.pid, flush=True)
            code = proc.wait()
        after = coverage(output, prompts)
        state['jobs'][ident] = dict(status=('completed_with_errors' if after['failed_or_unparsed'] else 'completed') if code == 0 and after['complete'] else 'failed', exit_code=code, **after)
        save_state(state_path, state)
        print('FINISHED', ident, state['jobs'][ident], flush=True)


if __name__ == '__main__':
    main()
