"""고정 Saluki 텍스트 가중치를 기존 RAM 임시 공간에 받는다. GPU를 사용하지 않는다."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path('/tmp/tripilot-saluki-20261009')
RAM = Path('/dev/shm/tripilot-saluki-20261009')
FILE = 'Underdog-Saluki-27B-1.0-IQ2-mix.gguf'
SIZE = 7898369152
SHA = '4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb'
REVISION = '1336c0b5d74dfe6ad7f793577092f5effd9f97c6'
URL = f'https://huggingface.co/ConwayResearch/Underdog-Saluki-27B-1.0/resolve/{REVISION}/{FILE}'


def memory():
    base = Path('/sys/fs/cgroup/memory')
    limit = int((base/'memory.limit_in_bytes').read_text())
    used = int((base/'memory.usage_in_bytes').read_text())
    host = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return dict(cgroup_limit=limit, cgroup_used=used, cgroup_headroom=limit-used,
                host_available=int(host['MemAvailable'].strip().split()[0])*1024)


def save(status, **values):
    data = dict(status=status, timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                revision=REVISION, expected_bytes=SIZE, expected_sha256=SHA,
                model_path=str(RAM/FILE), ephemeral_ram_storage=True, GPU_used=False,
                memory=memory(), **values)
    p = ROOT/'download_state.json'
    if p.exists():
        old = ROOT/'_backup/download_state_history'
        old.mkdir(parents=True, exist_ok=True)
        (old/f'{time.time_ns()}.json').write_bytes(p.read_bytes())
    temp = p.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.replace(p)
    print(json.dumps(data), flush=True)


def main():
    ROOT.mkdir(exist_ok=True)
    RAM.mkdir(exist_ok=True)
    lock = (ROOT/'download.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('DOWNLOAD_ALREADY_RUNNING', flush=True)
        return
    target = RAM/FILE
    if target.exists():
        assert target.stat().st_size == SIZE
        assert hashlib.file_digest(target.open('rb'), 'sha256').hexdigest() == SHA
        save('already_verified', bytes_saved=SIZE, sha256=SHA)
        return
    part = target.with_suffix('.gguf.part')
    assert not part.exists(), 'Preserve partial file; explicit resume required'
    free = os.statvfs(RAM).f_bavail*os.statvfs(RAM).f_frsize
    m = memory()
    assert free >= SIZE + 3*1024**3, 'RAM filesystem safety reserve'
    assert m['cgroup_headroom'] >= SIZE + 6*1024**3, 'Do not pressure existing GPU evaluation'
    assert m['host_available'] >= SIZE + 16*1024**3
    assert os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize >= 3*1024**3
    with (ROOT/'write_probe.txt').open('x') as f:
        f.write('Existing writable root; no storage rental or mount change.\n')
    save('downloading', bytes_saved=0, initial_ram_filesystem_free=free)
    start = time.monotonic()
    last = 0
    size = 0
    digest = hashlib.sha256()
    with urllib.request.urlopen(URL, timeout=120) as response, part.open('xb') as out:
        assert int(response.headers['Content-Length']) == SIZE
        while True:
            m = memory()
            if m['cgroup_headroom'] < 4*1024**3 or m['host_available'] < 16*1024**3:
                save('paused_for_existing_workload_memory', bytes_saved=size)
                time.sleep(10)
                continue
            block = response.read(4*1024**2)
            if not block:
                break
            out.write(block)
            digest.update(block)
            size += len(block)
            elapsed = time.monotonic()-start
            if elapsed-last >= 10:
                out.flush()
                save('downloading', bytes_saved=size, elapsed_seconds=round(elapsed, 2))
                last = elapsed
            # CPU/network preparation must leave room for the running evaluation.
            if elapsed < size/(50*1024**2):
                time.sleep(size/(50*1024**2)-elapsed)
        out.flush()
        os.fsync(out.fileno())
    assert size == SIZE and digest.hexdigest() == SHA, 'Preserve mismatched partial file'
    part.replace(target)
    save('verified', bytes_saved=size, sha256=digest.hexdigest(),
         elapsed_seconds=round(time.monotonic()-start, 2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if ROOT.exists():
            save('failed_preserved', error=repr(exc))
        raise
