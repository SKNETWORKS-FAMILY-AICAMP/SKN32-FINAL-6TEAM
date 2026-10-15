"""Read-only ARM disk, resident memory and inference runtime inspection."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--ssh', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
(args.output / '.gitignore').write_text('*\n', encoding='utf-8')
observer = (Path(__file__).parent / 'server/observe_arm_serving.py').read_text(encoding='utf-8')
code = '''import contextlib,io,json,os,subprocess
from pathlib import Path
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
 exec(OBSERVER)
obs=json.loads(buf.getvalue())
v=os.statvfs('/')
disk={'total_bytes':v.f_blocks*v.f_frsize,'used_bytes':(v.f_blocks-v.f_bfree)*v.f_frsize,'available_bytes':v.f_bavail*v.f_frsize}
disk['used_pct']=100*disk['used_bytes']/disk['total_bytes']
mem={}
for line in Path('/proc/meminfo').read_text().splitlines():
 k,value=line.split(':',1);mem[k]=int(value.strip().split()[0])*1024
ram={'total_bytes':mem['MemTotal'],'available_bytes':mem['MemAvailable'],'used_without_available_bytes':mem['MemTotal']-mem['MemAvailable']}
ram['used_without_available_pct']=100*ram['used_without_available_bytes']/ram['total_bytes']
rows=subprocess.check_output(['ps','-eo','pid,etimes,pcpu,rss,args'],text=True).splitlines()
processes=[x for x in rows if any(t in x for t in ['llama-server','vllm','arm_serving_queue.py'])]
active=obs.get('active') or {};pid=active.get('engine_pid');resident={}
if pid and Path('/proc/'+str(pid)+'/status').exists():
 for line in Path('/proc/'+str(pid)+'/status').read_text().splitlines():
  k,value=line.split(':',1)
  if k in ['VmRSS','RssAnon','RssFile','RssShmem','VmSwap']:resident[k]=int(value.strip().split()[0])*1024
root=Path.home()/'bench/continuous-travel-20261008'
current=root/active.get('job_id','')
logs={}
for jid in ['e4bt_q4_grouped60_cache_ABBA_1','e4bt_q4_grouped60_cache_ABBA_2','e4bt_q4_grouped60_cache_ABBA_3','e4bt_q4_grouped60_cache_ABBA_4',active.get('job_id','')]:
 p=root/jid/'engine.log'
 if p.is_file():logs[jid]=[x for x in p.read_text(errors='replace').splitlines() if any(w in x for w in ['load_model','model loaded','prompt eval time','eval time =','total time =','listening on'])]
models=[{'name':p.name,'bytes':p.stat().st_size,'allocated_bytes':p.stat().st_blocks*512} for p in (Path.home()/'bench').glob('*.gguf')]
print(json.dumps({'observed_at_utc':obs['observed_at'],'disk_root':disk,'ram':ram,'processes':processes,'engine_resident_memory':resident,'active':active,'service':obs['service'],'resource_summary':obs['resource_summary'],'model_files':models,'engine_log_evidence':logs,'health':obs['health'],'slots':obs['slots']}))
'''.replace('OBSERVER', repr(observer))
raw = subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',args.ssh,'python3 -'], input=code.encode('utf-8'), timeout=55)
data = json.loads(raw)
(args.output / 'observation.json').write_bytes(raw)
print(json.dumps({k:data[k] for k in ['observed_at_utc','disk_root','ram','engine_resident_memory','active','resource_summary']}, ensure_ascii=False))
