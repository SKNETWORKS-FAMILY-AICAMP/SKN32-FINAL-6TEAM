from pathlib import Path
from datetime import datetime
import json, os, subprocess, sys
ROOT = Path(__file__).resolve().parents[2]
CS = ROOT/'final_project_cs'
sys.stdout.reconfigure(encoding='utf8')
state = json.loads((Path(__file__).parent/'graph-identity-state-20261010-v1.json').read_text(encoding='utf8'))
ev = ROOT/state['evidence']
phase = sys.argv[1]
files = ['test_graph_atomic_replacement_v1.py']
if phase == 'after':
    files += ['test_turn_policy_content_reload_v1.py', 'test_car_turn_restrictions_v1.py', 'test_graph_router.py']
args = [sys.executable, '-m', 'pytest', *['tests/unit/travel/mobility/'+name for name in files], '-q',
        '-p', 'no:cacheprovider', f'--basetemp={ROOT/".tmp/mobility_complete_20261008"/ ("graph_identity_"+phase+"_v1")}',
        f'--junitxml={ev/(phase+"-v1.xml")}']
p = subprocess.run(args, cwd=CS, env=dict(os.environ, PYTHONIOENCODING='utf-8'), capture_output=True,
                   text=True, encoding='utf8', errors='replace')
with (ev/(phase+'-v1.log')).open('x', encoding='utf8') as f:
    f.write(p.stdout+'\n'+p.stderr)
with (ev/(phase+'-v1-run.json')).open('x', encoding='utf8') as f:
    json.dump({'command': args, 'files': files, 'exit_code': p.returncode,
               'finished_at': datetime.now().astimezone().isoformat()}, f, ensure_ascii=False, indent=2)
print(p.stdout[-1800:])
sys.exit(p.returncode)
