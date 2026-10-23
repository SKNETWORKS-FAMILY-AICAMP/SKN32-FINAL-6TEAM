"""기존 기반·자료·학습 코드를 대조하고 새 대기열의 입력을 고정한다."""
import hashlib
import json
from pathlib import Path
import subprocess
import os

work = Path('/root/daily_rag_repeat_20261008')
expected = {
    work / 'qlora_train_finch.py': 'c43cc981465b6a4f8e55eca5dba3c1dbaa7f7815b2c952cd71ce799052e5c874',
    work / 'finch_schedule.py': 'cbfd5f58c08f202826f37aea9c6ffada859c707ad19ad20197cb4a8c611d213b',
    Path('/root/work/train_oos2.jsonl'): '07e6f7156883f9adb91812b2306b6dd813f60b189ae1da2610ae8c20d2d55a3c',
}
for path, want in expected.items():
    assert hashlib.sha256(path.read_bytes()).hexdigest() == want
assert Path('/root/hf_models/gemma-4-E4B-it/config.json').is_file()
assert Path('/root/daily_rag_20261008/SMOKE_DONE').is_file()
space = os.statvfs(work)
assert space.f_bavail * space.f_frsize >= 3 * 2 ** 30
subprocess.run(['bash', '-n', str(work / 'run_B57_repeat_20261008.sh')], check=True)
with (work / 'frozen_inputs.sha256').open('x') as f:
    f.write(''.join(f'{digest}  {path}\n' for path, digest in expected.items()))
plan = {'our_training': True, 'model': 'Gemma-4-E4B-it existing base',
        'dependency': 'existing B56 ALLDONE marker; wait without GPU allocation',
        'seed': 20261013, 'reference_seed': 20261012, 'mode_order': ['finch', 'cosine'],
        'reference_mode_order': ['cosine', 'finch'], 'epochs': 2, 'rank': 16, 'accum': 8,
        'max_lr': 5e-5, 'finch_base_rate': 2e-5, 'finch_alpha': 0.9,
        'purpose': 'Estimate seed variation of learning-rate comparison; not a product promotion',
        'frozen_inputs': {str(path): digest for path, digest in expected.items()},
        'preflight': {'frozen_hashes': [3, 3], 'shell_syntax': [1, 1], 'existing_smoke_marker': True,
                      'available_bytes': space.f_bavail * space.f_frsize},
        'prepared_full_training_jobs': 2, 'training_completed': 0,
        'new_model_download': False, 'weight_hash_reverified_this_preflight': False,
        'holdout_validation_complete': False, 'product_adoption': False}
with (work / 'prepared.json').open('x') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)
print(json.dumps(plan, ensure_ascii=False))
