from pathlib import Path
from datetime import datetime
import hashlib, json, shutil, sys

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding='utf8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
previous = ROOT/'final_project_cs/wiki/records/evidence/2026-10-10_0311_차량회전자료_내용갱신/final-integrity-v1.json'
old = json.loads(previous.read_text(encoding='utf8'))
hashes = old['source_test_data_hashes'] | old['artifact_hashes']
current = {name: sha(ROOT/name) for name in hashes}
changed = [name for name in hashes if current[name] != hashes[name]]
assert not changed, changed
tag = datetime.now().strftime('%Y-%m-%d_%H%M')+'_도로자료_원자교체_감지'
ev = ROOT/'final_project_cs/wiki/records/evidence'/tag
ev.mkdir()
backups = []
for name in ['final_project_cs/app/domains/travel_ops/instances/mobility/engine/turn_restrictions.py',
             'final_project_cs/wiki/teams/mobility.md']:
    path = ROOT/name
    backup = path.parent/'_backup'/tag/path.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    assert sha(backup) == current[name]
    backups.append({'source': name, 'backup': backup.relative_to(ROOT).as_posix(), 'sha256': sha(backup)})
state = {'tag': tag, 'evidence': ev.relative_to(ROOT).as_posix(), 'baseline': current, 'backups': backups}
with (ev/'baseline-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
with (Path(__file__).parent/'graph-identity-state-20261010-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(json.dumps({'evidence': state['evidence'], 'matched': len(current), 'backups': len(backups)}, ensure_ascii=False))
