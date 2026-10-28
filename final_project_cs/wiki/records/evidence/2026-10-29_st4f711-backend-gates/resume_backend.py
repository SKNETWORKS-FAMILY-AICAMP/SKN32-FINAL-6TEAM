from pathlib import Path
import os, subprocess, json, time, hashlib, socket
S=Path('C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch')
W=S/'st4f711-backend-20261029-v1'
W.mkdir(exist_ok=False)
OLD=S/'tf106-20261029/independent-latest-711-20261029'
G=json.loads((OLD/'setup.json').read_text())['git']
PY=S/'date_risk_env_312/Scripts/python.exe'
ENV={k:v for k,v in os.environ.items() if not k.startswith(('ACOP_','PYTEST_','PG'))}
ENV.update(GIT_OPTIONAL_LOCKS='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0')
def run(name,args,cwd=W,env=ENV):
    t=time.monotonic()
    with (W/(name+'.log')).open('w',encoding='utf-8') as f:
        r=subprocess.run([str(x) for x in args],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT)
    print(name,r.returncode,round(time.monotonic()-t,2),flush=True)
    return r.returncode
(W/'context.json').write_text(json.dumps({'python':str(PY),'git':G,'work':str(W)},indent=2))
(S/'_coord/ST4F711-backend-NOTICE.md').write_text('Owner Codex root, ST4F-711 backend continuation. Own scratch '+str(W)+'. T/S3/R notices read. No writes in other worker trees or original code. Isolated PostgreSQL port 55491 reserved after bind check; no shared DB. No integration/push until real gates and latest tip verified. Role-manager auto deploy risk is being checked. Other workers: please avoid concurrent ST4F-711 push.\n',encoding='utf-8')
assert run('team-tip',[G,'-c','credential.helper=','ls-remote','https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git','refs/heads/role-manager'])==0
assert run('clone',[G,'-c','core.longpaths=true','clone','--no-hardlinks',str(OLD/'validated'),str(W/'repo')])==0
R=W/'repo'
assert run('fetch-team',[G,'-c','credential.helper=','fetch','https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git','role-manager'],R)==0
assert run('checkout-latest',[G,'checkout','-b','st4f711/backend-validated','FETCH_HEAD'],R)==0
run('head',[G,'rev-parse','HEAD'],R)
PATCH=Path('C:/_proj/final_workspace/final_project_cs/wiki/records/evidence/2026-10-29_st4f711-independent-latest/ST4F-711-applicable.patch')
assert hashlib.sha256(PATCH.read_bytes()).hexdigest()=='27d6ff6fd7f4620ec0222667e49d14959ecdd0122975ef3e2f1816a5c0009c9f'
assert run('patch-check',[G,'apply','--check',PATCH],R)==0
assert run('patch-apply',[G,'apply',PATCH],R)==0
assert run('patch-reverse',[G,'apply','--reverse','--check',PATCH],R)==0
run('diff-check',[G,'diff','--check'],R)
run('python-packages',[PY,'-m','pip','list','--format=json'])
CS=R/'final_project_cs'
ENV.update(ACOP_DATABASE_URL='postgresql+psycopg://postgres@127.0.0.1:55491/st4f711',ACOP_LLM_PROVIDER='mock',ACOP_OPENAI_API_KEY='sk-dummy-for-ci',ACOP_LLM_MODEL='gpt-4o-mini',ACOP_EMBEDDING_MODEL='text-embedding-3-small',ACOP_TENANT_ID='demo',ACOP_SECRET_KEY='dummy-secret-key-for-ci-0123456789abcdef',ACOP_COMPOSER_JWT_SECRET='dummy-composer-jwt-secret-for-ci-0123456789',ACOP_COMPOSER_ISSUER_SECRET='dummy-composer-issuer-secret-for-ci-0123456789')
PG=Path('C:/_proj/postgresql/runtime/pgsql-16.15/bin')
with socket.socket() as sock: sock.bind(('127.0.0.1',55491))
assert run('initdb',[PG/'initdb.exe','-D',W/'pgdata','-U','postgres','--auth=trust','--encoding=UTF8','--locale=C'])==0
assert run('pg-start',[PG/'pg_ctl.exe','-D',W/'pgdata','-l',W/'postgres.log','-o','-h 127.0.0.1 -p 55491','-w','start'])==0
assert run('createdb',[PG/'createdb.exe','-h','127.0.0.1','-p','55491','-U','postgres','st4f711'])==0
if run('migrate',[PY,'-m','app.infrastructure.db.migrate'],CS): raise SystemExit(2)
if run('seed',[PY,'-m','scripts.seed_travel'],CS): raise SystemExit(3)
results={}
for name,args in [('contract',['-m','pytest','tests/contract','-q','--junitxml='+str(W/'contract.xml')]),('security',['-m','pytest','tests/security','-q','--junitxml='+str(W/'security.xml')]),('dod',['-m','scripts.verify_dod_v11'])]:
    results[name]=run(name,[PY,*args],CS)
    (W/'gates.json').write_text(json.dumps(results,indent=2))
print('WORK',W,flush=True)
