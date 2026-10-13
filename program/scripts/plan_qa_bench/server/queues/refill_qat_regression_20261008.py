"""QAT 여행 학습판의 아직 실행하지 않은 D/D2 비교를 기존 실행기에 예약한다."""
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
assert state['e4bqat_original_d']['status'].startswith('completed')
assert state['e4bqat_oos2r_mx']['status'] == 'completed'
references = {
    'd': ('e4bqat_original_d', 2735, '7c6836c3ad76eb94f5d3919322a39177f618e813859cd83e7c1ab64bb655c4d0'),
    'd2': ('e4bqat_original_d2', 1000, '252ba43c0089031031876a02e0e9a66fe3589f4d3ccb56022d09bfb74c8657b7'),
}
jobs = []
for variant in ['oos1', 'oos2', 'oos3', 'oos2r']:
    adapter = by_id[f'e4bqat_{variant}_h']
    assert hashlib.sha256(Path(adapter['lora']).read_bytes()).hexdigest() == adapter['lora_sha256']
    for suite, (reference, expected, prompt_hash) in references.items():
        job = copy.deepcopy(by_id[reference])
        assert '--lora' in Path(job['script']).read_text()
        job.update(id=f'e4bqat_{variant}_{suite}', tag=f'{suite}_backlog_e4bqat_{variant}',
            label=f'Gemma-4-E4B-it QAT Q4_0 with our-travel {variant} adapter',
            our_training=True, lora=adapter['lora'], lora_sha256=adapter['lora_sha256'],
            publisher_training='Google Instruct release and quantization-aware training; our-travel adapter recorded separately',
            purpose='Missing matched QAT D/D2 normal-request and no-selection regression coverage; diagnose H improvement versus mixed-request retention losses; retain compound diagnostic separately; no repeats or adoption')
        job['prompt_sha256'] = prompt_hash
        assert job['expected'] == expected
        ident = job['id']
        assert ident not in by_id and ident not in state and not (root/ident).exists(), ident
        assert all(Path(job[k]).is_file() for k in ['model', 'script', 'prompts', 'lora'])
        prompts = Path(job['prompts']).read_bytes()
        assert hashlib.sha256(prompts).hexdigest() == prompt_hash and len(json.loads(prompts)) == expected
        assert not list(Path('/workspace/heavy').glob('*'+job['tag']+'*.jsonl'))
        jobs.append(job)
assert len(jobs) == 8 and sum(j['expected'] for j in jobs) == 14940
assert os.statvfs(root).f_bavail*os.statvfs(root).f_frsize > 3*1024**3
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')+'_qat_regression_refill'
backup = root/'_backup'/stamp/'manifest.json'
backup.parent.mkdir(parents=True, exist_ok=False)
shutil.copy2(path, backup)
manifest['jobs'].extend(jobs)
temporary = root/f'manifest.{stamp}.tmp'
with temporary.open('x', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.flush()
    os.fsync(f.fileno())
assert path.read_bytes() == before, 'Concurrent manifest change; do not replace'
os.replace(temporary, path)
audit = dict(worker_pid=worker, backup=str(backup), added_jobs=jobs,
    jobs_registered=len(manifest['jobs']), expected_registered=sum(j['expected'] for j in manifest['jobs']),
    manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), no_worker_restart=True,
    no_new_model_download=True, model_hash_reverified_this_preflight=False,
    frozen_prompt_hashes_verified=True, adapter_hashes_verified=True,
    no_repeat_of_registered_jobs=True, added_expected_questions=14940)
with (root/(stamp+'_audit.json')).open('x', encoding='utf-8') as f:
    json.dump(audit, f, indent=2)
print(json.dumps(audit))
