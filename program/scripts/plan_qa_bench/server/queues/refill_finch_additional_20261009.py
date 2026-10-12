"""완료된 새 finch 여행 어댑터의 미실행 추가 평가를 기존 실행기에 보충한다."""
from pathlib import Path
from datetime import datetime, timezone
import copy, hashlib, json, os, shutil, sys
sys.path.insert(0, '/workspace/deciders/llama.cpp/gguf-py')
from gguf import GGUFReader

root = Path('/tmp/tripilot-a-backlog-20261008')
path = root / 'manifest.json'
before = path.read_bytes()
manifest = json.loads(before)
state = json.loads((root / 'state.json').read_text())['jobs']
pid = int((root / 'queue.pid').read_text())
assert b'gpu_eval_queue.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
adapter = Path(sys.argv[1]); digest = sys.argv[2]
assert hashlib.sha256(adapter.read_bytes()).hexdigest() == digest
by_id = {j['id']: j for j in manifest['jobs']}
model_digests = {}
for ident in ['e4bbase_h', 'e4bqat_original_h']:
    model = Path(by_id[ident]['model'])
    digest_model = hashlib.sha256()
    with model.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            digest_model.update(block)
    actual = digest_model.hexdigest()
    assert actual == model.name.removeprefix('sha256-')
    model_digests[str(model)] = actual
reference = GGUFReader(by_id['e4bqat_oos1_h']['lora'])
sig = lambda r: [(t.name, t.shape.tolist(), int(t.tensor_type)) for t in r.tensors]
assert sig(reference) == sig(GGUFReader(str(adapter)))
assert os.statvfs(root).f_bavail * os.statvfs(root).f_frsize > 3 * 2**30
jobs = []
for suite in ['d3', 'd', 'd2', 'h', 'mx']:
    for family, original in [('e4bbase', 'e4bbase'), ('e4bqat', 'e4bqat_original')]:
        source = by_id[f'{original}_{suite}']
        assert state[source['id']]['status'].startswith('completed')
        ident = f'{family}_finch_s20261012_{suite}'
        assert ident not in by_id and ident not in state and not (root/ident).exists()
        job = copy.deepcopy(source)
        job['prompt_sha256'] = by_id[f'e4bqat_original_{suite}']['prompt_sha256']
        job['model_sha256'] = model_digests[job['model']]
        job.update(id=ident, tag=f'{suite}_backlog_{family}_finch_s20261012',
            lora=str(adapter), lora_sha256=digest, our_training=True,
            label=f"Gemma-4-E4B-it {'QAT Q4_0' if family=='e4bqat' else 'Q4_K_M'} with our-travel finch 5e-5 seed20261012 adapter",
            publisher_training='Google Instruct release; QAT only when QAT base is used; our travel finch adapter learned separately',
            purpose='Missing evaluation of completed FINCH learning-rate comparator; fixed developer/regression sets, separate base quantizations; not independent holdout or adoption')
        assert all(Path(job[k]).is_file() for k in ['model','prompts','script','lora'])
        data = Path(job['prompts']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == job['prompt_sha256']
        assert len(json.loads(data)) == job['expected']
        assert '--lora' in Path(job['script']).read_text()
        jobs.append(job)
assert len(jobs) == 10 and sum(j['expected'] for j in jobs) == 18850
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')+'_finch_additional'
backup = root/'_backup'/stamp/'manifest.json'
backup.parent.mkdir(parents=True, exist_ok=False); shutil.copy2(path, backup)
manifest['jobs'].extend(jobs)
temp = root/f'manifest.{stamp}.tmp'
with temp.open('x',encoding='utf-8') as f:
    json.dump(manifest,f,indent=2); f.flush(); os.fsync(f.fileno())
assert path.read_bytes() == before, 'Concurrent manifest change'
os.replace(temp,path)
audit = dict(worker_pid=pid,backup=str(backup),added_jobs=jobs,
    jobs_registered=len(manifest['jobs']),added_expected=18850,
    adapter_sha256=digest,adapter_tensor_structure_match=True,
    no_worker_restart=True,no_model_download=True,model_whole_hash_reverified=True,
    manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
with (root/(stamp+'_audit.json')).open('x') as f: json.dump(audit,f,indent=2)
print(json.dumps(audit))
