from pathlib import Path
import subprocess,json,hashlib,shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
base=Path(__file__).parent
snapshot=json.loads((base/'A_snapshot_hb0754_20261009.json').read_text(encoding='utf-8'))
jobs=[j for j in snapshot['manifest']['jobs'] if (j['id'].startswith('saluki_original_') and j.get('suite')!='smoke12') or ('cosine_s20261012' in j['id'] and not j['id'].endswith('_d3'))]
assert len(jobs)==13 and sum(j['expected'] for j in jobs)==27555
assert all(snapshot['state']['jobs'][j['id']]['status'].startswith('completed') for j in jobs)
out=base/'A_completed_hb0754_20261009';out.mkdir(exist_ok=False)
remote_root='/tmp/tripilot-a-backlog-20261008'
sources=['acopilot-gpu:'+remote_root+'/'+j['id'] for j in jobs]
subprocess.run(['scp','-q','-r',*sources,str(out)],check=True)
code='''import pathlib,json,hashlib\nr=pathlib.Path('/tmp/tripilot-a-backlog-20261008')\nids='''+repr([j['id'] for j in jobs])+'''
rows=[]
for ident in ids:
 for p in (r/ident).glob('*'):
  if p.is_file(): rows.append(dict(relative=ident+'/'+p.name,bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()))
print(json.dumps(rows))
'''
r=subprocess.run(['ssh','acopilot-gpu','python3 -'],input=code,text=True,encoding='utf-8',capture_output=True,check=True)
files=json.loads(r.stdout)
for f in files:
    p=out/f['relative']
    assert p.stat().st_size==f['bytes'] and hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==f['sha256']
for j in jobs:
    dest=base/j['id'];assert not dest.exists();shutil.copytree(out/j['id'],dest)
    suite=j.get('suite') or j['id'].split('_')[-1]
    script={'d':'backlog_choice_report.py','d2':'backlog_choice_report.py','d3':'backlog_choice_report.py','h':'backlog_h_report.py','mx':'backlog_mx_report.py'}[suite]
    args=[sys.executable,str(base.parent.parent/script),j['id']]
    if suite in ['d','d2','d3']:args.append(suite.upper())
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',check=True)
    with (out/f"{j['id']}_aggregate_stdout.json").open('x',encoding='utf-8') as f:f.write(result.stdout)
with (out/'archive_verification.json').open('x',encoding='utf-8') as f:json.dump(dict(files=files,remote_local_sha_match=[len(files),len(files)],jobs=[j['id'] for j in jobs],saved=27555,expected=27555,originals=5,our_trained_jobs=8,observed_at_utc=snapshot['observed_at_utc']),f,ensure_ascii=False,indent=2)
print(json.dumps(dict(files=len(files),jobs=len(jobs),saved=27555,expected=27555,archive=str(out))))
