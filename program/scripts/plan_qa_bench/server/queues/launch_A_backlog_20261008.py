"""GPU 서버 A의 새 평가 대기열을 한 번만 시작한다."""
import os
from pathlib import Path
import subprocess

root = Path('/tmp/tripilot-a-backlog-20261008')
pidfile = root / 'queue.pid'
if pidfile.exists():
    pid = int(pidfile.read_text())
    os.kill(pid, 0)
    print('ALREADY_RUNNING', pid)
else:
    with (root / 'queue.log').open('xb') as log, open(os.devnull, 'rb') as null:
        process = subprocess.Popen(['python3', str(root / 'gpu_eval_queue.py'), '--root', str(root)],
                                   cwd=root, stdin=null, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    with pidfile.open('x') as f:
        f.write(str(process.pid))
    print('STARTED', process.pid)
