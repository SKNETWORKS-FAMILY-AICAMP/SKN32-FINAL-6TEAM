"""SFT-as-context 여행 적용판. 기존 worker에서 원본 부모 모델만 두 번째 추론한다."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

def parse(content):
    m = re.search(r'"item"\s*:\s*(null|\d+)', content)
    return (bool(m), None if not m or m.group(1) == 'null' else int(m.group(1)))

def main():
    assert not os.environ.get('LORA'), 'Second pass must use the unchanged publisher original'
    tag = os.environ['TAG']; path = Path(os.environ['PROMPTS']); rows = sorted(json.loads(path.read_text()), key=lambda x: (x['set'], x['qi']))
    assert len({r['i'] for r in rows}) == len(rows)
    engine = os.environ['LLAMA_SERVER']; port = os.environ['PORT']; model = os.environ['GGUF']
    env = dict(os.environ, LD_LIBRARY_PATH=str(Path(engine).parent)+':'+os.environ.get('LD_LIBRARY_PATH',''))
    command = ['taskset','-c',os.environ.get('CORES','0-5'),engine,'-m',model,'-t','4','-ngl','99','-c','4096','-np','1','--host','127.0.0.1','--port',port,'--jinja']
    contract = dict(paper='2610.11132v1', method='travel adaptation; not original paper reproduction', prompt_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), command=command, context=4096,max_tokens=16,temperature=0,seed=0,
        first_pass_reused=True, end_to_end_latency_measured=False, second_pass_our_training=False, independent_holdout=False,
        parser='same item value regex as historical baselines; separate strict_json diagnostic', automatic_retry=False)
    with Path('context_contract.json').open('x') as f: json.dump(contract,f,indent=2)
    def post(endpoint, body):
        req=urllib.request.Request(f'http://127.0.0.1:{port}/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        return json.loads(urllib.request.urlopen(req,timeout=900).read())
    with Path('engine.log').open('x') as log:
        proc = subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            healthy=False
            for _ in range(600):
                if proc.poll() is not None: raise RuntimeError('Model load failed; preserve attempt')
                try: urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=3); healthy=True; break
                except Exception: time.sleep(3)
            assert healthy, 'Health timeout'
            with Path(f'd_test_{tag}.jsonl').open('x',encoding='utf8') as f:
                for n,x in enumerate(rows,1):
                    r={k:v for k,v in x.items() if k!='prompt'}; begin=time.perf_counter()
                    body=dict(messages=[dict(role='user',content=x['prompt'])],max_tokens=16,temperature=0,seed=0,cache_prompt=True,chat_template_kwargs=dict(enable_thinking=False))
                    try:
                        template=post('apply-template',body)['prompt']; tokens=post('tokenize',dict(content=template,add_special=True))['tokens']
                        r['input_tokens']=len(tokens)
                        if len(tokens)+16>4096: raise ValueError('Context overflow; no truncation or omitted row')
                        result=post('v1/chat/completions',body); choice=result['choices'][0]; content=choice['message'].get('content') or ''
                        parsed,pick=parse(content); r.update(content=content,parsed=parsed,pick=pick,finish_reason=choice.get('finish_reason'),usage=result.get('usage'))
                        try:
                            obj=json.loads(content);r['strict_json']=isinstance(obj,dict) and set(obj)=={'item'} and (obj['item'] is None or type(obj['item']) is int)
                        except (ValueError,TypeError): r['strict_json']=False
                    except Exception as exc: r.update(parsed=False,pick=None,error=repr(exc))
                    r['ms']=round((time.perf_counter()-begin)*1000); f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
                    if n%100==0: print('SAVED',n,'/',len(rows),flush=True)
        finally:
            if proc.poll() is None: proc.terminate();proc.wait(timeout=30)

if __name__=='__main__': main()
