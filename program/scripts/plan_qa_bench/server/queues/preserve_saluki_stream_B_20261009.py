"""검증된 A RAM 모델을 stdin으로 받아 B 기존 디스크에 보관한다. GPU를 사용하지 않는다."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path('/root/saluki_original_20261009')
SIZE = 7898369152
SHA = '4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb'
MODEL = ROOT/'Underdog-Saluki-27B-1.0-IQ2-mix.gguf'


def memory():
    p = Path('/sys/fs/cgroup/memory')
    limit = int((p/'memory.limit_in_bytes').read_text())
    used = int((p/'memory.usage_in_bytes').read_text())
    return dict(limit=limit, used=used, headroom=limit-used)


def state(status, **values):
    p = ROOT/'preservation_state.json'
    record = dict(status=status, pid=os.getpid(), timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  expected=SIZE, expected_sha256=SHA, memory=memory(), GPU_used=False,
                  source='Verified A RAM file; no second upstream download',
                  storage='Existing B root disk; not a local off-machine permanent backup', **values)
    if p.exists():
        backup = ROOT/'_backup/preservation_history'
        backup.mkdir(parents=True, exist_ok=True)
        (backup/f'{time.time_ns()}.json').write_bytes(p.read_bytes())
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(record, indent=2))
    temp.replace(p)


def main():
    ROOT.mkdir(exist_ok=True)
    lock = (ROOT/'preservation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert not MODEL.exists(), 'Existing copy must be verified, not overwritten'
    part = MODEL.with_suffix('.gguf.part')
    assert not part.exists(), 'Preserve partial transfer; explicit byte-offset resume required'
    free = os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
    assert free >= SIZE + 6*1024**3, 'Reserve 3GiB plus queued training/output growth'
    assert memory()['headroom'] >= 4*1024**3
    assert hasattr(os, 'posix_fadvise'), 'Bound the new file cache, preserving current training memory'
    count = 0
    digest = hashlib.sha256()
    flushed = 0
    last = 0
    state('receiving', saved=0, initial_disk_free=free)
    with part.open('xb') as output:
        while True:
            if memory()['headroom'] < 3*1024**3:
                state('paused_for_training_memory', saved=count)
                time.sleep(10)
                continue
            block = sys.stdin.buffer.read(4*1024**2)
            if not block:
                break
            output.write(block)
            digest.update(block)
            count += len(block)
            if count-flushed >= 128*1024**2:
                output.flush()
                os.fdatasync(output.fileno())
                os.posix_fadvise(output.fileno(), flushed, count-flushed, os.POSIX_FADV_DONTNEED)
                flushed = count
            if time.monotonic()-last >= 10:
                state('receiving', saved=count)
                last = time.monotonic()
        output.flush()
        os.fsync(output.fileno())
        os.posix_fadvise(output.fileno(), 0, count, os.POSIX_FADV_DONTNEED)
    assert count == SIZE and digest.hexdigest() == SHA, 'Preserve incomplete or mismatched transfer'
    part.replace(MODEL)
    state('verified', saved=count, sha256=digest.hexdigest())
    print(json.dumps(dict(saved=count, expected=SIZE, sha256=digest.hexdigest(), model=str(MODEL))), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if ROOT.exists():
            state('failed_preserved', error=repr(exc))
        raise
