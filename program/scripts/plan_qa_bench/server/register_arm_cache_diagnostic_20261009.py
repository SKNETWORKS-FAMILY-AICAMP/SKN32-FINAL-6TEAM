"""현재 ARM 작업을 유지하고 동일 문항 캐시 ABBA 진단만 원자적으로 등록한다."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import shutil
import subprocess
import sys


root = Path.home() / 'bench/continuous-travel-20261008'
payload = json.load(sys.stdin)
items = payload['items']
stats = payload['stats']
assert len(items) == len({r['i'] for r in items}) == 60
assert sum(r['gold'] is not None for r in items) == 20
source = root / 'd3.json'
assert hashlib.sha256(source.read_bytes()).hexdigest() == stats['source_sha256']
original = {r['i']: r for r in json.loads(source.read_text(encoding='utf-8'))}
assert all(r == original[r['i']] for r in items)
assert shutil.disk_usage(root).free >= 3 * 1024**3
unit = 'tripilot-arm-serving.service'
service = subprocess.check_output(['systemctl', 'show', unit, '-p', 'MainPID', '-p', 'ActiveState'], text=True)
assert 'ActiveState=active' in service
with (root / 'manifest_edit.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest_path = root / 'manifest.json'
    before = manifest_path.read_bytes()
    manifest = json.loads(before)
    state = json.loads((root / 'state.json').read_text())
    active = json.loads((root / 'active.json').read_text())
    ids = [f'e4bt_q4_grouped60_cache_ABBA_{i+1}' for i in range(4)]
    if any(j['id'] in ids for j in manifest['jobs']):
        raise RuntimeError('이미 등록된 진단입니다. 중복 등록하지 않습니다')
    template = next(j for j in manifest['jobs'] if j['id'] == 'e4bt_q4_d3')
    model = Path(template['model'])
    assert model.is_file() and model.stat().st_size == template['model_size_bytes']
    data = (json.dumps(items, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    assert hashlib.sha256(data).hexdigest() == stats['processed_sha256']
    prompts = root / 'd3_grouped60_cache_diagnostic_20261009.json'
    with prompts.open('xb') as f:
        f.write(data)
    jobs = [dict(template, id=ident, prompts=str(prompts),
                 prompt_sha256=stats['processed_sha256'], expected=60,
                 cache_prompt=flag,
                 purpose='Cache locality development diagnostic; matched ABBA repeats, 60 unique inputs',
                 diagnostic={'version':'20261009-v1','repeat_index':i+1,
                             'context_groups':5,'independent_questions':60,
                             'repeated_calls_not_independent':True})
            for i, (ident, flag) in enumerate(zip(ids, stats['ABBA_cache_flags']))]
    begun = [j for j in manifest['jobs'] if j['id'] in state['jobs']]
    pending = [j for j in manifest['jobs'] if j['id'] not in state['jobs']]
    manifest['jobs'] = begun + jobs + pending
    assert all(j in manifest['jobs'] for j in json.loads(before)['jobs'])
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S_arm_cache_ABBA')
    backup = root / '_backup' / stamp
    backup.mkdir(parents=True)
    shutil.copy2(manifest_path, backup / 'manifest.json')
    if manifest_path.read_bytes() != before:
        raise RuntimeError('등록 중 manifest가 변경되어 원자적 교체를 중단했습니다')
    temporary = root / ('manifest.'+stamp+'.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(manifest_path)
    after_service = subprocess.check_output(['systemctl','show',unit,'-p','MainPID','-p','ActiveState'],text=True)
    assert after_service == service
    print(json.dumps(dict(registered_at_utc=datetime.now(timezone.utc).isoformat(),
                         registered_jobs=ids, jobs_added=4, calls_added=240,
                         unique_questions=60, exact_records_verified=60,
                         prompt_sha256=stats['processed_sha256'],
                         existing_worker_preserved=True, active_job=active['job_id'],
                         existing_jobs_unchanged=len(json.loads(before)['jobs']),
                         manifest_jobs=len(manifest['jobs']),
                         pending_jobs=len(jobs)+len(pending),
                         backup=str(backup.relative_to(root))), ensure_ascii=True))
