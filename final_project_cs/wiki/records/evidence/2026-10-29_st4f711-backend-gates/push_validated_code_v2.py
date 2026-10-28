from pathlib import Path
import os,json,subprocess,hashlib,datetime
S=Path('C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch');W=S/'st4f711-backend-20261029-v1';R=W/'repo'
G=json.loads((W/'context.json').read_text())['git'];ENV={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0'}
BASE='c714eecdbcc6d6ec1865876321a90887a3e02dfd'
TEAM='https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git';ORIGIN='https://github.com/roroblack/A-COP.git'
PREFIX=[G,'-c','credential.helper=','-c','credential.helper=!'+(W/'gh.exe').as_posix()+' auth git-credential']
account=json.loads(subprocess.check_output([str(W/'gh.exe'),'api','user'],env=ENV))
ENV.update(GIT_AUTHOR_NAME=account['login'],GIT_COMMITTER_NAME=account['login'],GIT_AUTHOR_EMAIL=str(account['id'])+'+'+account['login']+'@users.noreply.github.com',GIT_COMMITTER_EMAIL=str(account['id'])+'+'+account['login']+'@users.noreply.github.com')
def run(name,args):
 name += '-v2'
 assert not (W/(name+'.log')).exists(),name
 p=subprocess.run(PREFIX+args,cwd=R,env=ENV,capture_output=True)
 (W/(name+'.log')).write_bytes(p.stdout+p.stderr)
 print(name,p.returncode,flush=True)
 assert p.returncode==0,name
 return p.stdout.decode('utf8').strip()
assert all(v==0 for v in json.loads((W/'ready-gates.json').read_text()).values())
assert len(json.loads((W/'ready-gates.json').read_text()))==4
assert all(v==0 for v in json.loads((W/'web-results.json').read_text()).values())
assert json.loads((W/'prior-evidence-audit.json').read_text())['matching']==61
for x in json.loads((W/'complete-web-build-correspondence.json').read_text()).values():assert x['matched']==x['files']==1378 and not x['different'] and not x['missing']
notices=json.loads((W/'coordination-before-integration.json').read_text())
for n,x in notices.items():assert hashlib.sha256((S/'_coord'/n).read_bytes()).hexdigest()==x['sha256'],'coordination changed: '+n
with (S/'_coord/ST4F711-backend-NOTICE.md').open('a',encoding='utf8') as f:f.write('\n'+datetime.datetime.now().astimezone().isoformat()+' Integration reservation: all required real backend gates and focused concurrency41, web1224/lint/types passed, previous built inputs1378/1378 equal. Preparing three-file code commit and coordinated fast-forward push to both role-manager; source parent c714eecdb. No develop/main, no manual deployment.\n')
assert run('precommit-head',['rev-parse','HEAD'])==BASE
for n,url in [('team',TEAM),('origin',ORIGIN)]:assert run(n+'-before-push',['ls-remote',url,'refs/heads/role-manager']).split()[0]==BASE
paths=['final_project_cs/frontend/apps/web/src/features/intake-review/intake-starting.tsx','final_project_cs/frontend/apps/web/src/features/trip-registration/registration-screen.tsx','final_project_cs/frontend/apps/web/src/features/intake-review/intake-starting-return.test.ts']
run('stage-source',['add','--',*paths])
run('source-staged-check',['diff','--cached','--check'])
assert set(run('source-staged-files',['diff','--cached','--name-only']).splitlines())==set(paths)
run('source-commit',['commit','-m','fix(web): restore registration form when intake navigation fails'])
SHA=run('source-sha',['rev-parse','HEAD']);assert run('source-parent',['rev-parse','HEAD^'])==BASE
for n,url in [('origin',ORIGIN),('team',TEAM)]:run(n+'-dry-run',['push','--dry-run',url,'HEAD:refs/heads/role-manager'])
for n,url in [('origin',ORIGIN),('team',TEAM)]:assert run(n+'-immediate-tip',['ls-remote',url,'refs/heads/role-manager']).split()[0]==BASE
result={'source_sha':SHA,'base_sha':BASE,'remotes':{},'time':datetime.datetime.now().astimezone().isoformat()}
for n,url in [('origin',ORIGIN),('team',TEAM)]:
 run(n+'-push',['push',url,'HEAD:refs/heads/role-manager'])
 tip=run(n+'-after-push',['ls-remote',url,'refs/heads/role-manager']).split()[0]
 result['remotes'][n]=tip;(W/'source-push-result.json').write_text(json.dumps(result,indent=2))
 assert tip==SHA,n
print(json.dumps(result,indent=2))
