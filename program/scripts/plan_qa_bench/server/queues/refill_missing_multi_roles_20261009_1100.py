"""기보관 원본·학습판의 누락 복수 항목 역할만 기존 worker에 보충한다."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import fcntl
import hashlib
import json
import os
import shutil

root=Path('/tmp/tripilot-a-backlog-20261008')
path=root/'manifest.json'
pid=int((root/'queue.pid').read_text())
assert b'gpu_eval_queue.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
worker_lock=(root/'queue.lock').open('a')
try:fcntl.flock(worker_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:pass
else:raise AssertionError('The existing worker must own the GPU queue')
worker_lock.close()
space=os.statvfs(root).f_bavail*os.statvfs(root).f_frsize
assert space>3*2**30+100*2**20, 'Preserve space reserve and answer growth'
edit=(root/'manifest.edit.lock').open('a');fcntl.flock(edit,fcntl.LOCK_EX)
before=path.read_bytes();manifest=json.loads(before);state=json.loads((root/'state.json').read_text())['jobs']
by_id={j['id']:j for j in manifest['jobs']}
reference=by_id['e4bbase_multi_items_bc_a1']
prompts=Path(reference['prompts']);runner=Path(reference['script'])
assert state[reference['id']]['status'].startswith('completed')
assert hashlib.sha256(prompts.read_bytes()).hexdigest()==reference['prompt_sha256']
assert hashlib.sha256(runner.read_bytes()).hexdigest()==reference['runner_sha256']
rows=json.loads(prompts.read_text());assert len(rows)==len({r['i'] for r in rows})==835
assert sum(len(r['gold_set'])==2 for r in rows)==66
hashes={};sources=['g12bbase_d','winnow_original_d','winnow_oos_d'];jobs=[];compat=[]
for source in sources:
    old=by_id[source];assert state[source]['status'].startswith('completed')
    ident=source.removesuffix('_d')+'_multi_items_bc_a1'
    assert ident not in by_id and ident not in state and not (root/ident).exists()
    # Reject an existing role under a different ID as well as exact duplicate IDs.
    assert not any(j.get('suite')=='multi_items_bc' and j['model']==old['model'] and j.get('lora','')==old.get('lora','') for j in manifest['jobs'])
    for key in ['model','lora']:
        if not old.get(key):continue
        p=Path(old[key]);assert p.is_file();stat=p.stat()
        if str(p) not in hashes:
            with p.open('rb') as f:hashes[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
        assert p.stat().st_size==stat.st_size and p.stat().st_mtime_ns==stat.st_mtime_ns
        expected=old.get(key+'_sha256') or (old.get('adapter_sha256') if key=='lora' else (p.name.removeprefix('sha256-') if p.name.startswith('sha256-') else None))
        if expected:assert hashes[str(p)]==expected,(source,key)
    job=copy.deepcopy(old)
    job.update(id=ident,tag=ident,suite='multi_items_bc',prompts=str(prompts),script=str(runner),expected=835,
        prompt_sha256=reference['prompt_sha256'],runner_sha256=reference['runner_sha256'],
        model_sha256=hashes[old['model']],logprobs='0',
        output_contract='Strict items array; same itinerary/question/information; max_tokens64; fixed single/no-request/compound denominators',
        role='Previously missing multi-item B/C role; not a rerun of completed single-item D/E and not independent holdout',
        automatic_retry=False,comparison_runs=1)
    if old.get('lora'):job['lora_sha256']=hashes[old['lora']]
    if source=='g12bbase_d':job['publisher_training']='Google Instruct release; no guguroute fine-tuning'
    jobs.append(job);compat.append(dict(source_job=source,source_state=state[source],new_id=ident,
        existing_base_and_adapter_engine_execution=True,new_multi_output_accuracy_unmeasured=True))
stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')+'_missing_multi_role_refill'
backup=root/'_backup'/stamp/'manifest.json';backup.parent.mkdir(parents=True,exist_ok=False);shutil.copy2(path,backup)
manifest['jobs'].extend(jobs);temp=root/('manifest.'+stamp+'.tmp')
with temp.open('x') as f:json.dump(manifest,f,indent=2);f.flush();os.fsync(f.fileno())
assert path.read_bytes()==before,'Concurrent manifest edit';os.replace(temp,path)
audit=dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),worker_pid=pid,
    existing_worker_preserved=True,worker_lock_held=True,new_GPU_worker=False,no_new_download=True,
    free_bytes_before=space,registered_jobs=3,registered_questions=2505,missing_roles_checked=3,
    missing_role_sources=compat,whole_model_adapter_SHA256=hashes,backup=str(backup),
    manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),jobs=jobs,
    failures_or_missing_excluded_from_denominator=False,old_completed_tasks_repeated=False,
    native_Valen_not_treated_as_multi_item=True)
with (root/(stamp+'_audit.json')).open('x') as f:json.dump(audit,f,indent=2)
print(json.dumps(audit))
