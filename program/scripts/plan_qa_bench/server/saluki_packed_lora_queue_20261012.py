"""Existing exclusive queue adapter. One control record means execution, not accuracy."""
import json, os, subprocess, sys, hashlib, time
from pathlib import Path

def main():
    config=json.loads(Path(__file__).with_name('queue_private_config.json').read_text(encoding='utf-8-sig'))
    root=Path(__file__).parent
    command=[config['python'],str(root/'runner.py'),'--mode','gpu-smoke-and-train',
             '--model',os.environ['GGUF'],'--data',config['data'],
             '--cpu-report',str(root/'cpu_attempt1/cpu_preflight.json'),
             '--output',str(Path.cwd()/'train_attempt1'),'--execute-in-queue']
    for path in (config['python'],config['data'],root/'runner.py',root/'cpu_attempt1/cpu_preflight.json'):
        if not Path(path).is_file():raise RuntimeError(f'prerequisite file missing: {path}')
    if '--validate-only' in sys.argv:
        print(json.dumps({'status':'validated','command_arguments':len(command),'gpu_started':False}));return
    log=Path('training_driver.log')
    with log.open('x',encoding='utf-8') as handle:
        code=subprocess.run(command,stdout=handle,stderr=subprocess.STDOUT,env=dict(os.environ,OMP_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false')).returncode
    result_path=Path('train_attempt1/completed.json')
    success=code==0 and result_path.is_file()
    parsed=json.loads(result_path.read_text()) if success else None
    record={'i':0,'parsed':{'execution_complete':True,'rows_trained':parsed['rows'],'accuracy_measurement':False} if success else None,
            'error':None if success else f'terminal training attempt exit {code}; inspect preserved train_attempt1/failed.json',
            'purpose':'exclusive GPU smoke then full approved 2613-row training, control record only',
            'unix_time':time.time()}
    Path(f"d_test_{os.environ['TAG']}.jsonl").write_text(json.dumps(record,ensure_ascii=False)+'\n',encoding='utf-8')
    if not success:sys.exit(code or 1)

if __name__=='__main__':main()
