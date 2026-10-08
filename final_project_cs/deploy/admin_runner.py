"""독립 운영 컨테이너의 두 프로세스. 하나가 죽으면 둘 다 종료한다."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main() -> int:
    processes: list[subprocess.Popen] = []
    stopping = False

    def stop(_number=None, _frame=None):
        nonlocal stopping
        stopping = True
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    commands = [
        [sys.executable, "-m", "uvicorn", "app.ops_entrypoint:app", "--host", "127.0.0.1", "--port", "8070"],
        ["node", str(Path("/srv/admin/node_modules/next/dist/bin/next")), "start", "--hostname", "0.0.0.0", "--port", "3300"],
    ]
    try:
        for index, command in enumerate(commands):
            processes.append(subprocess.Popen(command, cwd="/srv" if index == 0 else "/srv/admin", env=os.environ.copy()))
        while not stopping:
            finished = next((p for p in processes if p.poll() is not None), None)
            if finished is not None:
                return finished.returncode or 1
            time.sleep(0.2)
        return 0
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
