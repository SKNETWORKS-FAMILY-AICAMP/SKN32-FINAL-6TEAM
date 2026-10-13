"""Convert a completed custom packed LoRA to PEFT and GGUF on tmpfs only."""
import hashlib,json,os,sys,subprocess,traceback,shutil,runpy
from pathlib import Path

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def main():
    cfg=json.loads(Path(__file__).with_name('queue_private_config.json').read_text(encoding='utf-8-sig'))
    if Path(sys.executable).absolute()!=Path(cfg['python']).absolute():
        os.execv(cfg['python'],[cfg['python'],str(Path(__file__).resolve())]+sys.argv[1:])
    if '--converter-child' in sys.argv:
        converter=Path(cfg['converter']);sys.path.insert(0,str(converter.parent));sys.path.insert(1,str(converter.parent/'gguf-py'))
        from conversion import get_model_class
        # No MTP weights were adapted. The original Qwen3.5 architecture is retained.
        get_model_class('Qwen3_5ForCausalLM').no_mtp=True
        sys.argv=[str(converter)]+sys.argv[sys.argv.index('--converter-child')+1:]
        runpy.run_path(str(converter),run_name='__main__');return
    source=Path(cfg['train_root']);dest=Path(cfg['converted_root']);adapter=source/'adapter.safetensors'
    if '--validate-only' in sys.argv:
        assert Path(cfg['converter']).is_file();assert str(dest).startswith('/dev/shm/')
        print(json.dumps({'status':'validated','waiting_for_training':not (source/'completed.json').exists(),'gpu_started':False}));return
    record=None
    try:
        terminal=Path('conversion_completed.json')
        if terminal.exists() or Path('conversion_failed.json').exists():raise RuntimeError('terminal conversion attempt already exists')
        status=json.loads((source/'completed.json').read_text());settings=json.loads((source/'adapter_config.json').read_text())
        if status['rows']!=2613 or digest(adapter)!=status['adapter_sha256']:raise RuntimeError('training completion/adapter identity mismatch')
        if settings['base_sha256']!='4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb':raise RuntimeError('wrong original base')
        if not str(dest).startswith('/dev/shm/'):raise RuntimeError('conversion output must stay on tmpfs')
        if shutil.disk_usage('/dev/shm').free < 1024**3:raise RuntimeError('tmpfs free space below 1GiB')
        if int(Path('/sys/fs/cgroup/memory.max').read_text())-int(Path('/sys/fs/cgroup/memory.current').read_text()) < 2*1024**3:raise RuntimeError('conversion RAM headroom below 2GiB')
        dest.mkdir(exist_ok=False);peft=dest/'peft';base=dest/'base';peft.mkdir();base.mkdir()
        os.environ['CUDA_VISIBLE_DEVICES']=''
        from safetensors.torch import load_file,save_file
        from transformers import AutoConfig
        weights=load_file(str(adapter),device='cpu')
        renamed={}
        for name,value in weights.items():
            if not name.endswith(('.lora_A','.lora_B')):raise RuntimeError('unexpected custom adapter key')
            renamed['base_model.model.'+name+'.weight']=value
        if len(renamed)!=2*len(settings['targets']):raise RuntimeError('adapter tensor count differs from targets')
        save_file(renamed,str(peft/'adapter_model.safetensors'))
        (peft/'adapter_config.json').write_text(json.dumps({'peft_type':'LORA','r':settings['rank'],'lora_alpha':settings['alpha'],'lora_dropout':settings['dropout'],'target_modules':settings['targets'],'task_type':'CAUSAL_LM'}))
        model=Path(cfg['original_model']);config=AutoConfig.from_pretrained(str(model.parent),gguf_file=model.name,local_files_only=True)
        config.architectures=['Qwen3_5ForCausalLM'];config.save_pretrained(base)
        del weights,renamed
        temp=dest/'adapter_f16.incomplete.gguf';final=dest/'adapter_f16.gguf'
        command=[cfg['python'],str(Path(__file__)),'--converter-child','--base',str(base),'--outtype','f16','--outfile',str(temp),str(peft)]
        with Path('converter.log').open('x') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        sys.path.insert(0,str(Path(cfg['converter']).parent/'gguf-py'));import gguf,numpy as np
        reader=gguf.GGUFReader(str(temp));names=[t.name for t in reader.tensors]
        if len(names)!=2*len(settings['targets']) or len(set(names))!=len(names):raise RuntimeError('GGUF coverage differs from adapter')
        if not all(np.isfinite(t.data).all() for t in reader.tensors):raise RuntimeError('nonfinite f16 converted tensor')
        del reader;os.replace(temp,final)
        result={'status':'completed','source_adapter_sha256':status['adapter_sha256'],'output_sha256':digest(final),'output_bytes':final.stat().st_size,'tensor_count':len(names),'architecture':'qwen35','mtp_adapters':False,'accuracy_measurement':False}
        terminal.write_text(json.dumps(result,indent=2));record={'i':0,'parsed':result,'error':None}
    except Exception as exc:
        result={'status':'failed','error':str(exc),'traceback':traceback.format_exc(),'retry_requires_fix':True}
        Path('conversion_failed.json').write_text(json.dumps(result,indent=2));record={'i':0,'parsed':None,'error':str(exc)}
    Path(f"d_test_{os.environ['TAG']}.jsonl").write_text(json.dumps(record)+'\n')
    if record['error']:sys.exit(1)

if __name__=='__main__':main()
