from pathlib import Path
from datetime import datetime
import hashlib
import html
import json
import re
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
ev = cs / 'wiki/records/evidence/2026-10-09_0737_환승운임_시간경계'
proof = json.loads((ev / 'verification-proof-v1.json').read_text(encoding='utf8'))
report = root / proof['report']
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v26'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(root / p) == h for p, h in proof['source_test_data_hashes'].items())
backups = json.loads((ev / 'backup-manifest-v1.json').read_text(encoding='utf8'))
assert all(sha(root / b['backup']) == b['sha256'] for b in backups)
checked = []
for file in (report, assets / 'mobility-readiness.html'):
    data = file.read_text(encoding='utf8')
    links = re.findall(r'\]\(([^)]+)\)', data) if file.suffix == '.md' else re.findall(r'href="([^"]+)"', data)
    for link in links:
        link = html.unescape(link)
        if link.startswith(('https:', 'http:', '#')):
            continue
        target = (file.parent / link.split('#')[0]).resolve()
        assert target.exists(), (file, link)
        checked.append({'file': file.relative_to(root).as_posix(), 'target': target.relative_to(root).as_posix()})
catalog = json.loads((assets / 'readiness-catalog.json').read_text(encoding='utf8'))
assert len(catalog['features']) == 21
new = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json',
       cs / 'wiki/teams/mobility.md', ev / 'verification-proof-v1.json', ev / 'backup-manifest-v1.json']
for file in new:
    text = file.read_text(encoding='utf8')
    assert not re.search(r'(?:\d{1,3}\.){3}\d{1,3}|webhooks/|@[0-9]', text), file
for name in ('publish_transfer_clock_v1.py', 'validate_transfer_clock_v1.py'):
    assert not (ev / name).exists()
    shutil.copy2(Path(__file__).parent / name, ev / name)
out = {'created_at': datetime.now().astimezone().isoformat(), 'source_hash_matches': len(proof['source_test_data_hashes']),
       'backup_hash_matches': len(backups), 'local_links': checked, 'features': len(catalog['features']),
       'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in new},
       'browser_render_verified': False, 'ip_pattern_scan_scope': [p.relative_to(root).as_posix() for p in new]}
with (ev / 'publication-validation-v1.json').open('x', encoding='utf8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps({'source_hash_matches': out['source_hash_matches'], 'backups': len(backups),
                  'local_links': len(checked), 'artifacts': len(new), 'features': out['features']}, ensure_ascii=False))
