"""Inspect the existing A4000 queue; optionally collect terminal artifacts only.

Reads the ignored private config. Starts/stops no remote job and never extracts
an archive automatically. Repeated collection of the same terminal set is skipped.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
REMOTE_SNAPSHOT = r'''
from pathlib import Path
from datetime import datetime,timezone
import json,os,shutil,subprocess
q=Path('/root/gpu_single_queue_20261012');hf=Path('/root/hf_app_completion_missing_20261011_2230')
manifest=json.loads((q/'manifest.json').read_text());state=json.loads((q/'state.json').read_text())
def read(path):return json.loads(path.read_text()) if path.is_file() else None
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),manifest=manifest,state=state,
 dependency=read(q/'dependency_status.json'),hf_state=read(hf/'state.json'),
 dispatcher_alive=Path('/proc/2814996').exists(),predecessor_alive=Path('/proc/2814363').exists(),
 root_free_bytes=shutil.disk_usage('/').free,shm_free_bytes=shutil.disk_usage('/dev/shm').free,
 gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used','--format=csv,noheader'],text=True).strip())))
'''


def command(code):
    encoded=base64.b64encode(code.encode()).decode()
    return 'python3 -c "import base64;exec(base64.b64decode(\''+encoded+'\'))"'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--collect',action='store_true');args=parser.parse_args()
    private=json.loads((ROOT/'datasets/travel/gpu_feeder_private_20261009/private_config.json').read_text())
    ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',private['B']]
    snapshot=json.loads(subprocess.check_output(ssh+[command(REMOTE_SNAPSHOT)],timeout=60))
    local=ROOT/'datasets/travel/model_queue_handoff_20261012';local.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    (local/f'snapshot_{stamp}_private.json').write_text(json.dumps(snapshot,indent=2),encoding='utf8')
    states=snapshot['state']['jobs'];jobs=snapshot['manifest']['jobs']
    terminal={i:s for i,s in states.items() if s.get('status') in ('completed','completed_with_errors','failed')}
    print(json.dumps(dict(observed_utc=snapshot['utc'],registered=len(jobs),terminal=len(terminal),
        pending=len(jobs)-len(terminal)-sum(s.get('status')=='running' for s in states.values()),
        dispatcher_alive=snapshot['dispatcher_alive'],predecessor_alive=snapshot['predecessor_alive'],gpu=snapshot['gpu'],
        root_free_bytes=snapshot['root_free_bytes'],snapshot_folder=str(local)),ensure_ascii=False))
    if not args.collect or not terminal:return
    token=hashlib.sha256(json.dumps(terminal,sort_keys=True).encode()).hexdigest()[:16]
    archive=local/f'terminal_{token}.tar'
    if archive.exists():print('동일 종료 상태의 보관 파일이 이미 있습니다.');return
    ids=list(terminal)
    inventory=r'''
from pathlib import Path
import json,sys
q=Path('/root/gpu_single_queue_20261012');ids=IDENTIFIERS
files=[]
for ident in ids:
 folder=q/ident
 if folder.is_dir():
  files += [p for p in folder.rglob('*') if p.is_file() and not p.is_symlink() and (p.suffix in ('.json','.jsonl','.log','.safetensors','.gguf') or p.name=='job.log')]
if 'winnow_upgrade_train' in ids:
 folder=Path('/root/winnow_upgrade_20261012')
 files += [p for p in folder.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in ('.json','.safetensors','.gguf')]
if 'saluki_packed_lora_convert_s20261019' in ids:
 folder=Path('/dev/shm/saluki_packed_lora_20261012')
 files += [p for p in folder.glob('*.gguf') if p.is_file() and not p.is_symlink()]
files=sorted(set(files));print(json.dumps(dict(paths=[str(p) for p in files],bytes=sum(p.stat().st_size for p in files))))
'''.replace('IDENTIFIERS',repr(ids))
    listing=json.loads(subprocess.check_output(ssh+[command(inventory)],timeout=60))
    assert shutil.disk_usage(local).free > listing['bytes'] + 512*2**20,'로컬 회수 여유 공간 부족'
    tarcode=r'''
from pathlib import Path
import tarfile,sys
paths=PATHS
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
 for value in paths:
  p=Path(value);assert p.is_file() and not p.is_symlink();archive.add(str(p),arcname=str(p).lstrip('/'),recursive=False)
'''.replace('PATHS',repr(listing['paths']))
    partial=archive.with_suffix('.partial.tar')
    assert not partial.exists(),'이전 미완료 회수 파일을 보존하고 확인하세요'
    with partial.open('xb') as output:subprocess.run(ssh+[command(tarcode)],stdout=output,check=True,timeout=600)
    partial.rename(archive)
    with archive.open('rb') as source:sha=hashlib.file_digest(source,'sha256').hexdigest()
    archive.with_suffix('.json').write_text(json.dumps(dict(sha256=sha,inventory=listing,terminal=terminal),indent=2),encoding='utf8')
    print('종료 산출물 보관 완료:',archive)


if __name__=='__main__':main()
