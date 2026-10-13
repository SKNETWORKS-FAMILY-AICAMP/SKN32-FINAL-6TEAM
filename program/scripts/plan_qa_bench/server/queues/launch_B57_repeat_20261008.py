"""준비된 두 번째 대조 학습 대기열을 중복 없이 한 번만 등록한다."""
import fcntl
import os
from pathlib import Path
import subprocess

work = Path('/root/daily_rag_repeat_20261008')
with (work / 'launch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    pidfile = work / 'queue.pid'
    if pidfile.exists():
        pid = int(pidfile.read_text().strip())
        os.kill(pid, 0)
        print(f'ALREADY_RUNNING pid={pid}')
    else:
        with (work / 'job.log').open('xb') as log, open(os.devnull, 'rb') as null:
            process = subprocess.Popen(['bash', str(work / 'run_B57_repeat_20261008.sh')],
                                       cwd=work, stdin=null, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        with pidfile.open('x') as f:
            f.write(str(process.pid))
        print(f'STARTED pid={process.pid}')
