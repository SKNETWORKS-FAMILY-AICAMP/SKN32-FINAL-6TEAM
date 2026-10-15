from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
import hashlib
import json
import re
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-envelope-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
manifest = json.loads((ev / 'backup-manifest-v1.json').read_text(encoding='utf8'))
proof = json.loads((ev / 'verification-proof-v1.json').read_text(encoding='utf8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
stamp = datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')
report = next((cs / 'wiki/records/reports').glob('2026-10-09_*_지하철_빈결과오인과_보관회복_검증.md'))
assets = cs / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v36'

def backup(path):
    dst = path.parent / '_backup' / (stamp + '_응답오인_발행경로수정') / path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(path, dst)
    manifest['backups'].append({'source': path.relative_to(root).as_posix(),
                                'backup': dst.relative_to(root).as_posix(), 'sha256': sha(path)})

for path in [report, scratch / 'publish_subway_envelope_v1.py', ev / 'publish_subway_envelope_v1.py']:
    backup(path)
    text = path.read_text(encoding='utf8')
    if path.suffix == '.md':
        text = text.replace('](../../../../app/', '](../../../app/')
        text = text.replace('](../../../../../datasets/', '](../../../../datasets/')
        text = text.replace('backup-manifest-v1.json)', 'backup-manifest-v2.json)')
    else:
        text = text.replace('](../../../../{source_backup.', '](../../../{source_backup.')
        text = text.replace('](../../../../../{raw.relative_to', '](../../../../{raw.relative_to')
    path.write_text(text, encoding='utf8')
with (ev / 'publication-failure-v1.json').open('x', encoding='utf8') as f:
    json.dump({'failed_check': 'relative report link exists', 'reason': 'source backup and raw folder references climbed one directory too far',
               'action': 'Backed up report/generator/copy and corrected two link prefixes; product code/test results unchanged'}, f, indent=2)
with (ev / 'backup-manifest-v2.json').open('x', encoding='utf8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
shutil.copy2(Path(__file__), ev / Path(__file__).name)
links = []
for doc in [report, assets / 'mobility-readiness.html']:
    content = doc.read_text(encoding='utf8')
    hrefs = re.findall(r'\]\(([^)]+)\)', content) if doc.suffix == '.md' else re.findall(r'href="([^"]+)"', content)
    for href in hrefs:
        if href.startswith(('https://', 'http://', '#')): continue
        path = (doc.parent / href).resolve()
        assert path.exists(), href
        links.append(path.relative_to(root).as_posix())
for rel, digest in proof['source_test_data_hashes'].items(): assert sha(root / rel) == digest, rel
for item in manifest['backups']: assert sha(root / item['backup']) == item['sha256'], item['backup']
class PageCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = 0
        self.labels = []
        self.selects = []
        self.scripts = []
        self.in_script = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article': self.articles += 1
        if tag == 'label': self.labels.append(attrs.get('for'))
        if tag == 'select': self.selects.append(attrs.get('id'))
        if tag == 'script': self.in_script = True
    def handle_endtag(self, tag):
        if tag == 'script': self.in_script = False
    def handle_data(self, data):
        if self.in_script: self.scripts.append(data)
page = PageCheck()
page.feed((assets / 'mobility-readiness.html').read_text(encoding='utf8'))
assert page.articles == 21 and page.labels == page.selects == ['filter']
with (ev / 'visual-structure-check-v1.json').open('x', encoding='utf8') as f:
    json.dump({'articles': page.articles, 'visible_filter_label': True, 'browser_render_verified': False}, f, indent=2)
with (scratch / 'subway-envelope-visual-script-v1.js').open('x', encoding='utf8') as f: f.write('\n'.join(page.scripts))
artifacts = [report, assets / 'mobility-readiness.html', assets / 'readiness-catalog.json', cs / 'wiki/teams/mobility.md',
             root / state['debug'], root / 'datasets/mobility/REPORT.md', root / 'datasets/mobility/README.md',
             ev / 'verification-proof-v1.json', ev / 'backup-manifest-v2.json']
result = {'source_hash_matches': len(proof['source_test_data_hashes']), 'backup_hash_matches': len(manifest['backups']),
          'local_links': links, 'artifact_hashes': {p.relative_to(root).as_posix(): sha(p) for p in artifacts},
          'feature_count': 21, 'browser_render_verified': False}
with (ev / 'publication-validation-v2.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps({'report': report.relative_to(root).as_posix(), 'sources': result['source_hash_matches'],
                  'backups': result['backup_hash_matches'], 'artifacts': len(artifacts), 'links': len(links)}, ensure_ascii=False))
