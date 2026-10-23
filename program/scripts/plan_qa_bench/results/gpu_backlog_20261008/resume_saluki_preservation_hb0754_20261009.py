"""대용량 단일 파이프 실패를 보존하고 검증된 잔여 조각만 별도로 옮긴다."""
from pathlib import Path
import subprocess,json,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
base=Path(__file__).parent
def remote(alias,code):
    r=subprocess.run(['ssh',alias,'python3 -'],input=code,text=True,encoding='utf-8',capture_output=True,check=True)
    return json.loads(r.stdout)
info=remote('acopilot-gpu-b',r'''
from pathlib import Path
import hashlib,json,os
p=Path('/root/saluki_original_20261009/Underdog-Saluki-27B-1.0-IQ2-mix.gguf.part')
assert not Path('/proc/2799499').exists()
print(json.dumps(dict(bytes=p.stat().st_size,sha=hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),free=os.statvfs(p.parent).f_bavail*os.statvfs(p.parent).f_frsize)))
''')
offset=info['bytes'];assert offset==7196936192
a=remote('acopilot-gpu',r'''
from pathlib import Path
import hashlib,json,os
p=Path('/dev/shm/tripilot-saluki-20261009/Underdog-Saluki-27B-1.0-IQ2-mix.gguf')
h=hashlib.sha256();left=7196936192
with p.open('rb') as f:
 while left:
  b=f.read(min(left,8*1024**2));assert b;h.update(b);left-=len(b)
 assert h.hexdigest()=='''+repr(info['sha'])+r'''
 tail=Path('/tmp/tripilot-saluki-20261009/preservation_tail_hb0754.bin')
 assert not tail.exists()
 assert os.statvfs(tail.parent).f_bavail*os.statvfs(tail.parent).f_frsize>3*1024**3+701432960
 with tail.open('xb') as o:
  for b in iter(lambda:f.read(8*1024**2),b''):o.write(b)
print(json.dumps(dict(path=str(tail),bytes=tail.stat().st_size,sha=hashlib.file_digest(tail.open('rb'),'sha256').hexdigest(),prefix_sha=h.hexdigest())))
''')
assert a['bytes']==7898369152-offset
out=base/'saluki_preservation_resume_hb0754_20261009';out.mkdir(exist_ok=False)
tail=out/'preservation_tail_hb0754.bin'
subprocess.run(['scp','-q','acopilot-gpu:'+a['path'],str(tail)],check=True)
assert tail.stat().st_size==a['bytes'] and hashlib.file_digest(tail.open('rb'),'sha256').hexdigest()==a['sha']
subprocess.run(['scp','-q',str(tail),'acopilot-gpu-b:/root/saluki_original_20261009/preservation_tail_hb0754.bin'],check=True)
b=remote('acopilot-gpu-b',r'''
import hashlib,json,os,shutil,fcntl,time
from pathlib import Path
r=Path('/root/saluki_original_20261009');p=r/'Underdog-Saluki-27B-1.0-IQ2-mix.gguf.part';tail=r/'preservation_tail_hb0754.bin'
lock=(r/'preservation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert p.stat().st_size==7196936192 and not Path('/proc/2799499').exists()
assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()=='''+repr(info['sha'])+r'''
assert hashlib.file_digest(tail.open('rb'),'sha256').hexdigest()=='''+repr(a['sha'])+r'''
assert os.statvfs(r).f_bavail*os.statvfs(r).f_frsize>p.stat().st_size+tail.stat().st_size+3*1024**3
backup=r/'_backup'/'hb0754_before_verified_tail_resume';backup.mkdir(parents=True,exist_ok=False)
shutil.copy2(r/'preservation_state.json',backup/'preservation_state.json')
def copy_flush(src,dest,mode):
 with src.open('rb') as inp,dest.open(mode) as out:
  for chunk in iter(lambda:inp.read(8*1024**2),b''):
   out.write(chunk);out.flush();os.fdatasync(out.fileno());os.posix_fadvise(out.fileno(),0,0,os.POSIX_FADV_DONTNEED)
copy_flush(p,backup/p.name,'xb')
copy_flush(tail,p,'ab')
assert p.stat().st_size==7898369152
actual=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
assert actual=='4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb'
dest=r/'Underdog-Saluki-27B-1.0-IQ2-mix.gguf';assert not dest.exists();p.rename(dest)
state=dict(status='complete_verified_tail_resume',timestamp=time.time(),expected=7898369152,saved=7898369152,sha256=actual,original_failure_preserved=str(backup),new_resume_method='verified prefix and separate bounded tail SCP; no repeated 7.9GB pipe',GPU_used=False,storage='Existing B root disk; not off-machine durable archive')
tmp=r/'preservation_state.hb0754.tmp'
with tmp.open('x') as f:json.dump(state,f,indent=2)
tmp.replace(r/'preservation_state.json')
print(json.dumps(state))
''')
with (out/'resume_verification.json').open('x',encoding='utf-8') as f:json.dump(dict(partial_prefix=info,tail=a,result=b),f,indent=2)
print(json.dumps(b,ensure_ascii=False,indent=2))
