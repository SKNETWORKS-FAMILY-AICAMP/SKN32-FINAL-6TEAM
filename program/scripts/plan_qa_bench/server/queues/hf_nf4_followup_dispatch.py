"""기존 HF 평가가 종료되고 잠금이 해제된 뒤 별도 누락 평가를 시작한다."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior-root', type=Path, required=True)
    parser.add_argument('--next-root', type=Path, required=True)
    parser.add_argument('--queue', type=Path, required=True)
    args = parser.parse_args()
    own_lock = (args.next_root/'dispatcher.lock').open('a')
    fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (args.next_root/'dispatcher.pid').write_text(str(os.getpid()))
    prior_lock = (args.prior_root/'queue.lock').open('a')
    while True:
        try:
            fcntl.flock(prior_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            time.sleep(10)
            continue
        pid = int((args.prior_root/'queue.pid').read_text())
        if Path(f'/proc/{pid}').exists():
            fcntl.flock(prior_lock, fcntl.LOCK_UN)
            time.sleep(10)
            continue
        if not (args.prior_root/'PASS_FINISHED').is_file():
            raise RuntimeError('Prior worker ended without final marker; preserve and inspect')
        manifest = json.loads((args.prior_root/'manifest.json').read_text())
        states = json.loads((args.prior_root/'state.json').read_text())['jobs']
        if any(states.get(j['id'], {}).get('status') not in
               ('completed', 'completed_with_errors', 'failed') for j in manifest['jobs']):
            raise RuntimeError('Prior queue has incomplete jobs; do not overlap')
        break
    result = subprocess.run(['python3', str(args.queue), '--root', str(args.next_root)])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
