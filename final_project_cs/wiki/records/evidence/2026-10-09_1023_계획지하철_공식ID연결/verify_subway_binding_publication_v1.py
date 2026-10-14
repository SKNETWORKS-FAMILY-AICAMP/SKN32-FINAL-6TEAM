from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import subprocess
import shutil

root = Path(__file__).resolve().parents[2]
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-binding-work-v1.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
proof = json.loads((ev / 'verification-proof-v1.json').read_text(encoding='utf8'))
publication = json.loads((ev / 'publication-validation-v1.json').read_text(encoding='utf8'))
hashes = {**proof['source_test_data_hashes'], **publication['artifact_hashes']}
for rel, digest in hashes.items(): assert hashlib.sha256((root / rel).read_bytes()).hexdigest() == digest, rel
page = root / 'final_project_cs/wiki/records/reports/assets/2026-10-09_mobility_readiness_v37/mobility-readiness.html'
code = '\n'.join(re.findall(r'<script>(.*?)</script>', page.read_text(encoding='utf8'), re.S))
script = scratch / 'subway-binding-visual-script-v1.js'
with script.open('x', encoding='utf8') as f: f.write(code)
node = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe'
command = [node, '--check', str(script)]
result = subprocess.run(command, capture_output=True, text=True, encoding='utf8')
with (ev / 'visual-script-syntax-v1.log').open('x', encoding='utf8') as f: f.write(result.stdout + result.stderr)
with (ev / 'final-integrity-v1.json').open('x', encoding='utf8') as f:
    json.dump({'checked_at': datetime.now().astimezone().isoformat(), 'source_and_artifact_hash_matches': len(hashes),
               'syntax_command': command, 'syntax_exit_code': result.returncode, 'browser_render_verified': False}, f, indent=2)
assert result.returncode == 0, result.stdout + result.stderr
shutil.copy2(Path(__file__), ev / Path(__file__).name)
print(json.dumps({'hashes': len(hashes), 'js_syntax': 'passed', 'browser_render_verified': False}))
