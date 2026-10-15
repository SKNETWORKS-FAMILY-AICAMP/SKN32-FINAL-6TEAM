"""기존 여행 입력의 누락 복수 항목 역할을 기존 worker 대기열에 보충한다."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil


root = Path('/tmp/tripilot-a-backlog-20261008')
path = root / 'manifest.json'; before = path.read_bytes(); manifest = json.loads(before)
state = json.loads((root/'state.json').read_text())['jobs']
pid = int((root/'queue.pid').read_text()); assert b'gpu_eval_queue.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
assert os.statvfs(root).f_bavail*os.statvfs(root).f_frsize > 3*2**30
prep = Path('/tmp/tripilot-multi-items-20261009')
prompt = prep/'prompts.json'; script = prep/'multi_items_eval_20261009.py'
rows = json.loads(prompt.read_text()); assert len(rows) == 835 and len({x['i'] for x in rows}) == 835
assert sum(len(x['gold_set']) == 2 for x in rows) == 66
assert sum(len(x['gold_set']) == 0 for x in rows) == 186
prompt_sha = hashlib.sha256(prompt.read_bytes()).hexdigest(); runner_sha = hashlib.sha256(script.read_bytes()).hexdigest()
by_id = {j['id']: j for j in manifest['jobs']}; added=[]; hashes={}
sources=['e4bbase_d','e4bqat_original_d','e4bbase_cosine_s20261012_d','e4bqat_cosine_s20261012_d','e4bbase_finch_s20261012_d','e4bqat_finch_s20261012_d']
for source in sources:
    old = by_id[source]; assert state[source]['status'].startswith('completed')
    for key in ['model','lora']:
        if not old.get(key): continue
        p = Path(old[key]); assert p.is_file()
        if str(p) not in hashes:
            with p.open('rb') as f: hashes[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
        expected = old.get(key+'_sha256') or p.name.removeprefix('sha256-')
        assert hashes[str(p)] == expected, (source,key)
    job = copy.deepcopy(old); ident=source.removesuffix('_d')+'_multi_items_bc_a1'
    assert ident not in by_id and ident not in state and not (root/ident).exists()
    job.update(id=ident,tag=ident,suite='multi_items_bc',prompts=str(prompt),script=str(script),expected=835,prompt_sha256=prompt_sha,runner_sha256=runner_sha,output_contract='strict items array with 64 output tokens; separately scored B and C',role='missing multi-item response contract; same existing travel fixture; not prior D/E or independent holdout',automatic_retry=False)
    added.append(job)
assert len(added) == 6
stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')+'_multi_items_role'
backup = root/'_backup'/stamp/'manifest.json'; backup.parent.mkdir(parents=True,exist_ok=False); shutil.copy2(path,backup)
manifest['jobs'].extend(added); temp=root/f'manifest.{stamp}.tmp'
with temp.open('x') as f:json.dump(manifest,f,indent=2);f.flush();os.fsync(f.fileno())
assert path.read_bytes() == before, 'Concurrent modification';os.replace(temp,path)
audit=dict(worker_pid=pid,no_worker_restart=True,backup=str(backup),added_jobs=added,added_expected=5010,jobs_registered=len(manifest['jobs']),prompt_sha256=prompt_sha,runner_sha256=runner_sha,whole_model_adapter_hashes=hashes,no_new_download=True,manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
with (prep/'registration_audit.json').open('x') as f:json.dump(audit,f,indent=2)
print(json.dumps(audit))
