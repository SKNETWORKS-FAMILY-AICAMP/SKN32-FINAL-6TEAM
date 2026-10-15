"""기존 QAT 원본 D와 여행 학습판 D3의 누락 비교만 원자적으로 예약한다."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import shutil

root = Path('/tmp/tripilot-a-backlog-20261008')
path = root/'manifest.json'
before = path.read_bytes()
manifest = json.loads(before)
state = json.loads((root/'state.json').read_text())['jobs']
worker = int((root/'queue.pid').read_text())
assert b'gpu_eval_queue.py' in Path(f'/proc/{worker}/cmdline').read_bytes()
by_id = {j['id']: j for j in manifest['jobs']}
assert len(by_id) == len(manifest['jobs'])
assert state['e4bqat_oos2_h']['status'] == state['e4bqat_oos3_h']['status'] == 'completed'
template = by_id['e4bqat_original_d3']
assert '--lora' in Path(template['script']).read_text()
jobs = []
original = copy.deepcopy(by_id['e4bbase_d'])
original.update(id='e4bqat_original_d', tag='d_backlog_e4bqat_original',
    label=template['label'], model=template['model'], model_sha256=template['model_sha256'],
    publisher_training=template['publisher_training'], our_training=False,
    purpose='Missing original QAT D coverage for matched original-model comparison; existing regression suite, no repeated completed evaluation or product adoption')
original['prompt_sha256'] = hashlib.sha256(Path(original['prompts']).read_bytes()).hexdigest()
assert original['prompt_sha256'] == '7c6836c3ad76eb94f5d3919322a39177f618e813859cd83e7c1ab64bb655c4d0'
jobs.append(original)
for variant in ['oos1', 'oos2', 'oos3', 'oos2r']:
    adapter = by_id[f'e4bqat_{variant}_h']
    job = copy.deepcopy(template)
    job.update(id=f'e4bqat_{variant}_d3', tag=f'd3_backlog_e4bqat_{variant}',
        label=f'Gemma-4-E4B-it QAT Q4_0 with our-travel {variant} adapter',
        our_training=True, lora=adapter['lora'], lora_sha256=adapter['lora_sha256'],
        publisher_training='Google Instruct release and quantization-aware training; our-travel adapter recorded separately',
        purpose='Missing D3 normal-request and no-request coverage on QAT base; diagnose observed mixed-request regression against matched original and Q4_K_M adapters; no repeat or adoption')
    assert hashlib.sha256(Path(job['lora']).read_bytes()).hexdigest() == job['lora_sha256']
    jobs.append(job)
for job in jobs:
    ident = job['id']
    assert ident not in by_id and ident not in state and not (root/ident).exists(), ident
    assert all(Path(job[k]).is_file() for k in ['model', 'script', 'prompts'])
    prompts = Path(job['prompts']).read_bytes()
    assert hashlib.sha256(prompts).hexdigest() == job['prompt_sha256']
    assert len(json.loads(prompts)) == job['expected']
    assert not list(Path('/workspace/heavy').glob('*'+job['tag']+'*.jsonl'))
assert len(jobs) == 5 and sum(j['expected'] for j in jobs) == 4175
assert os.statvfs(root).f_bavail*os.statvfs(root).f_frsize > 3*1024**3
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')+'_qat_choice_refill'
backup = root/'_backup'/stamp/'manifest.json'
backup.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(path, backup)
manifest['jobs'].extend(jobs)
temporary = root/f'manifest.{stamp}.tmp'
with temporary.open('x', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.flush()
    os.fsync(f.fileno())
assert path.read_bytes() == before, 'Concurrent manifest update; do not replace'
os.replace(temporary, path)
audit = dict(worker_pid=worker, backup=str(backup), added_jobs=jobs,
    jobs_registered=len(manifest['jobs']), expected_registered=sum(j['expected'] for j in manifest['jobs']),
    manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    no_worker_restart=True, no_new_model_download=True, model_hash_reverified_this_preflight=False,
    frozen_prompt_hashes_verified=True, adapter_hashes_verified=True,
    no_repeat_of_registered_jobs=True, added_expected_questions=4175)
with (root/(stamp+'_audit.json')).open('x', encoding='utf-8') as f:
    json.dump(audit, f, indent=2)
print(json.dumps(audit))
