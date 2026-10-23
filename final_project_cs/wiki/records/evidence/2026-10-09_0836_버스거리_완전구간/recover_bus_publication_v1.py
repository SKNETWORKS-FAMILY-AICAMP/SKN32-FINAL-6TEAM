from pathlib import Path
import json
import subprocess
import sys

scratch = Path(__file__).parent
root = scratch.parents[1]
state = json.loads((scratch / 'bus-distance-work-v3.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
with (ev / 'publication-attempt-v1.json').open('x', encoding='utf8') as f:
    json.dump({'status': 'failed_before_mutation', 'reason': 'run.json UTF-8 read used platform cp949 default',
               'recovery': 'explicit UTF-8 in publisher v2, v1 preserved'}, f, ensure_ascii=False, indent=2)
source = (scratch / 'publish_bus_completeness_v1.py').read_text(encoding='utf8')
source = source.replace('.read_text())', ".read_text(encoding='utf8'))")
source = source.replace('# 既存資料ではなく、同じ欠損入力で出発観測の前後を再現する。', '# 같은 합성 누락 입력으로 출발 관측의 전후를 재현한다.')
source = source.replace("'publish_bus_completeness_v1.py']", "'publish_bus_completeness_v1.py', 'publish_bus_completeness_v2.py', 'recover_bus_publication_v1.py']")
with (scratch / 'publish_bus_completeness_v2.py').open('x', encoding='utf8') as f:
    f.write(source)
r = subprocess.run([sys.executable, str(scratch / 'publish_bus_completeness_v2.py')], capture_output=True,
                   text=True, encoding='utf8')
with (ev / 'publication-attempt-v2.log').open('x', encoding='utf8') as f:
    f.write(r.stdout + r.stderr)
print(r.stdout + r.stderr)
sys.exit(r.returncode)
