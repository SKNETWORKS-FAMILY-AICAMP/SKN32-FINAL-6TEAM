"""기존 A worker에 연결검사와 성공을 기다리는 다섯 본 평가를 원자적으로 등록한다."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

payload = json.load(sys.stdin)
ROOT = Path('/tmp/tripilot-saluki-20261009')
QUEUE = Path('/tmp/tripilot-a-backlog-20261008')
MODEL = Path('/dev/shm/tripilot-saluki-20261009/Underdog-Saluki-27B-1.0-IQ2-mix.gguf')
SHA = '4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb'
download = json.loads((ROOT/'download_state.json').read_text())
assert download['status'] in ['verified', 'already_verified'] and download['sha256'] == SHA
assert MODEL.stat().st_size == 7898369152
assert hashlib.file_digest(MODEL.open('rb'), 'sha256').hexdigest() == SHA
pid = int((QUEUE/'queue.pid').read_text())
os.kill(pid, 0)
assert b'gpu_eval_queue.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
lock = (QUEUE/'queue.lock').open('r')
try:
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:
    pass
else:
    raise AssertionError('Existing worker does not own the GPU queue')
lock.close()

smoke = base64.b64decode(payload['smoke_b64'])
assert hashlib.sha256(smoke).hexdigest() == payload['smoke_sha256']
source = base64.b64decode(payload['runner_b64'])
assert hashlib.sha256(source).hexdigest() == payload['runner_sha256']
compile(source, 'saluki_eval_20261009.py', 'exec')
smoke_path = ROOT/'smoke_prompts_d3_12.json'
runner_path = ROOT/'saluki_eval_20261009.py'
assert not smoke_path.exists() and not runner_path.exists()
canonical = Path('/workspace/heavy/all_prompts_d3.json')
assert hashlib.sha256(canonical.read_bytes()).hexdigest() == payload['canonical_d3_sha256']
original = {r['i']: r for r in json.loads(canonical.read_text())}
smoke_rows = json.loads(smoke)
assert len(smoke_rows) == len({r['i'] for r in smoke_rows}) == 12
assert all(original[r['i']] == r for r in smoke_rows)
assert sum(r['gold'] is not None for r in smoke_rows) == 6
assert sum(r['gold'] is None for r in smoke_rows) == 6
with smoke_path.open('xb') as out:
    out.write(smoke)
with runner_path.open('xb') as out:
    out.write(source)

jobs = []
for suite in ['smoke12', 'd3', 'mx', 'h', 'd', 'd2']:
    if suite == 'smoke12':
        prompts, expected, digest = str(smoke_path), 12, payload['smoke_sha256']
        model = str(MODEL)
        tag = 'saluki_smoke_a1'
    else:
        spec = payload['suites'][suite]
        prompts, expected, digest = spec['path'], spec['expected'], spec['sha256']
        raw = Path(prompts).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert len(json.loads(raw)) == expected
        model = str(ROOT/'smoke_verified_model.gguf')
        tag = 'saluki_original_'+suite+'_a1'
    jobs.append(dict(id='saluki_original_'+suite+'_a1', suite=suite,
                     label='Underdog-Saluki-27B-1.0 IQ2-mix publisher original',
                     our_training=False,
                     publisher_training='Qwen3.8 developer-trained release and publisher GSQ/RCO quantization; no triPilot fine-tuning',
                     model=model, model_sha256=SHA,
                     model_revision='1336c0b5d74dfe6ad7f793577092f5effd9f97c6',
                     prompts=prompts, prompt_sha256=digest, expected=expected,
                     script=str(runner_path), runner_sha256=payload['runner_sha256'],
                     tag=tag, port=8401, logprobs='0' if suite in ['smoke12', 'd3'] else '1',
                     purpose='Connection gate' if suite == 'smoke12' else 'Matched frozen developer/regression suite; not holdout or adoption',
                     dependency=None if suite == 'smoke12' else str(ROOT/'SMOKE_PASS.json'),
                     ephemeral_ram_model=True, automatic_retry=False))

edit = (QUEUE/'manifest.edit.lock').open('a')
fcntl.flock(edit, fcntl.LOCK_EX)
manifest_path = QUEUE/'manifest.json'
old_bytes = manifest_path.read_bytes()
manifest = json.loads(old_bytes)
state = json.loads((QUEUE/'state.json').read_text())['jobs']
old_ids = {j['id'] for j in manifest['jobs']}
assert all(j['id'] not in old_ids and j['id'] not in state and not (QUEUE/j['id']).exists() for j in jobs)
assert not (ROOT/'smoke_verified_model.gguf').exists()
backup = QUEUE/'_backup'/time.strftime('%Y-%m-%d_%H%M%S_saluki_registration', time.gmtime())
backup.mkdir(parents=True)
shutil.copy2(manifest_path, backup/'manifest.json')
manifest['jobs'] = jobs + manifest['jobs']
temp = manifest_path.with_name('manifest.saluki.tmp')
with temp.open('x') as out:
    json.dump(manifest, out, indent=2)
assert manifest_path.read_bytes() == old_bytes, 'Concurrent manifest changed; preserve and rebase'
temp.replace(manifest_path)
audit = dict(timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             worker_pid=pid, existing_worker_preserved=True, current_job_not_interrupted=True,
             model_sha256=SHA, whole_model_sha_verified=True,
             canonical_smoke_ids_gold_type_prompt_match=[12,12],
             smoke_registered=1, main_conditionally_registered=5,
             main_expected=9425, priority=['smoke12','d3','mx','h','d','d2'],
             model_gate='Five main job model paths remain missing until 12/12 parsed smoke and 0 API errors create success symlink',
             backup=str(backup/'manifest.json'), jobs=jobs,
             manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
with (ROOT/'queue_registration.json').open('x') as out:
    json.dump(audit, out, indent=2)
print(json.dumps(audit))
