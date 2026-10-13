import os,pathlib,json,subprocess,sys,fcntl
r={"machine":sys.argv[1],"utc":subprocess.check_output(["date","-u","+%Y-%m-%dT%H:%M:%SZ"],text=True).strip(),"memory":pathlib.Path("/proc/meminfo").read_text(),"processes":subprocess.getoutput("ps -eo pid,ppid,etimes,args | grep -E 'gpu_eval_queue.py|llama-server|d_test_llama|run_B5[4-8]|qlora_train|saluki'"),"gpu":subprocess.getoutput("nvidia-smi --query-gpu=memory.used,utilization.gpu,memory.total --format=csv,noheader"),"mounts":[],"locks":[]}
x=json.loads(subprocess.check_output(["findmnt","-J","-o","TARGET,FSTYPE,OPTIONS"],text=True))
def walk(rows):
 for m in rows:
  target=m['target']; opts=m['options'].split(',')
  if 'rw' in opts and not target.startswith(('/proc','/sys')) and os.access(target,os.W_OK):
   try:
    v=os.statvfs(target);r['mounts'].append({"target":target,"fstype":m['fstype'],"free":v.f_bavail*v.f_frsize,"options":m['options']})
   except OSError as e:r['mounts'].append({"target":target,"error":str(e)})
  walk(m.get('children',[]))
walk(x['filesystems'])
for p in ['/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.current','/sys/fs/cgroup/memory/memory.limit_in_bytes','/sys/fs/cgroup/memory/memory.usage_in_bytes']:
 if pathlib.Path(p).is_file():r[p]=pathlib.Path(p).read_text().strip()
for p in ['/tmp/tripilot-a-backlog-20261008/queue.lock','/root/daily_rag_20261008/queue.lock','/root/daily_rag_repeat_20261008/queue.lock','/root/daily_rag_seed3_20261009/queue.lock']:
 if pathlib.Path(p).is_file():
  f=open(p,'r');busy=False
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
  except BlockingIOError:busy=True
  f.close();r['locks'].append({'path':p,'busy':busy})
r['named_roots']={}
for p in ['/workspace','/tmp','/root','/dev/shm','/mnt','/opt']:
 if pathlib.Path(p).exists():
  v=os.statvfs(p);r['named_roots'][p]={'free':v.f_bavail*v.f_frsize,'writable':os.access(p,os.W_OK)}
r['model_candidates']=[str(p) for root in ['/workspace','/root/hf_models','/tmp','/dev/shm'] if pathlib.Path(root).exists() for p in pathlib.Path(root).glob('*Saluki*') if p.is_file()]
r['engine_source_dirs']=[str(p) for root in ['/workspace','/tmp','/root'] if pathlib.Path(root).exists() for p in pathlib.Path(root).glob('*llama*') if p.is_dir()]
print(json.dumps(r))
