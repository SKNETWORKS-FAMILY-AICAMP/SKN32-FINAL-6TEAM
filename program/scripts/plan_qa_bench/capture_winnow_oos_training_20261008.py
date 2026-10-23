"""완료된 Winnow-E4B 학습 산출물과 레시피 근거를 읽기 전용으로 고정한다."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8')
remote=r'''
import json,pathlib,hashlib,importlib.metadata
p=pathlib.Path('/root/adapters/winnow_e4b_oos')
files={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in p.iterdir() if f.is_file()}
g=pathlib.Path('/root/work/winnow_e4b_oos_lora_f16.gguf')
train=pathlib.Path('/root/work/train_oos.jsonl')
code=pathlib.Path('/root/work/qlora_train2.py')
config=pathlib.Path('/root/hf_models/winnow-e4b-hf/config.json')
text=json.loads(config.read_text()); lang=text.get('text_config',text)
evals=[]
for f in sorted(pathlib.Path('/root/work').glob('eval_winnow_e4b_oos_mix*.json')):
 r=json.loads(f.read_text());evals.append({'name':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'modes':{key:{'saved':len(value['picks']),'errors':value['_errors']} for key,value in r.items() if isinstance(value,dict) and 'picks' in value}})
log=pathlib.Path('/root/qlora_eval_winnow_e4b_oos.log').read_text(errors='replace')
print(json.dumps({'hf_files':files,'adapter_config':json.loads((p/'adapter_config.json').read_text()),
 'gguf':{'bytes':g.stat().st_size,'sha256':hashlib.sha256(g.read_bytes()).hexdigest()},
 'train':{'name':train.name,'rows':sum(1 for line in train.open() if line.strip()),'sha256':hashlib.sha256(train.read_bytes()).hexdigest()},
 'training_code_sha256':hashlib.sha256(code.read_bytes()).hexdigest(),'base_config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
 'base_config_subset':{k:lang.get(k) for k in ['model_type','hidden_size','num_hidden_layers','num_attention_heads','num_key_value_heads','vocab_size']},
 'versions':{k:importlib.metadata.version(k) for k in ['torch','transformers','peft','bitsandbytes']},
 'evaluation_files':evals,'evaluation_done':'EVAL_DONE winnow_e4b_oos' in log,'evaluation_log_tail':log[-1200:],
 'training_log_tail':pathlib.Path('/root/qlora_train_winnow_e4b_oos.log').read_text(errors='replace')[-900:]},ensure_ascii=False))
'''
run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',sys.argv[1],'/root/venv_imajev/bin/python -'],input=remote,text=True,encoding='utf-8',capture_output=True,timeout=60)
if run.returncode:raise RuntimeError(run.stderr)
r=json.loads(run.stdout)
hf=ROOT/'datasets/core/pointing/trainset/train_oos/winnow_e4b_oos_hf_adapter_2026-10-08_1308'
gguf=ROOT/'datasets/core/pointing/trainset/train_oos/winnow_e4b_oos_lora_f16_2026-10-08_1308.gguf'
for name,info in r['hf_files'].items():
 p=hf/name
 assert p.stat().st_size==info['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==info['sha256'],name
assert gguf.stat().st_size==r['gguf']['bytes'] and hashlib.sha256(gguf.read_bytes()).hexdigest()==r['gguf']['sha256']
r.update({'observed_at_utc':datetime.now(timezone.utc).isoformat(),'hf_local':hf.relative_to(ROOT).as_posix(),
 'gguf_local':gguf.relative_to(ROOT).as_posix(),'local_remote_hashes_match':True,'our_training':True,
 'training_recipe':{'seed':20261012,'rank':16,'epochs':2,'lr':2e-4,'accum':8,'training_minutes':193.9,'max_gpu_gb_log':10.6},
 'additional_eval_queued':False,'additional_eval_resume':'Wait for basic evaluation completion; verify Winnow base GGUF provenance/adapter compatibility; register unique D/D2/D3/H/MX jobs in existing GPU A manifest.'})
name=sys.argv[2] if len(sys.argv)>2 else 'training_archive_verified.json'
assert Path(name).name==name and name.endswith('.json'), 'Output must be a new JSON filename'
out=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308'/name
with out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
print(json.dumps({k:r[k] for k in ['local_remote_hashes_match','train','training_recipe','evaluation_done','evaluation_files','versions','additional_eval_queued']},ensure_ascii=False))
