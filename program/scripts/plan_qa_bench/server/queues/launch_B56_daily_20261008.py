"""기존 GPU 서버 B에서 새 일일 연구 대기열을 한 번만 시작한다."""
import os
from pathlib import Path
import subprocess

work = Path('/root/daily_rag_20261008')
pidfile = work / 'queue.pid'
if pidfile.exists():
    pid = int(pidfile.read_text().strip())
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        raise RuntimeError('이전 실행이 종료됐습니다. 로그를 확인하고 새 재개 스크립트를 준비하세요.')
    print(f'ALREADY_RUNNING pid={pid}')
else:
    with (work / 'job.log').open('xb') as log, open(os.devnull, 'rb') as null:
        process = subprocess.Popen(['bash', str(work / 'run_B56_daily_20261008.sh')],
                                   cwd=work, stdin=null, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    with pidfile.open('x') as f:
        f.write(str(process.pid))
    print(f'STARTED pid={process.pid}')
