"""고정 배포 원본 결정 API를 기존 GPU worker에서만 순차 실행한다."""
import os
from pathlib import Path
import sys

PYTHON = '/workspace/rtenv/bin/python'
if Path(sys.prefix) != Path('/workspace/rtenv'):
    os.execv(PYTHON, [PYTHON, __file__])

import hashlib
import json
import math
import subprocess
import threading
import time
import traceback
os.environ.setdefault('TORCHINDUCTOR_COMPILE_THREADS', '1')
import torch
from transformers import AutoModel, AutoProcessor

ROOT = Path('/tmp/tripilot-valen-20261009')
MODEL = ROOT/'model'
SHA = '465714dd28702c4232d9233c2a2157d366967c541b2a27d9dadccc816304fd48'
TAG = os.environ['TAG']
SMOKE = TAG.startswith('valen_08b_original_smoke12_')
MARKER = ROOT/'SMOKE_PASS.json'


def memory():
    p = Path('/sys/fs/cgroup/memory')
    used = int((p/'memory.usage_in_bytes').read_text())
    limit = int((p/'memory.limit_in_bytes').read_text())
    stats = {k:int(v) for k,v in (line.split() for line in (p/'memory.stat').read_text().splitlines())}
    # Ordinary file pages can be reclaimed; shmem and anonymous memory cannot.
    file_pages = stats.get('total_inactive_file',stats.get('inactive_file',0)) + stats.get('total_active_file',stats.get('active_file',0))
    ordinary_cache = max(0,stats.get('total_cache',stats.get('cache',0))-stats.get('total_shmem',stats.get('shmem',0)))
    reclaimable = max(0,min(used,file_pages,ordinary_cache))
    return dict(used=used,limit=limit,headroom=limit-used,reclaimable_file_cache=reclaimable,
                working_headroom=limit-used+reclaimable,shmem=stats.get('total_shmem',stats.get('shmem',0)))


def memory_ready(measured):
    # Preserve the original direct margin; cache-accounted path reserves twice as much.
    return measured['headroom'] > 4*2**30 or measured['working_headroom'] > 8*2**30


def validate_response(response, keys):
    answer = response['answers']['selection']
    probs = answer['probabilities']
    assert answer['type'] == 'choice' and set(probs) == set(keys)
    assert all(type(v) in (float,int) and math.isfinite(v) and 0<=v<=1 for v in probs.values())
    assert math.isclose(sum(probs.values()),1,abs_tol=1e-6)
    chosen = answer['choice']
    assert chosen in keys and chosen == max(probs,key=probs.get)
    return chosen, probs


def main():
    assert not os.environ.get('LORA'), 'Original release only'
    assert int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip()) < 1000, 'Existing worker must own an idle GPU'
    preload_memory=memory()
    assert memory_ready(preload_memory), ('Insufficient direct or cache-accounted reserve',preload_memory)
    verified = json.loads((ROOT/'download_verified.json').read_text())
    assert verified['hashes']['model.safetensors'] == SHA
    for name, expected in verified['hashes'].items():
        with (MODEL/name).open('rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest() == expected, name
    if not SMOKE:
        passed = json.loads(MARKER.read_text())
        assert passed['parsed'] == passed['expected'] == 12 and passed['errors'] == 0
        assert passed['model_sha256'] == SHA
    prompts = Path(os.environ['PROMPTS'])
    rows = sorted(json.loads(prompts.read_text()),key=lambda x:(x['set'],x['qi']))
    output = Path(f'd_test_{TAG}.jsonl')
    assert not output.exists(), 'Preserve existing attempt; no automatic restart'
    torch.set_num_threads(4)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    begin = time.perf_counter()
    processor = AutoProcessor.from_pretrained(MODEL,trust_remote_code=True,local_files_only=True)
    model = AutoModel.from_pretrained(MODEL,trust_remote_code=True,local_files_only=True,
                                     dtype='auto',attn_implementation='sdpa').to('cuda').eval()
    dtype_params = {}
    for param in model.parameters():
        key=str(param.dtype); dtype_params[key]=dtype_params.get(key,0)+param.numel()
    assert dtype_params == {'torch.float32':854305641}, dtype_params
    assert all(p.dtype == torch.float32 for p in model.head.parameters())
    assert model.backbone_autocast_dtype == torch.bfloat16
    contract = dict(model_revision=verified['revision'],model_sha256=SHA,
        prompt_sha256=hashlib.sha256(prompts.read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        original_file_hashes=verified['hashes'], dtype_parameters=dtype_params,
        backbone_autocast='bfloat16',head_dtype='float32',execution='shared_state',temperature=1.0,
        our_training=False,publisher_training='Decision SFT by developer',expected=len(rows),
        local_files_only=True,processor_explicit=True, output='native choice-head probabilities',
        max_choices=255,max_tokens=32768,truncation=False, repeated_runs=1,
        load_seconds=time.perf_counter()-begin,memory_after_load=memory(),
        torch_version=torch.__version__,transformers_version=__import__('transformers').__version__,
        final_ranking=False, GPU_owner='existing queue worker', speed_directly_comparable_to_JSON_generation=False)
    with Path('valen_contract.json').open('x') as f:json.dump(contract,f,indent=2)
    stop=threading.Event()
    def monitor():
        with Path('valen_resources.jsonl').open('x') as f:
            while not stop.is_set():
                f.write(json.dumps(dict(timestamp=time.time(),memory=memory(),
                    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True).strip(),
                    torch_allocated=torch.cuda.memory_allocated(),torch_reserved=torch.cuda.memory_reserved()))+'\n');f.flush();stop.wait(5)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    records=[]
    try:
        with output.open('x',encoding='utf-8') as answers:
            for ix,row in enumerate(rows):
                record={k:row[k] for k in ['i','set','qi','type','gold']}
                start=time.perf_counter()
                try:
                    request=row['request']
                    response=model.predict(request,processor=processor,execution='shared_state',temperature=1.0)
                    chosen, probs=validate_response(response,request['questions']['selection']['criteria'])
                    assert response['usage']['input_tokens'] <= 32768
                    pick=None if chosen=='NONE' else int(chosen)
                    record.update(parsed=True,pick=pick,content=json.dumps(response,ensure_ascii=False),
                        native_response=response,choice_probabilities=probs,
                        p_null=probs['NONE'], p_mass=sum(probs.values()),
                        probability_kind='native choice head; not next-token or verbal confidence',
                        usage=response['usage'],internal_usage=response.get('internal_usage'))
                except Exception as exc:
                    record.update(parsed=False,error=repr(exc),traceback=traceback.format_exc())
                    if isinstance(exc,torch.cuda.OutOfMemoryError):torch.cuda.empty_cache()
                record['ms']=round((time.perf_counter()-start)*1000)
                answers.write(json.dumps(record,ensure_ascii=False)+'\n');answers.flush();records.append(record)
                if SMOKE or (ix+1)%100==0:print(TAG,ix+1,'/',len(rows),flush=True)
                # An OOM breaks this attempt and preserves missing items in the full denominator.
                if record.get('error','').startswith('OutOfMemoryError'):break
        summary=dict(expected=len(rows),saved=len(records),parsed=sum(bool(x.get('parsed')) for x in records),
            errors=sum(bool(x.get('error')) for x in records),missing=len(rows)-len(records),
            correct=sum(bool(x.get('parsed')) and x.get('pick')==x['gold'] for x in records),
            model_sha256=SHA,smoke=SMOKE,max_gpu_allocated=torch.cuda.max_memory_allocated(),memory=memory())
        with Path('valen_summary.json').open('x') as f:json.dump(summary,f,indent=2)
        if SMOKE:
            assert summary['parsed'] == summary['expected'] == 12 and summary['errors']==0, 'API/load/probability gate failed; preserve attempt'
            with MARKER.open('x') as f:json.dump(summary,f,indent=2)
            (ROOT/'smoke_verified_model.safetensors').symlink_to(MODEL/'model.safetensors')
        assert summary['missing'] == 0, 'Memory failure; do not retry automatically'
        print(json.dumps(summary),flush=True)
    finally:
        stop.set();thread.join(timeout=10)


if __name__ == '__main__':
    main()
