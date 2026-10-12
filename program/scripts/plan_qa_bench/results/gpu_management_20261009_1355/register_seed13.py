from pathlib import Path
import subprocess,json,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd();here=Path(__file__).parent
transfer=json.loads((here/'adapter_transfer.json').read_text())
src=(root/'program/scripts/plan_qa_bench/server/queues/refill_finch_additional_20261009.py').read_text(encoding='utf-8').replace('20261012','20261013')
src=src.replace('import copy, hashlib, json, os, shutil, sys','import copy, hashlib, json, os, shutil, sys, fcntl')
src=src.replace("before = path.read_bytes()", "edit=(root/'manifest.edit.lock').open('a');fcntl.flock(edit,fcntl.LOCK_EX)\nlock=(root/'queue.lock').open('a')\ntry:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError:pass\nelse:raise AssertionError('Existing worker must hold queue.lock')\nlock.close()\nbefore = path.read_bytes()")
src=src.replace("'Missing evaluation of completed FINCH learning-rate comparator; fixed developer/regression sets, separate base quantizations; not independent holdout or adoption'", "'Previously unevaluated second independent training seed FINCH comparator; frozen same developer/regression data, two quantizations; estimate seed variation, not independent holdout or adoption'")
src=src.replace("audit = dict(worker_pid=pid,backup=str(backup),added_jobs=jobs,", "audit = dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),worker_pid=pid,worker_lock_held=True,backup=str(backup),added_jobs=jobs,")
with (here/'refill_seed13_remote.py').open('x',encoding='utf-8') as f:f.write(src)
command='python3 - '+transfer['remote']+' '+transfer['sha256']
r=subprocess.run(['ssh','acopilot-gpu',command],input=src.encode(),capture_output=True,check=True)
audit=json.loads(r.stdout)
with (here/'A_seed13_registration.json').open('x',encoding='utf-8') as f:json.dump(audit,f,indent=2)
print(json.dumps({'added_jobs':len(audit['added_jobs']),'added_expected':audit['added_expected'],'worker_pid':audit['worker_pid'],'timestamp':audit['observed_at_utc']}))
