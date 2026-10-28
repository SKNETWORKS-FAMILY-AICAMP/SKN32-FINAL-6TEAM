from pathlib import Path
import os,subprocess,json,time
S=Path('C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch')
W=S/'st4f711-backend-20261029-v1';R=W/'repo';CS=R/'final_project_cs'
PY=S/'date_risk_env_312/Scripts/python.exe'
G=json.loads((W/'context.json').read_text())['git']
ENV={k:v for k,v in os.environ.items() if not k.startswith(('ACOP_','PYTEST_','PG'))}
ENV.update(GIT_OPTIONAL_LOCKS='0',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0',
 ACOP_DATABASE_URL='postgresql+psycopg://postgres@127.0.0.1:55491/st4f711',TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:55491/st4f711',
 ACOP_LLM_PROVIDER='mock',ACOP_OPENAI_API_KEY='sk-dummy-for-ci',ACOP_LLM_MODEL='gpt-4o-mini',ACOP_EMBEDDING_MODEL='text-embedding-3-small',ACOP_TENANT_ID='demo',
 ACOP_SECRET_KEY='dummy-secret-key-for-ci-0123456789abcdef',ACOP_COMPOSER_JWT_SECRET='dummy-composer-jwt-secret-for-ci-0123456789',ACOP_COMPOSER_ISSUER_SECRET='dummy-composer-issuer-secret-for-ci-0123456789',
 PYTHONPATH=str(W/'deps')+os.pathsep+str(R/'final_project_sample'),PGOPTIONS='-c timezone=Asia/Seoul')
ENV['PATH']=str(Path(G).parent)+os.pathsep+ENV['PATH']
def run(name,args,cwd=CS):
 t=time.monotonic()
 assert not (W/(name+'.log')).exists(),name
 with (W/(name+'.log')).open('w',encoding='utf8') as f:
  p=subprocess.run([str(a) for a in args],cwd=cwd,env=ENV,stdout=f,stderr=subprocess.STDOUT)
 print(name,p.returncode,round(time.monotonic()-t,2),flush=True);return p.returncode
if __name__=='__main__':
 assert 'dod' in json.loads((W/'gates.json').read_text()),'First gate run must finish before DB setup changes'
 assert run('register-prompts-v2',[PY,'-m','scripts.register_prompts'])==0
 assert run('db-identity-v2',[PY,'-c',"import psycopg,json; c=psycopg.connect('postgresql://postgres@127.0.0.1:55491/st4f711'); print(json.dumps([c.info.dbname,c.info.host,c.info.port,c.execute('SHOW TimeZone').fetchone()[0]])); c.close() "])==0
 results={}
 for name,args in [('contract-ready',['-m','pytest','tests/contract','-q','--junitxml='+str(W/'contract-ready.xml')]),('security-ready',['-m','pytest','tests/security','-q','--junitxml='+str(W/'security-ready.xml')]),('dod-ready',['-m','scripts.verify_dod_v11','--evidence-dir',str(W/'dod-evidence')])]:
  results[name]=run(name,[PY,*args]);(W/'ready-gates.json').write_text(json.dumps(results,indent=2))
 tests=['tests/e2e/test_web_initial_concurrency.py','tests/e2e/test_intake_read_lock.py','tests/unit/travel/test_intake_read_lock.py','tests/e2e/test_trip_intake_api.py','tests/contract/test_consumer_idempotency_contract.py','tests/unit/core/test_idempotency_request_id.py']
 results['concurrency-intake']=run('concurrency-intake',[PY,'-m','pytest',*tests,'-q','--junitxml='+str(W/'concurrency-intake.xml')])
 (W/'ready-gates.json').write_text(json.dumps(results,indent=2))
