"""Create final evidence without altering existing source SQL or prior reports."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

here = Path(__file__).resolve().parent
workspace = here.parents[2]
cs = workspace/'final_project_cs'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

before = json.loads((here/'sql-before.json').read_text())
changed = [{'file':name,'before':old,'after':digest(cs/name),
            'note':'shared change observed during task; this task did not write SQL'}
           for name,old in before.items() if digest(cs/name)!=old]
history = json.loads((cs/'app/infrastructure/db/migrations/migration-plan.json').read_text())['historical_files']
histories = []
for name in history:
    p = cs/'app/infrastructure/db/migrations'/name
    key = str(p.relative_to(cs))
    histories.append({'file':name,'sha256':digest(p),'same_as_start':before[key]==digest(p)})
owned = [
    'app/infrastructure/db/migrate.py','app/infrastructure/db/migration_sql.py',
    'deploy/.gitignore','deploy/Dockerfile.api','deploy/Dockerfile.migration-safety',
    'deploy/migration_safe_deploy.py','deploy/auto_deploy.sh','deploy/server_up.sh','requirements.txt',
    'tests/unit/core/test_migration_atomic_sql.py','tests/unit/core/test_migration_safe_deploy.py',
    'tests/integration/db/test_migrations_rerun.py','wiki/data/migrations.md',
    'wiki/records/reports/2026-10-12_migration-transaction-and-deploy-safety.md',
]
validation = {'sql_files_at_start':len(before), 'unchanged_sql_files':len(before)-len(changed),
    'observed_shared_sql_changes':changed,'sql_files_written_by_this_task':[],
    'historical_files':histories,'owned_source_sha256':{p:digest(cs/p) for p in owned},
    'protected_reports_modified_by_this_task':[],
    'note':'Hashes of current shared files; pre-existing changes are preserved, not attributed to this task.'}
(here/'source-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')

def suite(name):
    root = ET.parse(here/name).getroot()
    suites = list(root) if root.tag=='testsuites' else [root]
    return {key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}

focused = suite('focused-results-v3.xml')
db = suite('db-results-v2.xml')
summary = {'date':'2026-10-12','work':'new follow-up to the 25-item wiki review',
    'final_runs':{'focused_code_contracts':focused,'isolated_postgres':db},
    'passed':sum(s['tests']-s['failures']-s['errors']-s['skipped'] for s in (focused,db)),
    'total':sum(s['tests'] for s in (focused,db)),
    'earlier_attempts':{n:suite(n) for n in ('unit-results.xml','deploy-results-v1.xml','db-results.xml')},
    'runtime':json.loads((here/'db-runtime-result.json').read_text()),
    'isolated_cluster_stop':json.loads((here/'cluster-stop.json').read_text()),
    'historical_sql_unchanged':sum(v['same_as_start'] for v in histories),
    'historical_sql_total':len(histories),
    'actual_deployment':False,'business_db_changes':False,'real_customer_flow_test':False,
    'commit':False,'push':False,
    'remaining_before_deployment':[
        'Real Docker/Compose image build, native and mounted artifact checks.',
        'Candidate image SQL hash comparison and PostgreSQL 17 isolated regression.',
        'Environment-specific preflight, DB recovery materials and independent review.',
        'Separately approved deployment, exact-image recovery drill and synthetic customer flow.'],
    'limits':['Docker control failure tests use simulation, not a real Docker Engine.',
              'Database tests use vendor PostgreSQL 16.15 demo/pgvector 0.8.2, not production PG17.',
              'One shared SQL file changed during work and was preserved; no SQL file was written by this task.',
              'Whole-process kill, power loss and delayed daemon operations were not reproduced.']}
(here/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':summary['passed'],'total':summary['total'],'shared_sql_changes':len(changed)}))
