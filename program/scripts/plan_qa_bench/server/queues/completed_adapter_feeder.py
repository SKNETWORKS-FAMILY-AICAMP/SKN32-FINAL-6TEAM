"""승인 목록의 완료 어댑터만 보관하고 기존 GPU 평가 실행기에 공급한다.

SSH 이름은 git 밖 개인 설정에서 읽는다. 학습/평가 프로세스를 시작하지 않는다.
실패한 공급은 상태에 보존하며 운영자가 원인을 확인하기 전 재시도하지 않는다.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, io, json, msvcrt, os, shutil, subprocess, sys, tarfile, time

def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def save_new(p, data):
    with Path(p).open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)

def ssh(alias, code, args='', binary=False):
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',alias,'python3 - '+args],input=code.encode(),capture_output=True,timeout=900)
    if r.returncode: raise RuntimeError(r.stderr.decode('utf-8',errors='replace')[-4000:])
    return r.stdout if binary else json.loads(r.stdout)

def detail(alias,c,train_sha):
    code='''from pathlib import Path
import json,hashlib,os
c='''+repr(c)+'''
w=Path(c['work']);a=Path('/root/adapters')/c['tag']
if not (w/(c['mode']+'_DONE')).is_file():
 print(json.dumps({'complete':False}));raise SystemExit
r=json.loads((a/'recipe_complete.json').read_text())
assert r['status']=='completed' and r['schedule']==c['mode'] and r['seed']==c['seed']
assert r['train_sha256']=='''+repr(train_sha)+'''
assert r['input_rows']==r['used_rows']==2613 and r['filtered_rows']==0
assert r['epochs']==2 and r['rank']==16 and r['accum']==8
assert r['optimizer_steps']==len(r['rate_trace'])==654
assert all(0<x['lr']<=5e-5 for x in r['rate_trace'])
assert ('EVAL_DONE '+c['tag']) in (w/('eval_'+c['mode']+'.log')).read_text()
evals=list(Path('/root/work').glob('eval_'+c['tag']+'_mix*.json'));assert len(evals)==5
files=list(a.iterdir())+[w/(c['tag']+'_lora_f16.gguf')]+[w/n for n in ['train_'+c['mode']+'.log','convert_'+c['mode']+'.log','eval_'+c['mode']+'.log',c['mode']+'_DONE','qlora_train_finch.py','finch_schedule.py','prepared.json']]+evals
rows=[]
for p in files:
 if p.is_file():
  with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
  rows.append({'path':str(p),'bytes':p.stat().st_size,'sha256':h})
assert len({Path(x['path']).name for x in rows})==len(rows)
print(json.dumps({'complete':True,'files':rows,'recipe':r}))
'''
    return ssh(alias,code)

def register_source(template,c):
    src=template.replace('20261012',str(c['seed']))
    src=src.replace('finch_s',c['mode']+'_s').replace('travel finch','travel '+c['mode']).replace(' finch adapter',' '+c['mode']+' adapter').replace('FINCH',c['mode']).replace('_finch_additional','_'+c['mode']+'_additional')
    src=src.replace('import copy, hashlib, json, os, shutil, sys','import copy, hashlib, json, os, shutil, sys, fcntl')
    src=src.replace('before = path.read_bytes()',"edit=(root/'manifest.edit.lock').open('a');fcntl.flock(edit,fcntl.LOCK_EX)\nlock=(root/'queue.lock').open('a')\ntry:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError:pass\nelse:raise AssertionError('Existing worker must hold queue.lock')\nlock.close()\nbefore = path.read_bytes()")
    return src

def feed(cfg,c,folder):
    meta=detail(cfg['B'],c,cfg['train_sha256'])
    if not meta['complete']: return {'status':'waiting_training_completion','gpu_started':False}
    expected_digest=next(x['sha256'] for x in meta['files'] if x['path'].endswith('.gguf'))
    ids=[f'{family}_{c["mode"]}_s{c["seed"]}_{suite}' for suite in ['d3','d','d2','h','mx'] for family in ['e4bbase','e4bqat']]
    probe='''import json
from pathlib import Path
jobs=json.loads(Path('/tmp/tripilot-a-backlog-20261008/manifest.json').read_text())['jobs']
ids='''+repr(ids)+''';digest='''+repr(expected_digest)+'''
matching=[x for x in jobs if x.get('lora_sha256')==digest]
assert not matching or (len(matching)==10 and {x['id'] for x in matching}==set(ids)), 'Partial or equivalent role registrations require review'
print(json.dumps({'already_registered':len(matching)==10}))
'''
    if ssh(cfg['A'],probe)['already_registered']:
        return {'status':'registered','existing_registration':True,'registered_jobs':10,'gpu_started':False}
    folder.mkdir(exist_ok=False);save_new(folder/'source_detail.json',meta)
    assert shutil.disk_usage(folder).free>sum(x['bytes'] for x in meta['files'])*3+2**30
    code='''import io,json,tarfile,sys,hashlib
from pathlib import Path
rows='''+repr(meta['files'])+'''
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w:gz') as t:
 for x in rows:
  p=Path(x['path']);d=p.read_bytes();assert len(d)==x['bytes'] and hashlib.sha256(d).hexdigest()==x['sha256']
  e=tarfile.TarInfo(p.name);e.size=len(d);t.addfile(e,io.BytesIO(d))
sys.stdout.buffer.write(b.getvalue())
'''
    payload=ssh(cfg['B'],code,binary=True)
    with (folder/'source.tar.gz').open('xb') as f:f.write(payload)
    out=folder/'source';out.mkdir()
    with tarfile.open(fileobj=io.BytesIO(payload)) as t:
        for m in t.getmembers():
            p=out/m.name;assert m.isfile() and p.resolve().is_relative_to(out.resolve())
            with p.open('xb') as f:f.write(t.extractfile(m).read())
    data=Path(cfg['root'])/'datasets/core/pointing/trainset/train_oos'/c['tag'];data.mkdir(exist_ok=False)
    for x in meta['files']:
        p=out/Path(x['path']).name;assert p.stat().st_size==x['bytes'] and sha(p)==x['sha256']
        if '/root/adapters/' in x['path'] or p.suffix=='.gguf':shutil.copy2(p,data/p.name)
    gguf=next(data.glob('*.gguf'));digest=sha(gguf);remote='/tmp/tripilot-trained-adapters-20261008/'+c['mode']+'_s'+str(c['seed'])+'_lora_f16.gguf'
    check='''from pathlib import Path
import os,json,hashlib
p=Path('''+repr(remote)+''');n='''+str(gguf.stat().st_size)+'''
assert os.statvfs('/tmp').f_bavail*os.statvfs('/tmp').f_frsize>3*2**30+n+100*2**20
exists=p.exists()
if exists:assert p.stat().st_size==n and hashlib.sha256(p.read_bytes()).hexdigest()=='''+repr(digest)+'''
print(json.dumps({'exists_matching':exists}))
'''
    proof=ssh(cfg['A'],check)
    if not proof['exists_matching']:
        subprocess.run(['scp','-q',str(gguf),cfg['A']+':'+remote+'.part'],check=True,timeout=900)
        ssh(cfg['A'],"from pathlib import Path;import hashlib,os,json;p=Path("+repr(remote+'.part')+");assert hashlib.sha256(p.read_bytes()).hexdigest()=="+repr(digest)+";assert not Path("+repr(remote)+").exists();os.rename(p,"+repr(remote)+");print(json.dumps({'transferred':True}))")
    template=Path(cfg['template']);assert sha(template)==cfg['template_sha256']
    src=register_source(template.read_text(encoding='utf-8'),c)
    # Pin all original input and runner hashes before allowing the existing registration logic.
    gates='''import json,hashlib
from pathlib import Path
g='''+repr(cfg['original_contracts'])+'''
for x in g:
 for k in ['prompts','script']:
  assert hashlib.sha256(Path(x[k]).read_bytes()).hexdigest()==x[k+'_sha256']
'''
    src=gates+src
    (folder/'register_remote.py').write_text(src,encoding='utf-8')
    audit=ssh(cfg['A'],src,remote+' '+digest);save_new(folder/'registration.json',audit)
    save_new(folder/'verification.json',{'files':[len(meta['files']),len(meta['files'])],'gguf_sha256':digest,'adapter_directory':str(data),'registered_jobs':len(audit['added_jobs']),'expected':audit['added_expected']})
    return {'status':'registered','verification':str(folder/'verification.json'),'registered_jobs':len(audit['added_jobs']),'expected':audit['added_expected'],'gpu_started':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--once',action='store_true');ap.add_argument('--dry-run',action='store_true');args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text(encoding='utf-8'))
    if 'A' in cfg.get('disabled_machines', []):
        print(json.dumps({'status':'disabled_by_gpu_consolidation','target':'RTX A4000 only','gpu_started':False}),flush=True)
        return
    home=Path(cfg['home']);home.mkdir(exist_ok=True)
    lock=(home/'feeder.lock').open('a+b');lock.seek(0);lock.write(b'1');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise SystemExit('Another feeder holds the file lock')
    assert len(cfg['candidates'])==2 and {x['mode'] for x in cfg['candidates']}=={'cosine','finch'}
    assert all(x['seed']==20261014 for x in cfg['candidates'])
    assert all(x['tag']==f'oos2r_{x["mode"]}_5e5_seed20261014_20261009' and x['work']=='/root/daily_rag_seed3_20261009' for x in cfg['candidates'])
    assert sha(cfg['template'])==cfg['template_sha256']
    state_path=home/'state.json';state=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'candidates':{}}
    if not args.dry_run:
        pid_path=home/'feeder.pid'
        if pid_path.exists():
            backup=home/'_backup'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup.mkdir(parents=True);shutil.copy2(pid_path,backup/'feeder.pid')
        pid_path.write_text(str(os.getpid()),encoding='ascii')
    while True:
        now=datetime.now(timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%S%fZ')
        for c in cfg['candidates']:
            if state['candidates'].get(c['tag'],{}).get('status') in ['registered','failed_requires_review']:continue
            try:
                result={'status':'dry_run_ready' if detail(cfg['B'],c,cfg['train_sha256'])['complete'] else 'waiting_training_completion','mutations':False} if args.dry_run else feed(cfg,c,home/(stamp+'_'+c['mode']))
            except Exception as e:result={'status':'failed_requires_review','error':repr(e),'automatic_retry':False}
            state['candidates'][c['tag']]=result
        state.update(observed_at_utc=now.isoformat(),pid=os.getpid(),poll_seconds=cfg['poll_seconds'],dry_run=args.dry_run)
        save_new(home/('observation_'+stamp+'.json'),state)
        if not args.dry_run:
            if state_path.exists():
                backup=home/'_backup'/stamp;backup.mkdir(parents=True);shutil.copy2(state_path,backup/'state.json')
            tmp=home/('state_'+stamp+'.tmp');save_new(tmp,state);os.replace(tmp,state_path)
        print(json.dumps(state,ensure_ascii=False),flush=True)
        if args.once or args.dry_run:break
        time.sleep(cfg['poll_seconds'])

if __name__=='__main__':main()
