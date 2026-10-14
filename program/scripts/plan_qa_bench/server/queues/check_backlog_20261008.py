"""승인된 GPU 기계의 대기열 상태를 읽기만 한다."""
import json
import os
import pathlib
import re
import subprocess
import sys

machine = sys.argv[1]
report = {"machine": machine}
if machine == 'A':
    root = pathlib.Path('/tmp/tripilot-a-backlog-20261008')
    report['manifest'] = json.loads((root / 'manifest.json').read_text())
    report['state'] = json.loads((root / 'state.json').read_text())
    report['queue_log_tail'] = (root / 'queue.log').read_text()[-3000:]
    report['worker_pid'] = int((root / 'queue.pid').read_text())
    report['answers'] = {str(p.relative_to(root)): sum(1 for _ in p.open())
                         for p in root.glob('*/*.jsonl')}
    report['processes'] = subprocess.getoutput('ps -eo pid,ppid,etimes,args | grep -E "gpu_eval_queue.py|d_test_llama_lp.py|llama-server"')
else:
    report['choice'] = pathlib.Path('/root/train_choice.txt').read_text()
    report['processes'] = subprocess.getoutput('ps -eo pid,ppid,etimes,args | grep -E "run_B54|run_B56|run_B57|run_B58|qlora_train|qlora_eval|run_candidate"')
    active_matches = list(re.finditer(r'^\s*(\d+)\s+\d+\s+\d+\s+.*?\b(qlora_train(?:2|_finch)?\.py)\s+\S+\s+\S+\s+/root/adapters/([^\s]+)', report['processes'], re.MULTILINE))
    active = [m.group(3) for m in active_matches]
    report['active_training_variants'] = sorted(set(active))
    report['active_training_log'] = ('/root/qlora_train_' + active[0] + '.log') if len(set(active)) == 1 else None
    if len(active_matches) == 1 and active_matches[0].group(2) == 'qlora_train_finch.py':
        pid = active_matches[0].group(1)
        mode = active[0].split('_')[1]
        report['active_training_log'] = str(pathlib.Path(os.readlink('/proc/' + pid + '/cwd')) / ('train_' + mode + '.log'))
    report['logs'] = {}
    log_paths = [pathlib.Path('/root/run_B31.log'), pathlib.Path('/root/qlora_train_winnow_e4b_oos.log'),
                 pathlib.Path('/root/daily_rag_repeat_20261008/status.log')]
    if report['active_training_log']:
        log_paths.append(pathlib.Path(report['active_training_log']))
    for p in log_paths:
        if p.exists():
            report['logs'][str(p)] = p.read_text(errors='replace')[-5000:]
if machine == 'B':
    native = pathlib.Path('/root/hf_nf4_contract_20261010')
    if (native/'state.json').exists():
        import fcntl
        native_state = json.loads((native/'state.json').read_text())
        native_manifest = json.loads((native/'manifest.json').read_text())
        native_pid = int((native/'queue.pid').read_text())
        native_lock = (native/'queue.lock').open('a')
        try:
            fcntl.flock(native_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_held = False
        except BlockingIOError:
            lock_held = True
        native_lock.close()
        report['native_condition_queue'] = dict(state=native_state,
            worker_pid=native_pid, worker_alive=pathlib.Path(f'/proc/{native_pid}').exists(),
            lock_held=lock_held, manifest=native_manifest,
            saved={ident:sum(1 for _ in (native/ident/'answers.jsonl').open())
                   for ident in native_state['jobs'] if (native/ident/'answers.jsonl').exists()})
report['gpu_snapshot'] = subprocess.getoutput('nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader')
print(json.dumps(report, ensure_ascii=False))
