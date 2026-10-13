from pathlib import Path
import subprocess,json,sys
sys.stdout.reconfigure(encoding='utf-8')
base=Path(__file__).parent
script=base.parent.parent/'server/queues/refill_finch_additional_20261009.py'
command='python3 - /tmp/tripilot-trained-adapters-20261008/finch_s20261012_lora_f16.gguf d96f5ce87bf3df7a0a7f7701389743642d47f02c79f5d7e389a6ae0e8fb062cd'
r=subprocess.run(['ssh','acopilot-gpu',command],input=script.read_text(encoding='utf-8'),text=True,encoding='utf-8',capture_output=True,check=True)
audit=json.loads(r.stdout)
with (base/'finch_refill_hb0754_20261009.json').open('x',encoding='utf-8') as f:json.dump(audit,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in audit.items() if k!='added_jobs'},ensure_ascii=False))
