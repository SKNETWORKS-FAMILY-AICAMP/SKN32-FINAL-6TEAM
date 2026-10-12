"""기존 학습 어댑터의 QAT 기반 누락 H/MX만 구조 확인 뒤 원자적으로 예약한다."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, '/workspace/deciders/llama.cpp/gguf-py')
from gguf import GGUFReader

root = Path('/tmp/tripilot-a-backlog-20261008')
manifest_path = root/'manifest.json'
manifest = json.loads(manifest_path.read_text())
state = json.loads((root/'state.json').read_text())['jobs']
pid = int((root/'queue.pid').read_text())
assert Path(f'/proc/{pid}/cmdline').exists()
assert b'gpu_eval_queue.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
templates = {suite: next(j for j in manifest['jobs'] if j['id'] == 'e4bqat_oos1_'+suite) for suite in ['h','mx']}
reference = GGUFReader(templates['h']['lora'])
signature = [(t.name, t.shape.tolist(), int(t.tensor_type)) for t in reference.tensors]
assert signature and state['e4bqat_oos1_h']['status'] == 'completed'
paths = {
    'oos2': '/workspace/tripilot/oos2_lora_f16.gguf',
    'oos3': '/tmp/tripilot-oos3-eval/oos3_lora_f16.gguf',
    'oos2r': '/tmp/tripilot-oos2r-eval/oos2r_lora_f16.gguf',
}
audit = {'worker_pid': pid, 'reference_adapter': templates['h']['lora'],
         'reference_successful_h': state['e4bqat_oos1_h'], 'adapters': {}, 'jobs_added': []}
new_jobs = []
for variant, source in paths.items():
    path = Path(source)
    reader = GGUFReader(source)
    actual = [(t.name, t.shape.tolist(), int(t.tensor_type)) for t in reader.tensors]
    assert actual == signature, variant
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    audit['adapters'][variant] = {'sha256': sha, 'bytes': path.stat().st_size,
                                 'same_tensor_names_shapes_types_as_successful_oos1': True,
                                 'tensors': len(actual), 'engine_smoke_for_this_variant': False}
    for suite in ['h','mx']:
        ident = f'e4bqat_{variant}_{suite}'
        assert not any(j['id'] == ident for j in manifest['jobs']), ident
        assert ident not in state and not (root/ident).exists(), ident
        # 별도 옛 실행 위치에 같은 QAT 판의 답안이 있으면 자동 예약하지 않는다.
        assert not list(Path('/workspace/heavy').glob(f'*qat*{variant}*.jsonl')), variant
        job = copy.deepcopy(templates[suite])
        job.update(id=ident, tag=f'{suite}_backlog_e4bqat_{variant}', lora=source,
            lora_sha256=sha, our_training=True,
            label=f'Gemma-4-E4B-it QAT Q4_0 with our-travel {variant} adapter',
            publisher_training='Google Instruct release and quantization-aware training; our-travel adapter recorded separately',
            purpose='Missing QAT H/MX coverage of preserved travel adapter; compare false selections and normal-request retention with matched QAT original and completed Q4_K_M version; existing regression data, no adoption from one run')
        assert all(Path(job[k]).is_file() for k in ['model','prompts','script','lora'])
        assert hashlib.sha256(Path(job['prompts']).read_bytes()).hexdigest() == job['prompt_sha256']
        new_jobs.append(job)
        audit['jobs_added'].append({'id': ident, 'expected': job['expected'], 'our_training': True})
assert len(new_jobs) == 6
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')+'_qat_adapter_refill'
backup = root/'_backup'/stamp/'manifest.json'
backup.parent.mkdir(parents=True)
shutil.copy2(manifest_path, backup)
before_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
manifest['jobs'].extend(new_jobs)
temporary = root/f'manifest.{stamp}.tmp'
with temporary.open('x', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.flush()
    os.fsync(f.fileno())
assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == before_hash
os.replace(temporary, manifest_path)
audit.update(backup=str(backup), jobs_registered=len(manifest['jobs']),
             expected_registered=sum(j['expected'] for j in manifest['jobs']),
             manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
             no_worker_restart=True, no_new_model_download=True,
             no_repetition_of_completed_qat_jobs=True)
with (root/(stamp+'_audit.json')).open('x', encoding='utf-8') as f:
    json.dump(audit, f, indent=2)
print(json.dumps(audit))
