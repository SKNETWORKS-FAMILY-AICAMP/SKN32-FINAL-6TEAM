"""기존 학습 종료 뒤 단일 잠금으로 미측정 HF 추론 조건을 순차 처리한다."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import time


def save(path, value):
    if path.exists():
        backup = path.parent/'_backup'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(path, backup/path.name)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2))
    os.replace(temporary, path)


def validate_dependencies(jobs):
    """미등록·역순 의존 작업을 건너뛰고 완료로 표시하는 사고를 막는다."""
    seen = set()
    for job in jobs:
        ident = job['id']
        if ident in seen:
            raise ValueError('Duplicate job id: ' + ident)
        dependency = job.get('dependency')
        if dependency and dependency not in seen:
            raise ValueError('Dependency must precede job: ' + ident + ' -> ' + dependency)
        seen.add(ident)


def unfinished_jobs(jobs, states):
    terminal = {'completed', 'completed_with_errors', 'failed'}
    return [j['id'] for j in jobs if states.get(j['id'], {}).get('status') not in terminal]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    lock = (root/'queue.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (root/'queue.pid').write_text(str(os.getpid()))
    manifest = json.loads((root/'manifest.json').read_text())
    validate_dependencies(manifest['jobs'])
    assert hashlib.sha256(Path(manifest['runner']).read_bytes()).hexdigest() == manifest['runner_sha256']
    for filename, digest in manifest['frozen_files'].items():
        with Path(filename).open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest, filename
    state_path = root/'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'jobs': {}}
    for job in manifest['jobs']:
        ident = job['id']
        if ident in state['jobs']:
            continue
        if job.get('dependency') and state['jobs'].get(job['dependency'], {}).get('status') != 'completed':
            continue
        if not Path(manifest['prior_all_done']).is_file():
            raise RuntimeError('Preceding training is not complete')
        while int(subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used',
                    '--format=csv,noheader,nounits'], text=True).strip()) >= 1000:
            time.sleep(15)
        folder = root/ident
        folder.mkdir(exist_ok=False)
        config = folder/'job.json'; config.write_text(json.dumps(job, indent=2))
        state['jobs'][ident] = dict(status='running', started_at=datetime.now(timezone.utc).isoformat())
        save(state_path, state)
        with (folder/'job.log').open('x') as log:
            process = subprocess.run([manifest['python'], manifest['runner'], '--job', str(config)],
                cwd=folder, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ,
                HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false'))
        summary_path = folder/'summary.json'
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        complete = process.returncode == 0 and summary.get('saved') == job['expected']
        if ident == manifest['smoke_job']:
            complete = complete and summary.get('errors') == summary.get('unparsed') == 0
        state['jobs'][ident] = dict(status=('completed' if summary.get('unparsed') == 0 else 'completed_with_errors')
            if complete else 'failed', exit_code=process.returncode, **summary)
        save(state_path, state)
    unfinished = unfinished_jobs(manifest['jobs'], state['jobs'])
    if unfinished:
        save(root/'INCOMPLETE.json', {'unexecuted': unfinished,
             'reason': 'dependency failed or not ready; not all planned jobs executed'})
        raise RuntimeError('Unexecuted jobs remain: ' + ', '.join(unfinished))
    (root/'PASS_FINISHED').write_text(datetime.now(timezone.utc).isoformat())


if __name__ == '__main__':
    main()
