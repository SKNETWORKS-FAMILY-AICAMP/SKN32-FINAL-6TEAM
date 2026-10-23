"""검토된 고정 원본만 중복 캐시 없이 보관한다. GPU는 사용하지 않는다."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from huggingface_hub import snapshot_download

ROOT = Path('/tmp/tripilot-valen-20261009')
ROOT.mkdir(exist_ok=True)
lock = (ROOT/'download.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
spec = json.load(sys.stdin)
target = ROOT/'model'
weight_size = 3417285852
def free():
    s = os.statvfs(ROOT)
    return s.f_bavail*s.f_frsize
assert not (ROOT/'download_verified.json').exists(), 'Verified original already exists; no duplicate download'
assert free() >= weight_size + 3*2**30 + 150*2**20, 'Preserve disk reserve including tokenizer/code/outputs'
os.environ['HF_XET_CACHE'] = str(ROOT/'xet')
os.environ['HF_XET_CHUNK_CACHE_SIZE_BYTES'] = '0'
files = [x['name'] for x in spec['metadata_files']] + ['model.safetensors','tokenizer.json','tokenizer_config.json','processor_config.json','chat_template.jinja']
before = free()
print('DOWNLOAD_START', before, flush=True)
snapshot_download(repo_id=spec['repo_id'], revision=spec['revision'], local_dir=target,
                  allow_patterns=files, max_workers=2)
hashes = {}
for name in files:
    p = target/name
    with p.open('rb') as f:
        hashes[name] = hashlib.file_digest(f,'sha256').hexdigest()
for file in spec['metadata_files']:
    assert hashes[file['name']] == file['sha256'], file['name']
weight = spec['weights'][0]
assert (target/weight['name']).stat().st_size == weight['bytes']
assert hashes[weight['name']] == weight['lfs']['sha256']
assert free() > 3*2**30
result = dict(verified_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
              revision=spec['revision'], repo_id=spec['repo_id'], hashes=hashes,
              free_before=before, free_after=free(), weight_bytes=weight_size,
              our_training=False, no_GPU_used=True, local_dir=str(target),
              duplicate_weight_cache=False, status='verified')
with (ROOT/'download_verified.json').open('x') as f:
    json.dump(result,f,indent=2)
print(json.dumps(result),flush=True)
