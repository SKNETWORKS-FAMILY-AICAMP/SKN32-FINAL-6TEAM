from pathlib import Path
import os,json,subprocess,hashlib,time
from concurrent.futures import ThreadPoolExecutor
S=Path('C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch')
W=S/'st4f711-backend-20261029-v1'; R=W/'repo'; web=R/'final_project_cs/frontend/apps/web'
OLD=S/'tf106-20261029/independent-latest-711-20261029'
node=json.loads((OLD.parent/'continue-711-20261029/runtime.json').read_text())['node']
env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','NEXT_TELEMETRY_DISABLED':'1'}
env['PATH']=str(Path(node).parent)+os.pathsep+env['PATH']
deps=OLD/'build-web/node_modules'
assert deps.is_dir()
with (W/'web-dependencies.log').open('w') as f:
 r=subprocess.run(['cmd','/c','mklink','/J',str(web/'node_modules'),str(deps)],stdout=f,stderr=subprocess.STDOUT)
assert r.returncode==0
def run(job):
 name,args=job;t=time.monotonic()
 with (W/(name+'.log')).open('w',encoding='utf8') as f:
  p=subprocess.run([node,*args],cwd=web,env=env,stdout=f,stderr=subprocess.STDOUT)
 print(name,p.returncode,round(time.monotonic()-t,2),flush=True);return name,p.returncode
jobs=[('web-test',['node_modules/vitest/vitest.mjs','run']),('web-lint',['node_modules/eslint/bin/eslint.js','.','--format','json']),('web-types',['node_modules/typescript/bin/tsc','--noEmit','--incremental','false'])]
with ThreadPoolExecutor(3) as pool: results=dict(pool.map(run,jobs))
(W/'web-results.json').write_text(json.dumps(results,indent=2))
compare=[]
for old in (OLD/'validated/final_project_cs/frontend/apps/web/src').rglob('*'):
 if old.is_file():
  rel=old.relative_to(OLD/'validated');now=R/rel
  if not now.is_file() or old.read_bytes()!=now.read_bytes():compare.append(str(rel))
(W/'prior-validated-source-comparison.json').write_text(json.dumps({'differing':compare},indent=2))
print('prior validated source differences',compare)
