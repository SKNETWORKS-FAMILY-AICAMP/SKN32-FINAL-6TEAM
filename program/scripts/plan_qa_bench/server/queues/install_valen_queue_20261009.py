"""고정 Valen 연결검사와 성공을 기다리는 본 평가를 기존 worker에 등록한다."""
from pathlib import Path
import fcntl
import hashlib
import json
import os
import shutil
import time

ROOT=Path('/tmp/tripilot-valen-20261009')
QUEUE=Path('/tmp/tripilot-a-backlog-20261008')
manifest_path=QUEUE/'manifest.json'
pid=int((QUEUE/'queue.pid').read_text())
assert b'gpu_eval_queue.py' in Path(f'/proc/{pid}/cmdline').read_bytes()
probe=(QUEUE/'queue.lock').open('a')
try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:pass
else:raise AssertionError('Existing worker must own the queue')
probe.close()
verified=json.loads((ROOT/'download_verified.json').read_text())
assert verified['status']=='verified'
assert json.loads((ROOT/'cpu_preflight.json').read_text())['compiled']==12
assert os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize>3*2**30
runner=ROOT/'valen_native_eval_20261009.py'
compile(runner.read_text(),'valen_native_eval_20261009.py','exec')
contract=json.loads((ROOT/'prompts/contract.json').read_text())
jobs=[]
for suite in ['smoke12','d3','mx','h','d','d2']:
    prompts=ROOT/'prompts'/(suite+'.json')
    spec=contract['suites'][suite]
    assert hashlib.sha256(prompts.read_bytes()).hexdigest()==spec['prompt_sha256']
    assert len(json.loads(prompts.read_text()))==spec['expected']
    model=ROOT/('model/model.safetensors' if suite=='smoke12' else 'smoke_verified_model.safetensors')
    job=dict(id='valen_08b_original_'+suite+'_a1',tag='valen_08b_original_'+suite+'_a1',
        suite=suite, label='Valen-0.8B native decision head publisher original', our_training=False,
        publisher_training='Developer full decision SFT on Qwen3.5-0.8B',
        model=str(model),model_sha256=verified['hashes']['model.safetensors'],model_revision=verified['revision'],
        prompts=str(prompts),prompt_sha256=spec['prompt_sha256'],expected=spec['expected'],
        script=str(runner),runner_sha256=hashlib.sha256(runner.read_bytes()).hexdigest(),port=8401,logprobs='0',
        output_contract='Native choice-head distribution; parsed validates API, content holds native response',
        dependency=None if suite=='smoke12' else str(ROOT/'SMOKE_PASS.json'),
        automatic_retry=False,purpose='Connection gate' if suite=='smoke12' else 'Frozen original travel regression; not holdout or adoption')
    jobs.append(job)
edit=(QUEUE/'manifest.edit.lock').open('a');fcntl.flock(edit,fcntl.LOCK_EX)
before=manifest_path.read_bytes();manifest=json.loads(before)
state=json.loads((QUEUE/'state.json').read_text())['jobs'];old={j['id'] for j in manifest['jobs']}
assert all(j['id'] not in old and j['id'] not in state and not (QUEUE/j['id']).exists() for j in jobs)
backup=QUEUE/'_backup'/time.strftime('%Y-%m-%d_%H%M%S_valen_registration',time.gmtime());backup.mkdir(parents=True,exist_ok=False)
shutil.copy2(manifest_path,backup/'manifest.json')
# Current child continues; the next idle GPU runs connection then gated original comparison.
manifest['jobs']=jobs+manifest['jobs'];temporary=QUEUE/'manifest.valen.tmp'
with temporary.open('x') as f:json.dump(manifest,f,indent=2);f.flush();os.fsync(f.fileno())
assert manifest_path.read_bytes()==before;os.replace(temporary,manifest_path)
audit=dict(timestamp_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),worker_pid=pid,
    worker_preserved=True,current_child_preserved=True,smoke_registered=1,main_conditionally_registered=5,
    main_expected=9425,smoke_expected=12,priority=['smoke12','d3','mx','h','d','d2'],
    backup=str(backup/'manifest.json'),model_sha256=verified['hashes']['model.safetensors'],
    manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),jobs=jobs,
    gated_main_model_path_missing=not (ROOT/'smoke_verified_model.safetensors').exists())
with (ROOT/'registration_audit.json').open('x') as f:json.dump(audit,f,indent=2)
print(json.dumps(audit))
