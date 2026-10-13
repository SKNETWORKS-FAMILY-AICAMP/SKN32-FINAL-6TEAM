from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-binding-work-v1.json').read_text(encoding='utf8'))
path = root / 'final_project_cs/tests/unit/travel/mobility/test_subway_binding_v1.py'
backup = path.parent / '_backup' / (datetime.now().astimezone().strftime('%Y-%m-%d_%H%M') + '_연결시험_미사용import') / path.name
backup.parent.mkdir(parents=True, exist_ok=True)
assert not backup.exists()
shutil.copy2(path, backup)
state['backups'].append({'source': path.relative_to(root).as_posix(), 'backup': backup.relative_to(root).as_posix(),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
path.write_text(path.read_text(encoding='utf8').replace('from copy import deepcopy\n', ''), encoding='utf8')
with (scratch / 'subway-binding-work-v2.json').open('x', encoding='utf8') as f: json.dump(state, f, ensure_ascii=False, indent=2)
native = scratch / 'audit_subway_binding_v1.py'
with (scratch / 'audit_subway_binding_v2.py').open('x', encoding='utf8') as f:
    f.write(native.read_text(encoding='utf8').replace("data_dir=root / 'datasets/mobility'", "data_dir=root / 'datasets/mobility/processed'"))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
with (ev / 'native-failure-v1.json').open('x', encoding='utf8') as f:
    json.dump({'error': 'Audit supplied datasets/mobility instead of configured processed folder; input missing before runtime loading',
               'product_defect': False, 'next': 'New audit v2 selects documented processed layout; old script preserved.'}, f, indent=2)
print('prepared')
