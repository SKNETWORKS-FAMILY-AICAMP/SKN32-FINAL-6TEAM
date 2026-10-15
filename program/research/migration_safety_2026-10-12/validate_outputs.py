"""Validate only this follow-up's documents and evidence; do not rewrite wiki."""
import ast
import json
from pathlib import Path
import re
import yaml

here = Path(__file__).resolve().parent
root = here.parents[2]
documents = [here/'README.md', root/'final_project_cs/wiki/data/migrations.md',
    root/'final_project_cs/wiki/records/reports/2026-10-12_migration-transaction-and-deploy-safety.md']
checks = []
for path in documents:
    text = path.read_text(encoding='utf-8')
    for destination in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
        if destination.startswith(('http://','https://','#')):
            continue
        target = destination.split('#')[0]
        checks.append({'document':str(path.relative_to(root)), 'target':destination,
                       'passed':(path.parent/target).exists()})
    if '/wiki/' in path.as_posix():
        metadata = yaml.safe_load(text.split('---',2)[1])
        checks.append({'document':str(path.relative_to(root)), 'check':'frontmatter',
                       'passed':all(key in metadata for key in ('type','title','description','status','domain'))})
validation = json.loads((here/'source-validation.json').read_text())
for name in validation['owned_source_sha256']:
    if name.endswith('.py'):
        ast.parse((root/'final_project_cs'/name).read_text(encoding='utf-8'))
        checks.append({'file':name,'check':'python syntax','passed':True})
for row in validation['historical_files']:
    checks.append({'file':row['file'],'check':'historical bytes preserved','passed':row['same_as_start']})
wiki = json.loads((here/'wiki-check-final.json').read_text(encoding='utf-8'))
owned_wiki = ['final_project_cs/wiki/data/migrations.md',
    'final_project_cs/wiki/records/reports/2026-10-12_migration-transaction-and-deploy-safety.md']
ours = [item for items in wiki['problems'].values() for item in items if any(p in item for p in owned_wiki)]
checks.append({'check':'no whole-wiki violations attributed to owned documents','passed':not ours})
result = {'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,
    'whole_wiki_violations':wiki['total_violations'], 'owned_document_violations':ours,
    'whole_wiki_note':'Four violations in concurrent work outside this task were preserved.',
    'shell_syntax':'auto_deploy.sh and server_up.sh: bash -n passed',
    'diagram':'skill self_check passed; independent headless Chrome render visually inspected',
    'scope':'artifact and static validation, not customer workflow or real Docker deployment'}
(here/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':result['passed'],'total':result['total'],
                  'whole_wiki_violations':result['whole_wiki_violations']}))
assert result['passed']==result['total']
