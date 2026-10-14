"""Verify the exact base+adapter in the queued inference engine before release.

Readiness and two nonempty completions are NOT model accuracy measurements.
Failure leaves no ready adapter, so downstream evaluations cannot repeat a
known incompatible load. All process work remains inside the exclusive queue.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import urllib.request


def sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def main():
    config=json.loads(Path(__file__).with_name('load_gates_private.json').read_text())[os.environ['TAG']]
    assert sha(config['model'])==config['base_sha256'], 'wrong base for inference gate'
    lora=Path(config['lora']);ready=Path(config['ready_lora'])
    assert lora.is_file() and not ready.exists(), 'preserve previous released adapter'
    if config.get('conversion_record'):
        conversion=json.loads(Path(config['conversion_record']).read_text())
        assert sha(lora)==conversion['output_sha256']
    engine=os.environ['LLAMA_SERVER'];url='http://127.0.0.1:'+os.environ['PORT']
    command=[engine,'-m',config['model'],'--lora',str(lora),'-ngl','99','-t','4','-c','16384','-np','1',
             '--jinja','--host','127.0.0.1','--port',os.environ['PORT']]
    with Path('load_engine.log').open('x') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
            env=dict(os.environ,LD_LIBRARY_PATH=str(Path(engine).parent)))
        try:
            for _ in range(300):
                if process.poll() is not None:raise RuntimeError('base_adapter_load_failed')
                try:
                    with urllib.request.urlopen(url+'/health',timeout=2) as response:
                        if response.status==200:break
                except OSError:time.sleep(1)
            else:raise TimeoutError('adapter_load_readiness_timeout')
            with urllib.request.urlopen(url+'/lora-adapters',timeout=10) as response:adapters=json.load(response)
            candidates=adapters if isinstance(adapters,list) else adapters.get('adapters',[])
            assert any(Path(a.get('path','')).name==lora.name and float(a.get('scale',0))==1 for a in candidates), 'adapter not active at scale1'
            prompts=json.loads(Path(config['smoke_prompts']).read_text())[:2];responses=[]
            for prompt in prompts:
                payload={'messages':[{'role':'user','content':prompt['prompt']}], 'temperature':0,
                         'seed':20261019,'max_tokens':32,'chat_template_kwargs':{'enable_thinking':False}}
                request=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=180) as response:raw=json.load(response)
                assert raw['choices'][0]['message'].get('content'), 'empty completion'
                responses.append(raw)
            result=dict(base_sha256=config['base_sha256'],lora_sha256=sha(lora),active_adapters=adapters,
                        responses=responses,accuracy_measured=False,model_adoption=False)
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:process.kill();process.wait()
    temporary=ready.with_name(ready.name+'.ready-tmp');assert not temporary.exists()
    temporary.symlink_to(lora);os.replace(temporary,ready)
    Path('load_gate_passed.json').write_text(json.dumps(result,indent=2))
    Path('d_test_'+os.environ['TAG']+'.jsonl').write_text(json.dumps({'i':0,'parsed':result})+'\n')


if __name__=='__main__':main()
